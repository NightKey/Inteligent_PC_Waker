from wakeonlan import send_magic_packet
import re, socket, nmap, threading, time, pickle, json, random
from getmac import get_mac_address
import smdb_api as API
from os import path, devnull
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import PySimpleGUI as sg
from datetime import datetime, timedelta
from hashlib import sha256

loop_run = True
SMALL = 0
PARTIAL = 1
FULL = 2

class computers:
    """Stores multiple computer-phone address pairs.
    Can only send a wake package to a given PC, if the phone address is provided, and the PC wasn't waken before, or it were restored.
    """
    def __init__(self, send = None):
        self.stored = {}
        self.id = 0x0
        self.window = None
        self.send = send
        self.functions = [
            "stored",
            "id",
            "window",
            "send",
            "functions",
            "set_window",
            "ping",
            "add_new",
            "self_test",
            "get_UI_list",
            "__len__",
            "__getitem__",
            "changed",
            "remove",
            "get_by_name",
            "get_by_id",
            "iterate",
            "wake_everyone",
            "get_random_welcome",
            "wake",
            "reset_state",
            "save_to_json",
            "import_from_json",
            "is_MAC",
            "data_keys",
            "is_time"]
        self.data_keys = [
            "pc",
            "is online",
            "was wakened",
            "id",
            "name",
            "phone last online",
            "was online",
            "wake time",
            "alert on discord",
            "pc ip",
            "turn off sent",
            "manually turned off",
            "is time"]

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

    def add_new(self, address, key, name, dc=None, id=None):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        if not self.is_MAC(address):
            return "PC" # TypeError("'address' should be a MAC address")
        if not self.is_MAC(key) or self.is_time(key):
            return "KEY" # TypeError("'KEY' should be a MAC address or time intervall (0:00-12:00)")
        if key in self.stored:
            return "USED" # KeyError("'KEY' already used for a computer.")
        self.stored[key] = {"pc":address, 'is online':False, "was wakened":False, "id":self.id if id is None else id, "name":name, "phone last online":None, "was online":False, "wake time":None, 'alert on discord':dc, 'pc ip':None, 'turn off sent':None, "manually turned off":False, "is time":self.is_time(key)}
        if id is None: self.id += 0x1
        return False

    def self_test(self):
        for line in self.functions:
            _ = getattr(self, line)
        for _, data in self.stored:
            for line in self.data_keys:
                _ = data[line]

    def get_UI_list(self):
        """Returns a list for the UI containing the following format:
        name - offline/WOL sent
        """
        ret = []
        for item in self.stored.values():
            ret.append(f"{item['name']} - {'WOL sent' if item['was wakened'] and (not item['was online'] or (item['wake time'] is not None and datetime.now() - item['wake time'] < timedelta(minutes=2))) else 'Online' if item['is online'] else 'Offline'}")
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
        self.add_new(address=data[1], key=data[0], name=data[3], dc=data[4], id=data[2])
    
    def remove(self, other):
        del self.stored[other]

    def get_by_name(self, name):
        name = name.strip()
        print(f"Searching for {name}")
        for key, values in self.stored.items():
            if values["name"] == name or values["alert on discord"] == name:
                return key
    
    def get_by_id(self, id):
        for key, value in self.stored.items():
            if value["id"] == id:
                return key

    def iterate(self, resoults):
        if resoults == {}: return
        for phone, data in self.stored.items():
            PC_Online = (data["pc"].upper() in resoults and self.ping(resoults[data["pc"].upper()]))
            self.stored[phone]["is online"] = PC_Online
            if PC_Online and not self.stored[phone]['was online']:
                self.stored[phone]['was online'] = True
            if PC_Online and self.stored[phone]['pc ip'] is None:
                self.stored[phone]["pc ip"] = resoults[self.stored[phone]['pc']]
            elif not PC_Online:
                self.stored[phone]["pc ip"] = None
            if data["is time"]:
                try:
                    tmp = phone.split("-")
                except:
                    tmp = [phone, None]
                now = datetime.now().strftime("%H:%M")
                if tmp[0] == now:
                    self.wake(phone)
                elif tmp[1] == now:
                    shutdown_pc(phone)
                    self.reset_state(phone, FULL)
                continue
            if phone.upper() in resoults:
                data["phone last online"] = datetime.now()
                if not data["was wakened"] and not data['manually turned off']:
                    if PC_Online:
                        data["was wakened"] = True
                        data["wake time"] = datetime.now()
                    else:
                        self.wake(phone)
                elif data["was wakened"] and not PC_Online and data['was online']:
                    self.reset_state(phone, PARTIAL)
            elif data["was wakened"] and (data["phone last online"] is None or datetime.now()-data["phone last online"] > timedelta(minutes=5)):
                self.reset_state(phone, SMALL)
                if PC_Online and data["wake time"] is not None and datetime.now()-data["wake time"] <= timedelta(minutes=7): shutdown_pc(phone)
            elif data["phone last online"] is not None and datetime.now()-data["phone last online"] >= timedelta(hours=2):
                if data['pc ip'] is not None and (data['turn off sent'] is None or datetime.now()-data['turn off sent'] > timedelta(minutes=1)):
                    shutdown_pc(phone)
                    self.stored[phone]['turn off sent'] = datetime.now()
                self.reset_state(phone, FULL)
        else:
            self.window()
            
    def wake_everyone(self):
        for key in self.stored.keys():
            self.wake(key)

    def get_random_welcome(self):
        with open("welcomes.txt", 'r', encoding="utf-8") as f:
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
    
    def reset_state(self, phone, size):
        if size is SMALL:
            self.stored[phone]["was wakened"] = False
            print(f"{self.stored[phone]['name']} Phone offline")
        elif size is PARTIAL:
            self.stored[phone]['was online'] = False
            self.stored[phone]['manually turned off'] = True
            print(f"{self.stored[phone]['name']} PC went offline.")
        elif size is FULL:
            self.stored[phone]["phone last online"] = None
            self.stored[phone]['manually turned off'] = False
            print(f"{self.stored[phone]['name']} state reseted")
    
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
        if re.match(r"([a-fA-F0-9]{2}:[a-fA-F0-9]{2}:[a-fA-F0-9]{2}:[a-fA-F0-9]{2}:[a-fA-F0-9]{2}:[a-fA-F0-9]{2})", _input) is None:
            return False
        return True
    
    def is_time(self, _input):
        if re.match(r"^((([0-1]{0,1}\d)|(2[0-3])):([0-5]\d)-(([0-1]{0,1}\d)|(2[0-3])):([0-5]\d)){1}", _input) is None and re.match(r"^((([0-1]{0,1}\d)|(2[0-3])):([0-5]\d)){1}", _input) is None:
            return False
        return True

