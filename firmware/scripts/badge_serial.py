"""Read the badge's USB serial for N seconds, optionally sending commands first.
usage: badge_serial.py SECONDS [COMMANDS]"""
import glob, os, sys, time
import serial
secs = float(sys.argv[1]); cmds = sys.argv[2] if len(sys.argv) > 2 else ""
ports = []
for _ in range(50):  # wait up to 10 s for the port (it appears a few s after a reset)
    ports = [os.environ["BADGE_PORT"]] if os.environ.get("BADGE_PORT") else sorted(glob.glob("/dev/cu.usbmodem*"))
    if ports:
        break
    time.sleep(0.2)
if not ports:
    sys.exit("no badge serial port found")
port = ports[0]
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
