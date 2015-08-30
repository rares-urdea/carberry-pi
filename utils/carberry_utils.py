import serial


def scan_serial():
    """Scans for available ports. returns a list of serial names"""
    available_ports = []

    # Find available Bluetooth connection
    for i in range(256):
        try:
            s = serial.Serial("/dev/rfcomm"+str(i))
            available_ports.append((str(s.port)))
            s.close()   # explicit close 'cause of delayed GC in java
        except serial.SerialException:
            pass

    # On standard debian / ubuntu, the serial connection is /dev/ttyS<N> where 0 < N < 255
    for i in range(256):
        try:
            s = serial.Serial("/dev/ttyS"+str(i))
            available_ports.append(s.portstr)
            s.close()   # explicit close 'cause of delayed GC in java
        except serial.SerialException:
            pass

    # On raspbian it seems to be /dev/ttyUSB<N> instead
    for i in range(256):
        try:
            s = serial.Serial("/dev/ttyUSB"+str(i))
            available_ports.append(s.portstr)
            s.close()   # explicit close 'cause of delayed GC in java
        except serial.SerialException:
            pass
    
    return available_ports
