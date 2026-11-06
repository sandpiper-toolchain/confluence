# confluence
Convert signals (analog, serial, modbus, etc.) to MQTT that can be integrated into the Sandpiper ecosystem. The name *confluence* evokes the goal of this project which is to bring together multiple streams of data into one unified stream. 

## Network Topology
```
                                                                                                         
                                                                                                         
  ┌──────────┐                                                    ┌───────────────────────────┐          
  │ Sensor 1 ┼─────────┐      ┌───────────────────┐               │       MQTT Broker         │          
  └──────────┘   RS485 └─────►│ Confluence Node   │     TCP       │                           │          
                              │                   ├◄─────────────►│   Raspberry Pi running    │          
  ┌──────────┐         ┌─────►│ (Raspberry Pi)    │               │    Eclipse Mosquitto      │          
  │ Sensor 2 ┼─────────┘      └───────────────────┘               └────▲───────────────▲──────┘          
  └──────────┘ Modbus RS485                                            │               │                 
                                                                       │TCP            │TCP              
                                                                   ┌───┘               └───┐             
                                                                   │                       │             
                                                            ┌──────▼───────┐   ┌───────────▼──────────┐  
                                                            │ User Device  │   │  Additional          │  
                                                            │  HMI / GUI   │   │  Control/Measurement │  
                                                            │              │   │  (PLC, etc)          │  
                                                            └──────────────┘   └──────────────────────┘  
                                                                                                         

```
## Requirements
You will need a TCP network that you can add devices to and an MQTT broker that is accessible on that network. If you don't already have an MQTT broker I recommend setting up a Raspberry Pi as a broker using Eclipse Mosquitto.  Instructions for doing this can be found [here](mosquitto_raspberry_pi_setup.md). Each *confluence* "node" was envisioned to be a Raspberry Pi, but really any systemd-based Linux device could be used. Each node will need to have access to the MQTT broker over the TCP network and be able to connect to the sensor or device you would like to get data from/control.  For example if you want to get data from a Massa Ultrasonic distance sensor you will need to have USB to RS485 converter plugged into your node and properly wired to the sensor. 

## Installation
Clone or fork this repo onto each device that will be used as a node on the *confluence* network. 

Two scripts in `scripts/` automate the majority of setting up a new node — both are safe to re-run if you need to change
something later.  When setting up a new node, run both of these scripts.

- **`scripts/setup_udev_aliases.sh`** — gives this node's serial devices
  stable `/dev` names (e.g. `/dev/massa_ultrasonic`) instead of raw
  `/dev/ttyUSB*` names that can shuffle across reboots/re-enumeration.
  Takes the alias-to-device mapping as command-line arguments rather than
  hardcoding one hub's serial numbers, so the same script works on any
  node.

  Run: `./scripts/setup_udev_aliases.sh --list` (no sudo needed) on the node to list
  serial devices that are currently connected to the node. You should get a response like this: 

  ```
  Serial devices currently visible on this machine:

  /dev/ttyUSB1  ID_SERIAL_SHORT=BG00DTH3  ID_USB_INTERFACE_NUM=00

  Pass ALIAS=SERIAL or ALIAS=SERIAL:IFNUM pairs to install rules using these.
  ```

  Identify which device is connected to that serial port. If you have multiple serial devices connected, you may want to plug them in one at a time so its easier to identify which is which. To assign that serial port an alias run the command:

  `sudo ./scripts/setup_udev_aliases.sh [ALIAS]=[ID_SERIAL_SHORT]`

  For example, if I'm setting up a Massa ultrasonic distance sensor and I received the port list response shown above I would run the command: 
  `sudo ./scripts/setup_udev_aliases.sh massa_ultrasonic=BG00DTH3`

  Now you can configure the `confluence_config.json` for that device with com port information `"com port": "/dev/[ALIAS]"` or for the example with the Massa: `com port: "/dev/massa_ultrasonic`