class data_edit:
    def __init__(self, title, sender=None, pc=None, id=None, name=None, dc=None):
        """For editing the data
        """
        layout = [
            [sg.Text("Telefon MAC címe vagy időpont/intervallum"), sg.In(default_text=(sender if sender is not None else ''), key="SENDER")],
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
            [sg.Button("Új kapcsolat", key="NEW"), sg.Button("Szerkesztés", key="EDIT"), sg.Button("Törlés", key="DELETE"), sg.Combo(['ÉBRESZTÉS', 'KIKAPCSOLÁS', 'ALTATÁS', "ÚJRAINDÍTÁS"], default_value="ÉBRESZTÉS", key="SELECTION", size=(20,1)), sg.Button("Csináld", key="RUN")]
        ]
        self.window = sg.Window("IPW", layout, finalize=True)
        self.read = self.window.read
        self.is_running = True
        self.call_back = call_back
        self.pcs = pcs
        self.delete = delete
        self.get_items = get_items
        self.ui_wake = ui_wake
        self.shutdown_pc = shutdown_pc
        self.selected = None
        self.request_update = False

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
                    self.shutdown_pc(self.selected, _command=SLEEP)
                elif values['SELECTION'] == "ÚJRAINDÍTÁS":
                    self.shutdown_pc(self.selected, _command=RESTART)
        elif event == "__TIMEOUT__":
            if self.request_update:
                self.window["PCS"].Update(self.pcs)
                self.request_update = False


    def update_UI(self, pcs):
        self.pcs = pcs
        self.request_update = True

    def show(self):
        while self.is_running:
            event, values = self.read()
            self.work(event, values)

    def Close(self):
        self.window.Close()
        self.is_running = False

