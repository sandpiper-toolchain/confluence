# import Interfaces.Massa_Ultrasonic as Massa_Ultrasonic
import json
from Interfaces.Scheduler import scheduler, watchdog
import importlib

# scheduler = BlockingScheduler()
config_file_path = './confluence_config.json'

def schedule_jobs():
    with open(config_file_path,'r') as fid:
        configs = json.load(fid)
    
    active_interfaces = [interface for interface in configs['Active Interfaces']]

    # Add A job for each active interfaces. The name of the interface in the confluence_config.json file must match the name (case sensitive) of the module folder in the Interfaces Directory.
    for io in active_interfaces:
        importlib.import_module(f"Interfaces.{io}")

    watchdog.start()

    try:
        print("APScheduler started with parameterized jobs...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Shutting Down APScheduler")


if __name__ == "__main__":
    schedule_jobs()
    



