#!/usr/bin/env bash
# Set up confluence to run as a systemd service on this Pi (or any
# systemd-based Linux node): creates a venv, installs requirements,
# scaffolds credentials.py if missing, and installs/enables a
# confluence.service unit templated with THIS machine's actual user and
# paths — the committed confluence.service in the repo root hardcodes one
# specific deployment's user/paths (see the "fix: correct confluence.service
# user/paths" commits in this repo's history for why that's bitten before);
# this generates a correct one for wherever it's actually run instead.
#
# Usage (from the confluence repo root, or pass --repo-dir):
#   sudo ./scripts/setup_confluence_service.sh [options]
#
# Options:
#   --user USER        System user to run the service as (default: the
#                       owner of the repo directory).
#   --repo-dir DIR      Path to the confluence repo (default: parent of
#                       this script's own directory).
#   --venv DIR          Path to create/reuse a venv at (default:
#                       ~USER/.confluence-venv).
#   --start             Start the service immediately after enabling it
#                       (default: enabled for next boot, not started now —
#                       review `systemctl status confluence` first).
#   --remote-broker      This node does NOT run its own Mosquitto broker
#                       (the common case per the README's network
#                       topology — nodes are typically separate machines
#                       from the broker). Drops the
#                       After=/Requires=mosquitto.service lines so the
#                       service doesn't wait on/require a broker that will
#                       never start here. Default assumes mosquitto runs
#                       on this same machine (matches the committed
#                       confluence.service, i.e. red.lab's setup).
#   -h, --help          Show this help.
#
# What this does NOT do: write confluence_config.json or set up udev
# device aliases (see setup_udev_aliases.sh for that) or install/configure
# Mosquitto (see mosquitto_raspberry_pi_setup.md) — those are
# per-deployment/per-hardware decisions, not safe to automate blindly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_USER=""
VENV_DIR=""
START_NOW=0
REMOTE_BROKER=0

usage() {
    grep '^#' "$0" | sed -n '2,/^set -e/p' | sed '$d' | sed 's/^# \{0,1\}//'
    exit "${1:-1}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --user) SERVICE_USER="$2"; shift 2 ;;
        --repo-dir) REPO_DIR="$(cd "$2" && pwd)"; shift 2 ;;
        --venv) VENV_DIR="$2"; shift 2 ;;
        --start) START_NOW=1; shift ;;
        --remote-broker) REMOTE_BROKER=1; shift ;;
        -h|--help) usage 0 ;;
        *) echo "Unknown argument: $1" >&2; usage 1 ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo ./scripts/setup_confluence_service.sh ...)" >&2
    exit 1
fi

if [ ! -f "$REPO_DIR/confluence_daemon.py" ]; then
    echo "confluence_daemon.py not found in $REPO_DIR — pass the correct --repo-dir." >&2
    exit 1
fi

if [ -z "$SERVICE_USER" ]; then
    SERVICE_USER="$(stat -c '%U' "$REPO_DIR")"
    echo "No --user given; defaulting to $REPO_DIR's owner: $SERVICE_USER"
fi
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    echo "User '$SERVICE_USER' does not exist on this system." >&2
    exit 1
fi
USER_HOME="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"

if [ -z "$VENV_DIR" ]; then
    VENV_DIR="$USER_HOME/.confluence-venv"
fi

echo "Repo dir:     $REPO_DIR"
echo "Service user: $SERVICE_USER"
echo "Venv:         $VENV_DIR"
echo

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating venv at $VENV_DIR..."
    sudo -u "$SERVICE_USER" python3 -m venv "$VENV_DIR"
else
    echo "Venv already exists at $VENV_DIR, reusing it."
fi

echo "Installing requirements..."
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

if [ ! -f "$REPO_DIR/credentials.py" ]; then
    echo "No credentials.py found — copying credentials_example.py."
    echo "EDIT $REPO_DIR/credentials.py with your MQTT broker's address/port before starting the service."
    sudo -u "$SERVICE_USER" cp "$REPO_DIR/credentials_example.py" "$REPO_DIR/credentials.py"
else
    echo "credentials.py already exists, leaving it as-is."
fi

if [ ! -f "$REPO_DIR/confluence_config.json" ]; then
    echo "WARNING: $REPO_DIR/confluence_config.json does not exist — the service will fail to" >&2
    echo "         start until it's created (see README.md's 'Running confluence' section)." >&2
fi

if [ "$REMOTE_BROKER" -eq 1 ]; then
    BROKER_UNIT_LINES="After=network-online.target
Wants=network-online.target"
else
    BROKER_UNIT_LINES="After=network-online.target mosquitto.service
Wants=network-online.target
Requires=mosquitto.service"
fi

UNIT_FILE=/etc/systemd/system/confluence.service
echo "Writing $UNIT_FILE..."
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Confluence MQTT node
$BROKER_UNIT_LINES

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python -u confluence_daemon.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable confluence

if [ "$START_NOW" -eq 1 ]; then
    systemctl restart confluence
    echo
    echo "Started. Status:"
    systemctl status confluence --no-pager || true
else
    echo
    echo "Enabled for next boot but not started (pass --start to start it now)."
    echo "Review the config above, then: sudo systemctl start confluence"
fi