class console:
    def __init__(self, call_back):
        layout = [
            [sg.Listbox(values=[], key="SCREEN", size=(105,25))],
            [sg.In(key="INPUT", size=(85, 1)), sg.Button("Send", key="SEND", size=(15,1))]
        ]
        self.window = sg.Window("Console", layout, return_keyboard_events=True)
        self.read = self.window.read
        self.is_running = True
        self.shown = []
        self.commands = []
        self.call_back = call_back
        self.pointer = 0
    
    def close(self):
        self.is_running = False
        self.window.Close()

    def print(self, text):
        self.shown.append(f"[{datetime.now()}]: {text}")
        self.pointer = len(self.commands)
    
    def move_pointer(self, up=True):
        if self.pointer > 0 and up:
            self.pointer -= 1
        elif self.pointer < len(self.commands) and not up:
            self.pointer += 1
    
    def work(self, event, values):
        if event == sg.WINDOW_CLOSED:
            self.close()
        elif event == "SEND" or event == r"\r":
            self.print(values["INPUT"])
            self.commands.append(values["INPUT"])
            self.call_back(values["INPUT"])
            self.window["INPUT"].Update("")
        elif event == "Up:38":
            self.move_pointer()
            self.window["INPUT"].Update(self.commands[self.pointer])
        elif event == "Down:40":
            self.move_pointer(False)
            self.window["INPUT"].Update(self.commands[self.pointer])
        elif event == "__TIMEOUT__":
            self.window["SCREEN"].Update(self.shown)
    
    def show(self):
        while self.is_running:
            self.work(*self.read())

def retrive_confirmation(socket, name, delay):
    socket.settimeout(35 if not isinstance(delay, int) else int(delay)+5)
    ansv = ""
    try:
        r = socket.recv(1).decode("utf-8")
        print(f"Message retrived from {name}")
        if r:
            ansv = "PC executed the command"
        elif r is None:
            ansv = "socked timed out"
        else:
            ansv = "PC interrupted the command"
    except: 
        ansv = "Socket error!"
        print(f"Socket Exception! {name}")
    finally:
        print(f"{name} {ansv}")
        api_send(ansv, user=pcs[pcs.get_by_name(name)]["alert on discord"])

SHUTDOWN=0
SLEEP=1
RESTART=2

def shutdown_pc(phone, delay=None, _command=SHUTDOWN):
    try: 
        print(f'Shutdown {phone}')
        if phone not in pcs.stored: phone = pcs.get_by_name(phone)
        IP = pcs[phone]['pc ip']
        if IP is None: return
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.connect((IP, 666))
        command="SHUTDOWN" if _command is SHUTDOWN else "SLEEP" if _command is SLEEP else 'RESTART'
        send(_socket, sha256(f"{command}{globals()['pcs'][phone]['pc'].lower()}".encode("utf-8")).hexdigest())
        if delay is not None: send(_socket, delay)
        t = threading.Thread(target=retrive_confirmation, args=[_socket,globals()['pcs'][phone]['name'],delay,])
        t.name = f"Confirmation {globals()['pcs'][phone]['name']}"
        t.start()
    except Exception as ex:
        print(f"{type(ex)} -> {ex}")

