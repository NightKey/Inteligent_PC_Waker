from wakeonlan import send_magic_packet
import re, socket, nmap, threading, time, pickle
from getmac import get_mac_address
from os import path
import platform    # For getting the operating system name
import subprocess  # For executing a shell command

loop_run = True
class computers:
    """Stores multiple computer-phone address pairs.
Can only send a wake package to a given PC, if the phone address is provided, and the PC wasn't waken before, or it were restored.
    """
    def __init__(self):
        self.stored = {}

    def ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """
        # Option for the number of packets as a function of
        param = '-n' if platform.system().lower()=='windows' else '-c'
        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, '1', host]
        return subprocess.call(command) == 0

    def add_new(self, address, phone_address):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        if not self.is_MAC(address):
            raise TypeError("'address' should be a MAC address")
        if not self.is_MAC(phone_address):
            raise TypeError("'phone_address' should be a MAC address")
        if phone_address in self.stored:
            raise KeyError("'phone_address' already used for a computer.")
        self.stored[phone_address] = [address, False]   #[phone adress] -> [PC_address, is_awaken]

    def __getitem__(self, key):
        if key in self.stored:
            return self.stored[key][1]
        else:
            return None

    def change_phone(self, old_phone, new_phone):
        if not self.is_MAC(new_phone):
            raise TypeError("'new_phone' should be a MAC address")
        tmp = self.stored.pop(old_phone)
        self.stored[new_phone] = tmp
    
    def change_address(self, phone, address):
        if not self.is_MAC(address):
            raise TypeError("'address' should be a MAC address")
        self.stored[phone][0] = address

    def iterate(self, data):
        for key, value in self.stored.items():
            ping_ = self.ping(data[value[0].upper()])
            if key.lower() in data:
                if not value[1] and not ping_:
                    print(f"Waking pc {value[0]}")
                    self.wake(key)
            elif value[1] and not ping_:
                self.reset_state(key)
            
    def wake(self, key):
        if not self.stored[key][1]:
            send_magic_packet(self.stored[key][0])
            self.stored[key][1] = True
    
    def reset_state(self, key):
        self.stored[key][1] = False
    
    def is_MAC(self, _input):
        if re.match(r"([a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+)", _input) is None:
            return False
        return True

def scann(_ip):
    ip = _ip.split(".")
    ip[-1] = "2-254"
    ip = '.'.join(ip)
    #start = time.process_time()
    scanner = nmap.PortScanner()
    ip_s = scanner.scan(hosts=ip, arguments="-sn")
    #scann_end = time.process_time()
    mc = {}
    for ip in ip_s["scan"].values():
        if ip["addresses"]["ipv4"] != _ip:
            mc[ip["addresses"]["mac"]] = ip["addresses"]["ipv4"]
    #finish = time.process_time()
    return mc

def loop():
    global ip
    counter = 0
    while loop_run:
        pcs.iterate(scann(ip))
        if counter == 200:
            get_ip()
            counter = 0
        counter += 1
        time.sleep(20)

def main():
    global loop_run
    while loop_run:
        print(f"There is currently {len(pcs.stored)} pc added")
        ansv = input("Do you want to add a new PC? (For exit type in 'exit')")
        if ansv.lower() == "y":
            phone = input("Type in your PHONE's MAC adress (xx:xx:xx:xx:xx:xx): ")
            PC = input("Type in your PC's MAC adress (xx:xx:xx:xx:xx:xx): ")
            try:
                pcs.add_new(PC, phone)
            except Exception as ex:
                print(f"{type(ex)} --> {ex}")
        elif ansv.lower() == "exit":
            loop_run = False
        with open("pcs", "bw") as f:
            pickle.dump(pcs, f)

def get_ip():
    global ip
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()

def add_new_pc(address, phone):
    pcs.add_new(address, phone)

ip = None
get_ip()
if path.exists("pcs"):
    with open("pcs", 'br') as f:
        pcs = pickle.load(f)
else:
    pcs = computers()
check_loop = threading.Thread(target=loop)
check_loop.name = "Wake check loop"
check_loop.start()
main()