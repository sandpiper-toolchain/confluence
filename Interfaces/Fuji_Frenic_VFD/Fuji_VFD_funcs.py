import time
import minimalmodbus
import datetime

def function_code_to_register(function_code: str):
    function_code = function_code.upper()

    fc_dict = {
        "F":0x00,
        "E":0x01,
        "C":0x02,
        "P":0x03,
        "H":0x04,
        "S":0x07,
        "M":0x08,
        "Y":0x0E
    }

    high_byte = fc_dict[function_code[0]]
    low_byte = f"{int(function_code[1:]):02x}"

    hex_code = f"{high_byte:02x}{low_byte}"

    register_address = int(hex_code,16)

    return register_address
    

class VFD():
    def __init__(self,comm_port,server_id,baudrate,bytesize,parity,stopbits,timeout):
        try: 
            self.comm = minimalmodbus.Instrument(comm_port, server_id, debug=False)
            self.comm.serial.baudrate = baudrate
            self.comm.serial.bytesize = bytesize
            self.comm.serial.parity = parity
            self.comm.serial.stopbits = stopbits
            self.comm.serial.timeout = timeout   # seconds
            self.comm.mode = minimalmodbus.MODE_RTU   # rtu or ascii mode
            self.comm_status  = 'VFD Com Port Found: '+comm_port
        except Exception as e:
            print(e)
            self.comm_status = 'VFD Com Port Not Found: '+comm_port
            self.comm = ''

        self.comm_errors = 0
        self.analog_input = [float('nan'),float('nan')]

        self.alarm_codes = {0: 'No Alarm',
              1: 'OverCurrent During Acceleration',
              2: 'OverCurrent During Deceleration',
              3: 'OverCurrent During Constant Speed Operation',
              5: 'Ground Fault',
              6: 'OverVoltage During Acceleration',
              7: 'OverVoltage During Decceleration',
              8: 'OverVoltage During Constant Speed Operation or Stopping',
              10: 'Undervoltage',
              11: 'Input Phase Loss',
              14: 'Fuse Blown',
              16: 'Charing Circuit Fault',
              17: 'Heat Sink Overheat',
              18: 'External Alarm (E-Stop)',
              19: 'Internal Air Overheat',
              20: 'Motor Protection (PTC/NTC Thermistor)',
              22: 'Breaking Resistor Overheat',
              23: 'Motor OverLoad',
              24: 'Motor Overload, Motor 2',
              25: 'Inverter Overload',
              27: 'OverSpeed Protection',
              28: 'PG Disconnection',
              29: 'NTC Disconnection Error',
              31: 'Memory Error',
              32: 'Keypad Communications Error',
              33: 'CPU error',
              34: 'Option Communications Error',
              35: 'Option Error',
              36: 'Run Operation Error',
              37: 'Tuning Error',
              38: 'RS-485 Communications Error',
              44: 'Motor Over Load (Motor 3)',
              45: 'Motor OverLoad (motor 4)',
              46: 'Output Phaseloss',
              47: 'Folling Error: Excessive Speed Deviation',
              51: 'Data Save Error on insufficient voltage',
              53: 'RS-485 communications error (Option/Communications port2)',
              54: 'Hardware Error',
              57: 'EN Circuit Error',
              58: 'PID Feedback Disconnection Detected',
              59: 'DB Transistor Trounle',
              100: 'DC fan lock detected',
              101: 'Motor Overload Warning',
              102: 'Cooling Fin Overheat Warning',
              103: 'Life Warning',
              104: 'Command Loss',
              105: 'PID warning ouput',
              106: 'Low Torque Detected',
              108: 'Machine Life (accumulated operation hours)',
              109: 'Machine Life (Number of starting times)',
              254: 'Simulated Error'}
        


    def poll_state(self):
        try: 
            state_message_word = format(self.comm.read_register(2062,0,3),'016b')
            motor_alarm = int(state_message_word[4])
            motor_fwd =   int(state_message_word[15])
            motor_rev =   int(state_message_word[14])
            motor_acel =  int(state_message_word[6])
            motor_decel=  int(state_message_word[5])

            # print(state_message_word)

            if int(motor_alarm) >0: 
                alarm_code = self.comm.read_register(2064,0,3)
                # print('Alarm on '+motor_names[motor_comm_obj.address]+' VFD: '+alarm_codes[int(alarm_code)])
            else:
                alarm_code = 0

            if motor_alarm >0 and alarm_code ==18:
                self.e_stop =1
            else:
                self.e_stop=0

            if motor_fwd:
                self.state_message = 'motor On - Forward'
            elif motor_rev:
                self.state_message = 'motor On - Reverse'
            elif motor_acel:
                self.state_message = 'motor Acceleration'
            elif motor_decel:
                self.state_message = 'motor Decelerating'
            elif motor_alarm:
                self.state_message = self.alarm_codes[int(alarm_code)]
            else:
                self.state_message = 'motor Stopped'

            

        except Exception as e:
            print(e)
            self.comm_errors = self.comm_errors + 1
            self.e_stop = 0
            self.state_message = 'Error getting status'


    def poll_setpoint(self):
        try:
            self.setpoint = self.comm.read_register(2053,2,3)
        except Exception as e:
            print(e)
            self.comm_errors = self.comm_errors + 1
            self.setpoint = float('nan')

    def send_setpoint(self,setpoint):
        try:
            self.comm.write_register(1797,value=float(setpoint),number_of_decimals=2)
        except Exception as e:
            # print(e)
            self.comm_errors = self.comm_errors + 1
            raise

    def start_motor(self):
        start_command = int(b'0000000000000001',2)
        try:
            self.comm.write_register(1798,start_command,0)
        except Exception as e:
            self.comm_errors = self.comm_errors + 1
            print(e)
            raise

    def stop_motor(self):
        stop_command = int(b'0000000000000000',2)
        try:
            self.comm.write_register(1798,stop_command,0)
        except Exception as e:
            print(e)
            self.comm_errors = self.comm_errors + 1
            raise

    def clear_faults(self):
        # self.comm.write_bit(2,1,functioncode=5)
        try:
            command = int(b'1000000000000000',2)
            self.comm.write_register(1798,command,0)
            time.sleep(0.1)
            command = int(b'0000000000000000',2)
            self.comm.write_register(1798,command,0)
        except Exception as e:
            print(e)
            raise
        # self.comm.write_bit(2,1,functioncode=5)

    def poll_monitoring(self):
        try:
            m_codes = self.comm.read_registers(registeraddress=function_code_to_register("M01"),number_of_registers=12)
            self.freq_reference_perc         = m_codes[0]/20000
            self.frequency_reference    = m_codes[4]/100
            self.output_freq_perc       = m_codes[5]/20000
            self.output_freq            = m_codes[8]/100
            self.input_power            = m_codes[9]/100
            self.output_current_effective = m_codes[10]/100
            self.output_voltage_effective = m_codes[11]/10

            self.heat_sink_temp = self.comm.read_register(function_code_to_register('M62'),0)


        except Exception as e:
            print('\nError Polling Monitoring Data:')
            print(f"{e}\n")
            self.comm_errors = self.comm_errors + 1
            self.freq_reference_perc         = float('nan')
            self.frequency_reference    = float('nan')
            self.output_freq_perc       = float('nan')
            self.output_freq            = float('nan')
            self.input_power            = float('nan')
            self.output_current_effective = float('nan')
            self.output_voltage_effective = float('nan')
            self.heat_sink_temp = float('nan')
   
    def poll_status(self):
        self.poll_state()
        self.poll_setpoint()
        self.poll_monitoring()

        self.status = {
            "timestamp":datetime.datetime.now().isoformat(timespec='milliseconds'),
            "com errors":self.comm_errors,
            "state":self.state_message,
            "freq setpoint":f"{self.setpoint:0.2f} Hz",
            "freq perc of max":f"{self.freq_reference_perc*100:0.2f} %",
            "freq reference":f"{self.frequency_reference:0.2f} Hz",
            "output freq":f"{self.output_freq:0.2f} Hz",
            "input power":f"{self.input_power:0.2f} kW",
            "output current":f"{self.output_current_effective} amps",
            "output voltage":f"{self.output_voltage_effective} volts",
            "heat sink temperature":f"{self.heat_sink_temp} degC"
        }

        # print(self.status)


if __name__ == '__main__':
    # for i in range(1,13):
    #     reg = function_code_to_register(f'M{i}')
    #     print(reg)

    fuji_vfd = VFD('COM3',1,19200,8,'N',2,0.1)

    # setpoint = float(input('Enter Freq Setpoint: '))
    # fuji_vfd.send_setpoint(setpoint)

    # input('Press Enter to Start Motor')
    # fuji_vfd.start_motor()

    try:
        while True:
            fuji_vfd.poll_monitoring()
            print(f"heat sink temp: {fuji_vfd.heat_sink_temp}")
            # fuji_vfd.poll_status()
            # print(f'Status: {fuji_vfd.state_message}')
            # print(f'Setpoint: {fuji_vfd.setpoint}')
            time.sleep(1)
            # jets_s.clear_faults()
            # time.sleep(0.5)
    except KeyboardInterrupt:
        print('Stopping')
        # fuji_vfd.stop_motor()
