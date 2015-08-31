 #!/usr/bin/env python


import serial
import carberry_sensors
import string
import time
from carberry_sensors import hex_to_int
from utils.debug_event import debug_display

# Constants

GET_DTC_COMMAND = "03"
CLEAR_DTC_COMMAND = "04"
GET_FREEZE_DTC_COMMAND = "07"


def decrypt_dtc_code(code):
    """Returns the 5-digit DTC code from hex encoding"""
    dtc = []
    current = code
    for i in range(0,3):
        if len(current)<4:
            raise "Tried to decode bad DTC: %s" % code

        # type code
        tc = carberry_sensors.hex_to_int(current[0])
        tc >>= 2

        if tc == 0:
            type = "P"
        elif tc == 1:
            type = "C"
        elif tc == 2:
            type = "B"
        elif tc == 3:
            type = "U"
        else:
            raise tc

        dig1 = str(carberry_sensors.hex_to_int(current[0]) & 3)
        dig2 = str(carberry_sensors.hex_to_int(current[1]))
        dig3 = str(carberry_sensors.hex_to_int(current[2]))
        dig4 = str(carberry_sensors.hex_to_int(current[3]))
        dtc.append(type+dig1+dig2+dig3+dig4)
        current = current[4:]
    return dtc


class CarberryObdPort:
     """ CarberryObdPort abstracts all communication with OBD-II device."""

     def __init__(self, portnum, notify_window, SERTIMEOUT):
         """Initializes port by resetting the device and gettings supported PIDs. """

         baud = 38400
         databits = 8
         parity = serial.PARITY_NONE
         stop_bits = 1
         to = SERTIMEOUT
         self.elm_version = "Unknown"

         #state SERIAL is 1 connected, 0 disconnected (connection failed)
         self.state = 1
         self.port = None
         
         self.notify_window = notify_window
         debug_display(self.notify_window, 1, "Opening interface (serial port)")

         try:
             self.port = serial.Serial(portnum, baud, parity=parity, stopbits=stop_bits, bytesize=databits, timeout=to)
             
         except serial.SerialException as e:
             print e
             self.state = 0
             return None
             
         debug_display(self.notify_window, 1, "Interface " + self.port.portstr + "successfully opened")
         debug_display(self.notify_window, 1, "Connecting to ECU...")
         
         try:
            self.send_command("atz")   # initialize
            time.sleep(1)
         except serial.SerialException:
            self.state = 0
            return None
            
         self.elm_version = self.get_result()
         if(self.elm_version is None):
            self.state = 0
            return None
         
         debug_display(self.notify_window, 2, "atz response:" + self.elm_version)
         self.send_command("ate0")  # echo off
         debug_display(self.notify_window, 2, "ate0 response:" + self.get_result())
         self.send_command("0100")
         ready = self.get_result()
         
         if(ready is None):
            self.state = 0
            return None
            
         debug_display(self.notify_window, 2, "0100 response:" + ready)
         return None
              
     def close(self):
         """ Resets device and closes all associated filehandles"""
         
         if (self.port!= None) and self.state==1:
            self.send_command("atz")
            self.port.close()
         
         self.port = None
         self.elm_version = "Unknown"

     def send_command(self, cmd):
         """Internal use only: not a public interface"""
         if self.port:
             self.port.flushOutput()
             self.port.flushInput()
             for c in cmd:
                 self.port.write(c)
             self.port.write("\r\n")
             #debug_display(self._notify_window, 3, "Send command:" + cmd)

     def interpret_result(self, code):
         """Internal use only: not a public interface"""
         # Code will be the string returned from the device.
         # It should look something like this:
         # '41 11 0 0\r\r'
         
         # 9 seems to be the length of the shortest valid response
         if len(code) < 7:
             #raise Exception("BogusCode")
             print "boguscode?"+code
         
         # get the first thing returned, echo should be off
         code = string.split(code, "\r")
         code = code[0]
         
         #remove whitespace
         code = string.split(code)
         code = string.join(code, "")
         
         # there is no such sensor
         if code[:6] == "NODATA":
             return "NODATA"
             
         # first 4 characters are code from ELM
         code = code[4:]
         return code
    
     def get_result(self):
         """Internal use only: not a public interface"""

         repeat_count = 0
         if self.port is not None:
             buffer = ""
             while True:
                 c = self.port.read(1)
                 if len(c) == 0:
                    if(repeat_count == 5):
                        break
                    print "Got nothing\n"
                    repeat_count = repeat_count + 1
                    continue
                    
                 if c == '\r':
                    continue
                    
                 if c == ">":
                    break;

                 #if something is in the buffer, add it
                 if buffer != "" or c != ">":
                    buffer = buffer + c
                    
             if(buffer == ""):
                return None
             return buffer
         else:
            debug_display(self.notify_window, 3, "NO self.port!")
         return None

     # get sensor value from command
     def get_sensor_value(self, sensor):
         """Internal use only: not a public interface"""
         cmd = sensor.cmd
         self.send_command(cmd)
         data = self.get_result()
         
         if data:
             data = self.interpret_result(data)
             if data != "NODATA":
                 data = sensor.value(data)
         else:
             return "NORESPONSE"
             
         return data

     # return string of sensor name and value from sensor index
     def sensor(self, sensor_index):
         """Returns 3-tuple of given sensors. 3-tuple consists of
         (Sensor Name (string), Sensor Value (string), Sensor Unit (string) ) """
         sensor = carberry_sensors.SENSORS[sensor_index]
         r = self.get_sensor_value(sensor)
         return sensor.name, r, sensor.unit

     def sensor_names(self):
         """Internal use only: not a public interface"""
         names = []
         for s in carberry_sensors.SENSORS:
             names.append(s.name)
         return names

     def get_dtc(self):
          """Returns a list of all pending DTC codes. Each element consists of
          a 2-tuple: (DTC code (string), Code description (string) )"""
          dtcLetters = ["P", "C", "B", "U"]
          r = self.sensor(1)[1] #data
          dtcNumber = r[0]
          mil = r[1]
          DTCCodes = []

          print "Number of stored DTC:" + str(dtcNumber) + " MIL: " + str(mil)
          # get all DTC, 3 per mesg response
          for i in range(0, ((dtcNumber+2)/3)):
            self.send_command(GET_DTC_COMMAND)
            res = self.get_result()
            print "DTC result:" + res
            for i in range(0, 3):
                val1 = hex_to_int(res[3+i*6:5+i*6])
                val2 = hex_to_int(res[6+i*6:8+i*6]) #get DTC codes from response (3 DTC each 2 bytes)
                val  = (val1<<8)+val2 #DTC val as int
                
                if val==0: #skip fill of last packet
                  break
                   
                DTCStr=dtcLetters[(val&0xC000)>14]+str((val&0x3000)>>12)+str((val&0x0f00)>>8)+str((val&0x00f0)>>4)+str(val&0x000f)
                
                DTCCodes.append(["Active",DTCStr])
          
          #read mode 7
          self.send_command(GET_FREEZE_DTC_COMMAND)
          res = self.get_result()
          
          if res[:7] == "NODATA": #no freeze frame
            return DTCCodes
          
          print "DTC freeze result:" + res
          for i in range(0, 3):
              val1 = hex_to_int(res[3+i*6:5+i*6])
              val2 = hex_to_int(res[6+i*6:8+i*6]) #get DTC codes from response (3 DTC each 2 bytes)
              val  = (val1<<8)+val2 #DTC val as int
                
              if val==0: #skip fill of last packet
                break
                   
              DTCStr=dtcLetters[(val&0xC000)>14]+str((val&0x3000)>>12)+str((val&0x0f00)>>8)+str((val&0x00f0)>>4)+str(val&0x000f)
              DTCCodes.append(["Passive",DTCStr])
              
          return DTCCodes
              
     def clear_dtc(self):
         """Clears all DTCs and freeze frame data"""
         self.send_command(CLEAR_DTC_COMMAND)     
         r = self.get_result()
         return r
     
     def log(self, sensor_index, filename): 
          file = open(filename, "w")
          start_time = time.time() 
          if file:
               data = self.sensor(sensor_index)
               file.write("%s     \t%s(%s)\n" % \
                         ("Time", string.strip(data[0]), data[2])) 
               while 1:
                    now = time.time()
                    data = self.sensor(sensor_index)
                    line = "%.6f,\t%s\n" % (now - start_time, data[1])
                    file.write(line)
                    file.flush()