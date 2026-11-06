from .Massa_funcs import massa
import json
from Interfaces.MQTT import broker
import pandas as pd
from Interfaces.Scheduler import scheduler, watchdog

with open("./confluence_config.json",'r') as fid:
    configs = json.load(fid)

# Pull out a few commonly used parameters from the config file
node = configs['Node Name']
interface = 'Massa_Ultrasonic'
comms_configs = configs[interface]['comms']
publish_configs = configs[interface]['publish']

# instantiate the massa objects.  Open the comm port to establish communication with the devices.
massas = massa(comm_port=comms_configs['com port'],ids=comms_configs["ids"],names=configs[interface]['device names'],offset_array=configs[interface]["offsets_mm"])

# Define functions for what to do if message is received from the user (not the sensor)
def on_massa_message(client,userdata,message):
    print(f"Messaged Received on Topic:{message.topic}.  Message: {message.payload.decode()}")

broker.client.message_callback_add(f"{node}/{interface}/commands",on_massa_message)


def task():
    """
    This function is the task that will be called each time the scheduled job is executed. 
    This function handle is the value that should be entered for the "func" parameter of scheduler.add_job()

    Arguments: 
    none

    Returns:
    none
    """
    massas.poll_status()
    # poll_status() sets the error array to NaN floats when the read raised.
    watchdog.report(interface, all(isinstance(e, str) for e in massas.error_array))
    broker.publish_message(topic=f"{node}/{interface}",payload=pd.Series(massas.status).to_json())
    # print(pd.Series(massas.status).to_json()) # Using the pandas to_json instead of json.dumps handles converting to NAN to null.  JSON format doesn't support NANs.
if publish_configs['type'] == 'cron':
    job_configuration = {
        "func":task,
        "args":[],
        "trigger":"cron",
        "hour":publish_configs['interval_hr'],
        "minute":publish_configs['interval_min'],
        "second":publish_configs['interval_sec'],
        "id":"Massa_Ultrasonic"
    }
elif publish_configs['type'] =='interval':
        job_configuration = {
        "func":task,
        "args":[],
        "trigger":"interval",
        "seconds":publish_configs['seconds'],
        "id":"Massa_Ultrasonic"
    }


watchdog.register(interface)
scheduler.add_job(**job_configuration)