from wakeonlan import send_magic_packet
import re, socket, nmap, threading, time, pickle, json, smdb_api, random
from getmac import get_mac_address
from os import path, devnull
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import PySimpleGUI as sg
from datetime import datetime, timedelta
from hashlib import sha256

loop_run = True

class computers:
    """Stores multiple computer-phone address pairs.
    Can only send a wake package to a given PC, if the phone address is provided, and the PC wasn't waken before, or it were restored.
    """
    def __init__(self, send = None):
        self.stored = {}
        self.id = 0x0
        self.window = None
        self.send = send

    def set_window(self, window):
        self.window = window

    def ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """
        # Option for the number of packets as a function of
        param = '-n' if platform.system().lower()=='windows' else '-c'
        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, '1', host]
        with open(devnull, 'a') as dnull:
            tmp = subprocess.call(command, stdout=dnull) == 0
        return tmp

    def add_new(self, address, phone_address, name, dc=None, id=None):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        if not self.is_MAC(address):
            return "PC" # TypeError("'address' should be a MAC address")
        if not self.is_MAC(phone_address):
            return "PHONE" # TypeError("'phone_address' should be a MAC address")
        if phone_address in self.stored:
            return "USED" # KeyError("'phone_address' already used for a computer.")
        self.stored[phone_address] = {"pc":address, 'is_online':False, "was wakened":False, "id":self.id if id is None else id, "name":name, "phone last online":None, "was_online":False, "wake time":None, 'alert on discord':dc, 'pc_ip':None}
        if id is None: self.id += 0x1
        return False

    def get_UI_list(self):
        """Returns a list for the UI containing the following format:
        name - offline/WOL sent
        """
        ret = []
        for item in self.stored.values():
            ret.append(f"{item['name']} - {'WOL sent' if item['was wakened'] and (not item['was_online'] or (item['wake time'] is not None and datetime.now() - item['wake time'] < timedelta(minutes=2))) else 'Online' if item['is_online'] else 'Offline'}")
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

    def iterate(self, resoults):
        if resoults == {}: return
        for phone, data in self.stored.items():
            PC_Online = (data["pc"].upper() in resoults and self.ping(resoults[data["pc"].upper()]))
            self.stored[phone]["is_online"] = PC_Online
            if PC_Online and not self.stored[phone]['was_online']:
                self.window()
                self.stored[phone]['was_online'] = True
            if PC_Online and self.stored[phone]['pc_ip'] is None:
                self.stored[phone]["pc_ip"] = resoults[self.stored[phone]['pc']]
            elif not PC_Online:
                self.stored[phone]["pc_ip"] = None
            if phone.upper() in resoults:
                data["phone last online"] = datetime.now()
                if not data["was wakened"] and not PC_Online:
                    self.wake(phone)
                    self.window()
                elif data["was wakened"] and not PC_Online and data['was_online']:
                    print(f"{data['name']} PC went offline.")
                    self.window()
                    self.stored[phone]['was_online'] = False
            elif data["was wakened"] and (data["phone last online"] is None or datetime.now()-data["phone last online"] > timedelta(minutes=5)):
                self.reset_state(phone)
                self.window()
                if PC_Online and data["wake time"] is not None and datetime.now()-data["wake time"] <= timedelta(minutes=6): shutdown_pc(phone)
            
    def wake_everyone(self):
        for key in self.stored.keys():
            self.wake(key)

    def get_random_welcome(self):
        with open("welcomes.txt", 'r') as f:
            data = f.read(-1).split('\n')
        return random.choice(data)

    def wake(self, phone):
        print(f"Waking {self.stored[phone]['name']}")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        send_magic_packet(self.stored[phone]["pc"], ip_address="192.168.0.255")
        self.stored[phone]["was wakened"] = True
        self.stored[phone]["wake time"] = datetime.now()
        if self.send is not None:
            self.send(self.get_random_welcome(), user=self.stored[phone]["alert on discord"])
    
    def reset_state(self, phone):
        self.stored[phone]["was wakened"] = False
        print(f"{self.stored[phone]['name']} Phone offline")
    
    def save_to_json(self):
        out = [{'phone':phone, 'pc':values['pc'], 'name':values['name'], "dc":values["alert on discord"]} for phone, values in self.stored.items()]
        with open('export.json', 'w', encoding='utf-8') as f:
            json.dump(out, f)

    def import_from_json(self):
        with open("export.json", 'r', encoding='utf-8') as f:
            tmp = json.load(f)
        for item in tmp:
            self.add_new(item["pc"], item['phone'], item['name'], (item['dc'] if 'dc' in item else None))

    def is_MAC(self, _input):
        _input.replace("-", ':').replace(".", ':').replace(" ", ':')
        if re.match(r"([a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+:[a-fA-F0-9]+)", _input) is None:
            return False
        return True

class data_edit:
    def __init__(self, title, sender=None, pc=None, id=None, name=None, dc=None):
        """For editing the data
        """
        layout = [
            [sg.Text("Telefon MAC címe"), sg.In(default_text=(sender if sender is not None else ''), key="SENDER")],
            [sg.Text("PC MAC címe"), sg.In(default_text=(pc if pc is not None else ''), key="PC")],
            [sg.Text("Megjelenítendő név"), sg.In(default_text=(name if name is not None else ''), key="NAME")],
            [sg.Text("Discord név", tooltip="Csak, ha a server monitoring discord bot elérhető, és az API jelen van"), sg.In(default_text=(dc if dc is not None else ''), key="DC", tooltip="Csak, ha a server monitoring discord bot elérhető, és az API jelen van")],
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
            return [values["SENDER"], values["PC"], self.id, values["NAME"], values['DC']]

    def show(self):
        while self.is_running:
            event, values = self.read()
            ret = self.work(event, values)
        return ret

class main_window:
    def __init__(self, pcs, call_back, delete, get_items, ui_wake, shutdown_pc):
        sg.theme("dark")
        layout = [
            [sg.Listbox(values=pcs, key="PCS", size=(75,25), enable_events=True)],
            [sg.Button("Új kapcsolat", key="NEW"), sg.Button("Szerkesztés", key="EDIT"), sg.Button("Törlés", key="DELETE"), sg.Combo(['ÉBRESZTÉS', 'KIKAPCSOLÁS', 'ALTATÁS'], key="SELECTION", size=(20,1)), sg.Button("Csináld", key="RUN")]
        ]
        self.window = sg.Window("IPW", layout, finalize=True)
        self.read = self.window.read
        self.is_running = True
        self.call_back = call_back
        self.delete = delete
        self.get_items = get_items
        self.ui_wake = ui_wake
        self.shutdown_pc = shutdown_pc
        self.selected = None

    def work(self, event, values):
        if event == sg.WINDOW_CLOSED:
            self.Close()
        elif event == "PCS":
            self.selected = values["PCS"][0].split('-')[0]
            print(f"Selected: {self.get_items(self.selected)}")
        elif event == "DELETE":
            if self.selected is not None:
                self.delete(self.selected)
                self.selected = None
        elif event == "NEW" or event == "EDIT":
            if event == "NEW":
                tmp = data_edit(title="Új adat felvétele")
            else:
                if self.selected is not None:
                    data = self.get_items(self.selected)
                    tmp = data_edit("Szerkesztés", data[0], data[1]["pc"], data[1]["id"], data[1]["name"], data[1]["alert on discord"])
                    self.selected = None
            new_data = tmp.show()
            if new_data is not None:
                self.call_back(event, new_data)
        elif event == "RUN":
            if self.selected is not None:
                if values['SELECTION'] == "ÉBRESZTÉS":
                    self.update_UI(self.ui_wake(self.selected))
                elif values['SELECTION'] == "KIKAPCSOLÁS":
                    self.shutdown_pc(self.selected)
                elif values['SELECTION'] == "ALTATÁS":
                    self.shutdown_pc(self.selected, True)


    def update_UI(self, pcs):
        self.window["PCS"].Update(pcs)

    def show(self):
        while self.is_running:
            event, values = self.read()
            self.work(event, values)

    def Close(self):
        self.window.Close()
        self.is_running = False

def shutdown_pc(phone, sleep=False):
    try: 
        if phone not in pcs: phone = pcs.get_by_name(phone)
        IP = pcs[phone]['pc_ip']
        if IP is None: return
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.connect((IP, 666))
        command="SHUTDOWN" if not sleep else "SLEEP"
        send(_socket, sha256(f"{command}{globals()['pcs'][phone]['pc'].lower()}".encode("utf-8")).hexdigest())
    except Exception as ex: print(ex)

def scann(_ip):
    ip = _ip.split(".")
    ip[-1] = "2-24"
    ip = '.'.join(ip)
    start = time.process_time()
    scanner = nmap.PortScanner()
    mc = {}
    while True:
        try:
            ip_s = scanner.scan(hosts=ip, arguments="-sn --max-parallelism 100")
            #scann_end = time.process_time()
            for ip in ip_s["scan"].values():
                if ip["addresses"]["ipv4"] != _ip:
                    mc[ip["addresses"]["mac"]] = ip["addresses"]["ipv4"]
            finish = time.process_time()
            break
        except Exception as ex:
            print(f"Error happaned {ex}")
    return [mc, start, finish]

def send(socket, msg):
    msg = json.dumps(msg)
    while True:
        tmp = ''
        if len(msg) > 9:
            tmp = msg[9:]
            msg = msg[:9]
        socket.send(str(len(msg)).encode(encoding='utf-8'))
        socket.send(msg.encode(encoding="utf-8"))
        if tmp == '': tmp = '\n'
        if msg == '\n': break
        msg = tmp

def get_data(name):
    key = pcs.get_by_name(name)
    return [key, pcs[key]]

def avg(inp):
    return sum(inp)/len(inp)

def loop():
    global ip
    counter = 0
    _avg = []
    while loop_run:
        ret = scann(ip)
        pcs.iterate(ret[0])
        _avg.append(ret[2]-ret[1])
        if counter == 200:
            get_ip()
            counter = -1
            print(f'Average scann time: {avg(_avg)}')
            _avg = []
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
    #data = [values["SENDER"], values["PC"], self.id, values["NAME"], values['DC']]
    global pcs
    if _type == "NEW":
        ret = pcs.add_new(data[1], data[0], data[3], data[4], data[2])
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
            window.update_UI(pcs)
        elif "morning" in inp:
            pcs.wake_everyone()
        elif "stop" in inp:
            loop_run = False
            pcs.save_to_json()
            save()
            window.Close()
        elif "shutdown" in inp:
            name = inp.split(" ")[-1]
            shutdown_pc(pcs.get_by_name(name))
        elif "sleep" in inp:
            name = inp.split(" ")[-1]
            shutdown_pc(pcs.get_by_name(name), True)
        elif "list" in inp:
            for values in pcs:
                print(values.split(" - ")[0])

def UI_wake(name):
    pcs.wake(pcs.get_by_name(name))
    return pcs

def ui_update():
    window.update_UI(pcs)

def api_send(msg, user=None):
    _api.send_message(msg, user)

_api = smdb_api.API("Waker", "ef6a9df062560ce93e1236bce9dc244a6223f1f68ba3dd6a6350123c7719e78c")
_api.validate()
_api.create_function("wake", "Wakes up the connected PC's\nUsage: &wake <Added PC Name>\nCategory: NETWORK", UI_wake, True)
ip = None
get_ip()
if path.exists("pcs"):
    with open("pcs", 'br') as f:
        pcs = pickle.load(f)
else:
    pcs = computers(api_send)
    if path.exists('export.json'):
        pcs.import_from_json()
        save()
window = main_window(pcs, call_back, delete, get_data, UI_wake, shutdown_pc)
pcs.set_window(ui_update)
check_loop = threading.Thread(target=loop)
check_loop.name = "Wake check loop"
check_loop.start()
terminal = threading.Thread(target=console)
terminal.name = "Terminal"
terminal.start()
main()