"""Identify which /dev/serial/by-id port is which physical device.

For hardware wired through a shared USB hub, the by-id names alone don't
say which port is Massa vs. Fuji VFD vs. Teknic ClearCore — this probes
each candidate port with each device's actual read-only wire protocol and
reports which one answered. Safe to run any time: it never writes to the
VFD or ClearCore, only issues read queries.

Does NOT probe the ClearCore directly (its safl_ocean_hardware.TeknicMotor
protocol isn't available to this repo) — whatever port doesn't answer as
Massa or VFD is the ClearCore by elimination, assuming exactly three
devices are attached to the hub.

Usage (from the confluence repo root, inside the venv):
    python scripts/probe_serial_ports.py
"""

import glob
import os

import serial

# Adjust this if your hub's by-id name differs — see `ls /dev/serial/by-id/`.
# Ports named after a single-adapter device (e.g. the macron gantry bridge's
# AV0K9L0C) are NOT part of this hub and are excluded automatically.
HUB_GLOB = "/dev/serial/by-id/*-if0[0-3]-port0"

MASSA_BAUD = 19200
MASSA_ID = 1  # confluence_config.json Massa_Ultrasonic -> comms.ids[0]

VFD_BAUD = 19200
VFD_BYTESIZE = 8
VFD_PARITY = "N"
VFD_STOPBITS = 2
VFD_SERVER_ID = 1  # confluence_config.json Fuji_Frenic_VFD -> comms.serverID


def probe_massa(port: str) -> bool:
    """Send a Massa status query (see Massa_funcs.py's poll_status()) and
    check for a well-formed 6-byte reply from the expected device id."""
    try:
        ser = serial.Serial(
            port, baudrate=MASSA_BAUD, timeout=0.3, bytesize=8, parity="N", stopbits=1
        )
    except Exception:
        return False
    try:
        message = [170, MASSA_ID, 3, 0, 0, (170 + MASSA_ID + 3 + 0 + 0) % 256]
        ser.write(bytes(message))
        res = ser.read(6)
        return len(res) == 6 and res[0] == MASSA_ID
    except Exception:
        return False
    finally:
        ser.close()


def probe_vfd(port: str) -> bool:
    """Read the Fuji VFD's frequency setpoint register (2053, read-only
    here) over Modbus RTU — a clean reply (no CRC/timeout error) means
    this port is the VFD."""
    try:
        import minimalmodbus
    except ImportError:
        print("  (skipping VFD probe: minimalmodbus not installed)")
        return False
    try:
        instrument = minimalmodbus.Instrument(port, VFD_SERVER_ID, debug=False)
        instrument.serial.baudrate = VFD_BAUD
        instrument.serial.bytesize = VFD_BYTESIZE
        instrument.serial.parity = VFD_PARITY
        instrument.serial.stopbits = VFD_STOPBITS
        instrument.serial.timeout = 0.3
        instrument.mode = minimalmodbus.MODE_RTU
        instrument.read_register(2053, 2, 3)
        return True
    except Exception:
        return False


def main():
    candidates = sorted(glob.glob(HUB_GLOB))
    if not candidates:
        print(f"No ports matched {HUB_GLOB!r} — check `ls /dev/serial/by-id/` and adjust HUB_GLOB.")
        return

    print(f"Probing {len(candidates)} port(s):\n")
    results = {}
    for path in candidates:
        name = os.path.basename(path)
        print(f"{name}:")
        if probe_massa(path):
            print("  -> Massa_Ultrasonic (gauge)")
            results[path] = "Massa_Ultrasonic"
            continue
        if probe_vfd(path):
            print("  -> Fuji_Frenic_VFD (flow)")
            results[path] = "Fuji_Frenic_VFD"
            continue
        print("  -> no match (Teknic_ClearCore, by elimination, if exactly 3 devices are wired)")
        results[path] = "Teknic_ClearCore?"

    print("\nSummary:")
    for path, label in results.items():
        print(f"  {label:20s} {path}")


if __name__ == "__main__":
    main()