def scann(_ip):
    ip = _ip.split(".")
    ip[-1] = "2-24"
    ip = '.'.join(ip)
    API.blockPrint()
    start = time.process_time()
    scanner = nmap.PortScanner()
    API.enablePrint()
    mc = {}
    while True:
        try:
            ip_s = scanner.scan(hosts=ip, arguments="-sn --max-parallelism 1000")
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
            #print(f'Average scann time: {avg(_avg)}')
            _avg = []
        counter += 1
        time.sleep(0.2)

def main():
    global loop_run
    global window
    global console_window
    while True:
        window.work(*window.read(timeout=1))
        console_window.work(*console_window.read(timeout=1))
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
        ret = pcs.add_new(address=data[1], key=data[0], name=data[3], dc=data[4], id=data[2])
    elif _type == "EDIT":
        ret = pcs.changed(data)
    if not ret: window.update_UI(pcs)
    else:
        sg.popup(ret, "Error")
    save()

def delete(name):
    pcs.remove(pcs.get_by_name(name))
    window.update_UI(pcs)

def _console(inp):
    if "wake" in inp:
        name = inp.split(" ")[-1]
        pcs.wake(pcs.get_by_name(name))
        window.update_UI(pcs)
    elif "morning" in inp:
        pcs.wake_everyone()
    elif "stop" in inp:
        pcs.save_to_json()
        save()
        window.Close()
        console_window.close()
        _api.close()
    elif "shutdown" in inp:
        name = inp.split(" ")[-1]
        shutdown_pc(pcs.get_by_name(name))
    elif "sleep" in inp:
        name = inp.split(" ")[-1]
        shutdown_pc(pcs.get_by_name(name), _command=SLEEP)
    elif "restart" in inp:
        name = inp.split(" ")[-1]
        shutdown_pc(pcs.get_by_name(name), _command=RESTART)
    elif "list" in inp:
        for values in pcs:
            print(values.split(" - ")[0])
    elif "update" in inp:
        import updater
        if updater.main():
            _console("stop")
            from os import system as run
            run("restarter.bat")

def UI_wake(name):
    print(f"Wake {name}")
    pcs.wake(pcs.get_by_name(name))
    return pcs

def ui_update():
    window.update_UI(pcs)

def api_send(msg, user=None):
    try:
        _api.send_message(msg, user)
    except: print("API not avaleable!")

def api_sleep(phone, delay=None):
    try:
        shutdown_pc(phone, delay, _command=SLEEP)
    except Exception as ex:
        print(f"{type(ex)} -> {ex}")

def api_wake(name):
    try:
        print(f"Wake {name}")
        pcs.wake(pcs.get_by_name(name))
        ui_update()
    except Exception as ex:
        print(f"{type(ex)} -> {ex}")

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
try:
    pcs.self_test()
except:
    pcs = computers(api_send)
    if path.exists('export.json'):
        pcs.import_from_json()
        save()
window = main_window(pcs, call_back, delete, get_data, UI_wake, shutdown_pc)
console_window = console(_console)
print = console_window.print
pcs.set_window(ui_update)
check_loop = threading.Thread(target=loop)
check_loop.name = "Wake check loop"
check_loop.start()
_api = API.API("Waker", "ef6a9df062560ce93e1236bce9dc244a6223f1f68ba3dd6a6350123c7719e78c")
_api.validate(timeout=3)
_api.create_function("wake", "Wakes up the user's connected PC\nCategory: NETWORK", api_wake, [API.SENDER])
_api.create_function("shutdown", "Shuts down the user's connected PC\nUsage: &shutdown <delay in second. default: 30>\nCategory: NETWORK", shutdown_pc, [API.SENDER, API.USER_INPUT])
_api.create_function("sleep", "Sends the user's connected PC to sleep\nUsage: &sleep <delay in second. default: 30>\nCategory: NETWORK", api_sleep, [API.SENDER, API.USER_INPUT])
try:
    main()
except:
    _api.close("Fatal exception occured")