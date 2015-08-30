#!/usr/bin/env python

from datetime import datetime
from utils.carberry_utils import scan_serial
from carberry_io import OBDPort
import time
import carberry_sensors


class OBDCapture:
    def __init__(self):
        self.supportedSensorList = []
        self.port = None

    def connect(self):
        portnames = scan_serial()
        print portnames
        for port in portnames:
            self.port = OBDPort(port, None, 2, 2)
            if(self.port.State == 0):
                self.port.close()
                self.port = None
            else:
                break

        if(self.port):
            print "Connected to " + self.port.port.name
            
    def is_connected(self):
        return self.port
        
    def getSupportedSensorList(self):
        return self.supportedSensorList 

    def capture_data(self):

        text = ""
        #Find supported sensors - by getting PIDs from OBD
        # its a string of binary 01010101010101 
        # 1 means the sensor is supported
        self.supp = self.port.sensor(0)[1]
        self.supportedSensorList = []
        self.unsupportedSensorList = []

        # loop through PIDs binary
        for i in range(0, len(self.supp)):
            if self.supp[i] == "1":
                # store index of sensor and sensor object
                self.supportedSensorList.append([i+1, carberry_sensors.SENSORS[i+1]])
            else:
                self.unsupportedSensorList.append([i+1, carberry_sensors.SENSORS[i+1]])
        
        for supportedSensor in self.supportedSensorList:
            text += "supported sensor index = " + str(supportedSensor[0]) + " " + str(supportedSensor[1].shortname) + "\n"
        
        time.sleep(3)
        
        if(self.port is None):
            return None

        #Loop until Ctrl C is pressed        
        localtime = datetime.now()
        current_time = str(localtime.hour)+":"+str(localtime.minute)+":"+str(localtime.second)+"."+str(localtime.microsecond)
        #log_string = current_time + "\n"
        text = current_time + "\n"

        for supportedSensor in self.supportedSensorList:
            sensorIndex = supportedSensor[0]
            (name, value, unit) = self.port.sensor(sensorIndex)
            text += name + " = " + str(value) + " " + str(unit) + "\n"

        return text

if __name__ == "__main__":

    capture = OBDCapture()
    capture.connect()
    time.sleep(3)
    if not capture.is_connected():
        print "Not connected"
    else:
        capture.capture_data()
