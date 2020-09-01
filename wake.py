from wakeonlan import send_magic_packet
import re, socket, nmap, threading, time, pickle
from getmac import get_mac_address
from os import path
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import PySimpleGUI as sg

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

    def add_new(self, address, phone_address, name):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        if not self.is_MAC(address):
            return False # TypeError("'address' should be a MAC address")
        if not self.is_MAC(phone_address):
            return False # TypeError("'phone_address' should be a MAC address")
        if phone_address in self.stored:
            return False # KeyError("'phone_address' already used for a computer.")
        self.stored[phone_address] = [address, False, name]   #[phone adress] -> [PC_address, is_awaken]

    def get_UI_list(self):
        ret = []
        for item in self.stored.values():
            ret.append(f"{item[2]} - {'MP sent' if item[1] else 'PM not sent'}")
        return ret

    def __len__(self):
        return len(self.stored)

    def __getitem__(self, key):
        if isinstance(key, int):
            if key < len(self.stored):
                return self.get_UI_list()[key]
            else: raise StopIteration()
        if key in self.stored:
            return self.stored[key]
        else:
            return None

    def changed(self, data):
        if data[0] in self.stored:
            self.change_address(data[0], data[1])
            self.stored[data[0]][2] = data[2]
        elif self.get_by_name(data[2]) is not None:
            self.change_phone(self.get_by_name(data[2]), data[0])
            self.stored[data[0]][2] = data[2]

    def change_phone(self, old_phone, new_phone):
        if not self.is_MAC(new_phone):
            raise TypeError("'new_phone' should be a MAC address")
        tmp = self.stored.pop(old_phone)
        self.stored[new_phone] = tmp
    
    def remove(self, other):
        del self.stored[other]

    def change_address(self, phone, address):
        if not self.is_MAC(address):
            raise TypeError("'address' should be a MAC address")
        self.stored[phone][0] = address

    def get_by_name(self, name):
        name = name.strip()
        for key, values in self.stored.items():
            if values[2] == name:
                return key

    def iterate(self, data):
        ret = False
        for key, value in self.stored.items():
            try:
                data[value[0].upper()]
                Is_Online = True
            except: Is_Online = False
            ret = False
            if key.upper() in data:
                if not value[1] and not Is_Online:
                    ret = True
                    self.wake(key)
            elif value[1] and not Is_Online:
                self.reset_state(key)
                ret = True
        return ret
            
    def wake(self, key):
        print(f"\nWaking {self.stored[key][-1]}")
        send_magic_packet(self.stored[key][0], ip_address="192.168.0.255")
        send_magic_packet(self.stored[key][0], ip_address="192.168.0.255")
        send_magic_packet(self.stored[key][0], ip_address="192.168.0.255")
        send_magic_packet(self.stored[key][0], ip_address="192.168.0.255")
        self.stored[key][1] = True
    
    def reset_state(self, key):
        self.stored[key][1] = False
    
    def is_MAC(self, _input):
        if re.match(r"([a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+)", _input) is None:
            return False
        return True

class data_edit:
    def __init__(self, title, sender=None, pc=None, name=None):
        layout = [
            [sg.Text("Telefon MAC címe"), sg.In(default_text=(sender if sender is not None else ''), key="SENDER")],
            [sg.Text("PC MAC címe"), sg.In(default_text=(pc if pc is not None else ''), key="PC")],
            [sg.Text("Megjelenítendő név"), sg.In(default_text=(name if name is not None else ''), key="NAME")],
            [sg.Button("Mégsem", key="CANCLE"), sg.Button("Kész", key="FINISHED")]
        ]
        self.window = sg.Window(title, layout)
        self.read = self.window.read
        self.is_running = True

    def Close(self):
        self.is_running = False
        self.window.Close()

    def work(self, event, values):
        if event == "CANCLE" or event == sg.WIN_CLOSED:
            self.Close()
            return None
        elif event == "FINISHED":
            self.Close()
            return [values["SENDER"], values["PC"], values["NAME"]]

    def show(self):
        while self.is_running:
            event, values = self.read()
            ret = self.work(event, values)
        return ret

class main_window:
    def __init__(self, pcs, call_back, delete, get_items):
        layout = [
            [sg.Listbox(values=pcs, key="PCS", size=(75,25), enable_events=True)],
            [sg.Button("Új kapcsolat", key="NEW"), sg.Button("Törlés", key="DELETE")]
        ]
        self.window = sg.Window("IPW", layout, finalize=True)
        self.read = self.window.read
        self.is_running = True
        self.call_back = call_back
        self.delete = delete
        self.get_items = get_items

    def work(self, event, values):
        if event == sg.WINDOW_CLOSED:
            self.Close()
        elif event == "DELETE":
            if values["PCS"] != []:
                self.delete(values["PCS"][0].split("-")[0])
        elif event == "NEW" or event == "PCS":
            if event == "NEW":
                tmp = data_edit(title="Új adat felvétele")
            else:
                data = self.get_items(values["PCS"][0].split("-")[0])
                print(data)
                tmp = data_edit("Szerkesztés", data[0], data[1][0], data[1][2])
            new_data = tmp.show()
            if new_data is not None:
                self.call_back(event, new_data)

    def update_UI(self, pcs):
        self.window["PCS"].Update(pcs)

    def show(self):
        while self.is_running:
            event, values = self.read()
            self.work(event, values)

    def Close(self):
        self.window.Close()
        self.is_running = False


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

def get_data(name):
    key = pcs.get_by_name(name)
    return [key, pcs[key]]

def loop():
    global ip
    counter = 0
    while loop_run:
        if pcs.iterate(scann(ip)):
            window.update_UI(pcs)
        if counter == 200:
            get_ip()
            counter = 0
        counter += 1
        time.sleep(20)

def main():
    global loop_run
    global window
    window.show()
    loop_run = False

def save():
    with open("pcs", 'bw') as f:
        pickle.dump(pcs, f)

def get_ip():
    global ip
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()

def add_new_pc(address, phone):
    pcs.add_new(address, phone)

def call_back(_type, data):
    global pcs
    if _type == "NEW":
        pcs.add_new(data[1], data[0], data[2])
    elif _type == "PCS":
        pcs.changed(data)
    window.update_UI(pcs)
    save()

def delete(name):
    pcs.remove(pcs.get_by_name(name))
    window.update_UI(pcs)

def console():
    global loop_run
    while loop_run:
        inp = input(':')
        if "wake" in inp:
            name = inp.split(" ")[-1]
            pcs.wake(pcs.get_by_name(name))
        elif "stop" in inp:
            loop_run = False
            window.Close()

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
terminal = threading.Thread(target=console)
terminal.name = "Terminal"
terminal.start()
window = main_window(pcs, call_back, delete, get_data)
main()