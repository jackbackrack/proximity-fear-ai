"""Read the badge's USB serial for N seconds, optionally sending commands first.
usage: badge_serial.py SECONDS [COMMANDS]"""
import glob, sys, time
import serial
secs = float(sys.argv[1]); cmds = sys.argv[2] if len(sys.argv) > 2 else ""
port = sorted(glob.glob("/dev/cu.usbmodem*"))[0]
s = serial.Serial(port, 115200, timeout=0.2)
s.dtr = True
end = time.time() + secs; sent = False
while time.time() < end:
    if not sent and cmds:
        time.sleep(0.3)
        for c in cmds:
            s.write(c.encode()); time.sleep(0.2)
        sent = True
    line = s.readline()
    if line:
        print(line.decode(errors="replace").rstrip(), flush=True)
