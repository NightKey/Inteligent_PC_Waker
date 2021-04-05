import subprocess
from platform import system
import re
import time
import os

mac_filter = r"([a-fA-F0-9]{2}[:-]){5}([a-fA-F0-9]{2})"
ip_filter = r"([0-9]{1,3}[.]){3}([0-9]){1,3}"
system_specific_switches = ["-n", "-a"] if system() == "Windows" else ["-c", ""]

def pre_check(ip_range):
    devnull = open(os.devnull, "wb")
    for ip in ip_range:
        subprocess.Popen(["ping",  system_specific_switches[0], "1", ip], stdout=devnull)
    devnull.close()

def arp_scan():
    reply = subprocess.check_output(["arp", system_specific_switches[1]])
    reply = [[item for item in line.replace("\r", "").strip().split(' ') if re.match(mac_filter, item) or re.match(ip_filter, item)] for line in reply.decode("utf-8").split("\n") if re.search(mac_filter, line)]
    return reply