- **`scripts/setup_confluence_service.sh`** configures    *confluence* to run as a service on the Raspberry Pi. To use, run as root on the node itself (`sudo ./scripts/setup_confluence_service.sh --user root`) which creates a venv, installs `requirements.txt` into it, scaffolds `credentials.py` from the example if it doesn't exist yet, and
  installs/enables a `systemd` unit templated with this machine's actual
  user and paths (rather than the one committed at the repo root, which
  is one specific deployment's hardcoded values). `--help` for options,
  including `--remote-broker` for the common case where this node doesn't
  run its own Mosquitto but is publishing to an MQTT broker hosted on a different device. 

  After running the script, if you didn't pass the `--start` flag, you need to start the service with: `sudo systemctl start confluence`.  It will automatically start on boot if the system restarts. If you make changes to `confluence_config.json` or any of the code you will need to restart the service with the command: `sudo systemctl restart confluence`.

  **Monitoring the running service for errors:**  
  When confluence is running as a service, it will not print errors to the terminal automatically. Errors are logged using systemd's logging utility: `journalctl`. To view live logs in real time use the following command: 

  `sudo journalctl -u confluence.service -f`

  or to view the last 50 lines of the log:

  `sudo journalctl -u confluence.service -n 50 --no-pager`

  or to view logs generated only during the current boot:
  
  `sudo journalctl -u confluence.service -b`


Neither set up script touches `confluence_config.json` — that file is
  per-node/per-hardware and still needs to be written by hand (or copied
  from another node's and edited) as described below.

## Configuring the node with `confluce_config.json`:
You will need to update the file `confluence_config.json` for each specific node. This file tells the *confluence* node which devices are attached to the node (Active Interfaces), gives necessary settings to communicate with the sensor/device (com port, baudrate, etc.) and sets the rate to publish data to the MQTT broker. A sample of the configuration settings for each device should be included in the device's directory in the *Interfaces* folder (e.g. `confluence/Interfaces/Massa_Ultrasonic/Massa_confluence_config_example.json`)

### A note on publication intervals in `confluence_config.json`
*confluence* uses the Advance Python Scheduler (APScheduler) to poll sensors at regular intervals. Two different trigger methods are currently supported in *confluence*: cron and interval. Cron is designed to be used for slower sample rates and triggers at nice round timestamps. For example if configured to sample 1 per minute, a cron trigger will fire at 12:00:00 and then again at 12:01:00 instead of once a minute based on the start time. Interval can be configured for intervals faster than 1 second and starts when the task is first triggered.

## Configuring the connection to the MQTT broker
You will need to create a `credentials.py` file that lists the IP address and port number for your MQTT broker. An example of this file can be found in `credentials_example.py`, or if you already ran `scripts/setup_confluence_service.sh` one was already created for you. You will need to update the `mqtt_broker_address` field to the IP address of your MQTT broker. If the MQTT broker is running on this node, enter `'localhost'` in this field. The port number 1883 is the default port for MQTT brokers. Unless you set up a custom port number when you set up Mosquitto you shouldn't need to change this value.

## Extending *confluence*
*confluence* was written with extensibility in mind. To add a new device type to *confluence*, create a new directory in the *Interfaces* folder. Within that directory you will need 3 files: 
- an `__init__.py` file to set up the directory as a python package
- a `device_funcs.py` file that contains functions and methods to establish communications with the sensor/device, retreive data and/or send commands to the senor/device.
- `job_config.py` file that contains the task that is run at the interval given in `confluence_config.json`. This file contains the functions to publish data to the MQTT broker and/or process commands receieved over MQTT. 

**No changes to other code are necessary when adding a new interface.** The main script `confluence_daemon.py` reads the `confluence_config.json` file and imports the appropriate packages for each "active interface". For this reason, its important that references to the interface in the config json are spelled the exact same way (case sensitive) as the package name (the directory name in the *Interfaces* folder).

An example of the `confluence_config.json` file should be included in the package directory so that users know how to properly add the configuration to the config json to use the new interface. 

### Read Only Example
An example of read-only interface can be found in [`Interfaces/Massa_Ultrasonic`](./Interfaces/Massa_Ultrasonic/). This interface polls a Massa Ultrasonic Distance sensor at the interval set in `confluence_config.json` and publishes the data to the MQTT broker. 

### Read/Write Example
An example of a read-write interface can be found in [`Interfaces/Fuji_Frenic_VFD`](./Interfaces/Fuji_Frenic_VFD/).  This interface polls the status of a motor variable frequency drive (VFD) at the interval set in `confluence_config.json` and publishes the data to the MQTT broker, just like the Massa interface.  However, this interface also contains instructions in the `job_config.py` file to subscribe to a "commands" topic on the MQTT broker and to respond to commands recieved in that topic.  For example, if the confluence node receives a message in the commands topic that contains the subtopic "send_setpoint" the node will send a new frequency setpoint to the VFD. The frequency setpoint value is contained in the payload of the MQTT message with the topic `.../commands/send_setpoint`. Some commands do not require values in the payload of the message. For example if the node receives the command `start_motor` as a subtopic in the commands topic, it sends the modbus command to the VFD to start the motor. Any value contained in the payload of the message (if there is one) is ignored. 

