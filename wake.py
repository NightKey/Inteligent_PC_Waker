from wakeonlan import send_magic_packet
import re, socket, nmap, threading, time, pickle
from getmac import get_mac_address
from os import path
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import PySimpleGUI as sg
from datetime import datetime, timedelta

loop_run = True

class computers:
    """Stores multiple computer-phone address pairs.
    Can only send a wake package to a given PC, if the phone address is provided, and the PC wasn't waken before, or it were restored.
    """
    def __init__(self):
        self.stored = {}
        self.id = 0x0

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

    def add_new(self, address, phone_address, name, id=None):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        if not self.is_MAC(address):
            return "PC" # TypeError("'address' should be a MAC address")
        if not self.is_MAC(phone_address):
            return "PHONE" # TypeError("'phone_address' should be a MAC address")
        if phone_address in self.stored:
            return "USED" # KeyError("'phone_address' already used for a computer.")
        self.stored[phone_address] = {"pc":address, "was wakened":False, "id":self.id if id is None else id, "name":name, "phone last online":datetime.now()}   #[phone adress] -> [PC_address, is_awaken, ID, name]
        if id is None: self.id += 0x1
        return False

    def get_UI_list(self):
        ret = []
        for item in self.stored.values():
            ret.append(f"{item['name']} - {'MP sent' if item['was wakened'] else 'PM not sent'}")
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
        del self.stored[self.get_by_id(data[2])]
        self.add_new(data[1], data[0], data[3], data[2])
    
    def remove(self, other):
        del self.stored[other]

    def get_by_name(self, name):
        name = name.strip()
        for key, values in self.stored.items():
            if values["name"] == name:
                return key
    
    def get_by_id(self, id):
        for key, value in self.stored.items():
            if value["id"] == id:
                return key

    def iterate(self, data):
        ret = False
        if data == {}: return ret
        for phone, value in self.stored.items():
            PC_Online = value["pc"].upper() in data
            ret = False
            if phone.upper() in data:
                value["phone last online"] = datetime.now()
                if not value["was wakened"] and not PC_Online:
                    ret = True
                    self.wake(phone)
                elif value["was wakened"] and not PC_Online:
                    print(f"{value['name']} PC went offline.")
            elif value["was wakened"] and not PC_Online and datetime.now()-value["phone last online"] >= timedelta(minutes=10):
                self.reset_state(phone)
                ret = True
        return ret
            
    def wake_everyone(self):
        for key in self.stored.keys():
            self.wake(key)

    def wake(self, phone):
        print(f"Waking {self.stored[phone]['name']}")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        self.stored[phone]["was wakened"] = True
    
    def reset_state(self, phone):
        self.stored[phone]["was wakened"] = False
        print(f"{self.stored[phone]['name']} Phone offline")
    
    def is_MAC(self, _input):
        _input.replace("-", ':').replace(".", ':').replace(" ", ':')
        if re.match(r"([a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+)", _input) is None:
            return False
        return True

class data_edit:
    def __init__(self, title, sender=None, pc=None, id=None, name=None):
        layout = [
            [sg.Text("Telefon MAC címe"), sg.In(default_text=(sender if sender is not None else ''), key="SENDER")],
            [sg.Text("PC MAC címe"), sg.In(default_text=(pc if pc is not None else ''), key="PC")],
            [sg.Text("Megjelenítendő név"), sg.In(default_text=(name if name is not None else ''), key="NAME")],
            [sg.Button("Mégsem", key="CANCLE"), sg.Button("Kész", key="FINISHED")]
        ]
        self.window = sg.Window(title, layout)
        self.read = self.window.read
        self.is_running = True
        self.id = id

    def Close(self):
        self.is_running = False
        self.window.Close()

    def work(self, event, values):
        if event == "CANCLE" or event == sg.WIN_CLOSED:
            self.Close()
            return None
        elif event == "FINISHED":
            self.Close()
            return [values["SENDER"], values["PC"], self.id, values["NAME"]]

    def show(self):
        while self.is_running:
            event, values = self.read()
            ret = self.work(event, values)
        return ret

class main_window:
    def __init__(self, pcs, call_back, delete, get_items, ui_wake):
        layout = [
            [sg.Listbox(values=pcs, key="PCS", size=(75,25), enable_events=True)],
            [sg.Button("Új kapcsolat", key="NEW"), sg.Button("Szerkesztés", key="EDIT"), sg.Button("Törlés", key="DELETE"), sg.Button("Ébresztés", key="WAKE")]
        ]
        self.window = sg.Window("IPW", layout, finalize=True)
        self.read = self.window.read
        self.is_running = True
        self.call_back = call_back
        self.delete = delete
        self.get_items = get_items
        self.ui_wake = ui_wake

    def work(self, event, values):
        if event == sg.WINDOW_CLOSED:
            self.Close()
        elif event == "DELETE":
            if values["PCS"] != []:
                self.delete(values["PCS"][0].split("-")[0])
        elif event == "NEW" or event == "EDIT":
            if event == "NEW":
                tmp = data_edit(title="Új adat felvétele")
            else:
                data = self.get_items(values["PCS"][0].split("-")[0])
                print(data)
                tmp = data_edit("Szerkesztés", data[0], data[1][0], data[1][2], data[1][3])
            new_data = tmp.show()
            if new_data is not None:
                self.call_back(event, new_data)
        elif event == "WAKE":
            self.update_UI(self.ui_wake(values["PCS"][0].split("-")[0]))

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
    mc = {}
    while True:
        try:
            ip_s = scanner.scan(hosts=ip, arguments="-sn --max-parallelism 100")
            #scann_end = time.process_time()
            for ip in ip_s["scan"].values():
                if ip["addresses"]["ipv4"] != _ip:
                    mc[ip["addresses"]["mac"]] = ip["addresses"]["ipv4"]
            #finish = time.process_time()
            break
        except Exception as ex:
            print(f"Error happaned {ex}")
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
        time.sleep(0.2)

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
        ret = pcs.add_new(data[1], data[0], data[3], data[2])
    elif _type == "EDIT":
        ret = pcs.changed(data)
    if not ret: window.update_UI(pcs)
    else:
        sg.popup(ret, "Error")
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
        elif "morning" in inp:
            pcs.wake_everyone()
        elif "stop" in inp:
            loop_run = False
            window.Close()
        elif "list" in inp:
            for values in pcs:
                print(values.split(" - ")[0])

def UI_wake(name):
    pcs.wake(pcs.get_by_name(name))
    return pcs

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
window = main_window(pcs, call_back, delete, get_data, UI_wake)
main()