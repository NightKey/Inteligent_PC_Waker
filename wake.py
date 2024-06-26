from shutil import copy

try:
    from wakeonlan import send_magic_packet
    import re
    import socket
    import threading
    import time
    import pickle
    import json
    import random
    from getmac import get_mac_address
    from smdb_api import API, Message, Interface
    from os import path, devnull
    import platform    # For getting the operating system name
    import subprocess  # For executing a shell command
    from datetime import datetime, timedelta
    from datetime import time as dtime
    from hashlib import sha256
    import arpsim
except Exception as ex:
    from os import system as run
    from platform import system
    pre = "sudo " if system() == 'Linux' else ""
    post = " --user" if system() == 'Windows' else ""
    interpreter = 'python' if system() == 'Windows' else 'python3'
    run(f"{pre}{interpreter} -m pip install{post} --upgrade -r dependencies.txt")
    if system() == "Linux":
        run("sudo apt install net-tools")
    ext = "sh" if system() == 'Linux' else "exe"
    run(f"./restarter.{ext}")
    print(f"{type(ex)} -> {ex}")
    exit()


class computer:
    id: int = None
    pc: str = None
    phone: str = None
    name: str = None
    discord: str = None
    last_online: datetime = None
    was_wakened: bool = False
    is_online: bool = False
    is_time: bool = None
    was_online: bool = False
    wake_time: datetime = None
    last_signal: datetime = None
    manually_turned_off: bool = True
    pc_ip: str = None
    phone_last_online: datetime = None
    telegramm: int = None

    def __init__(self, id: str, pc: str, phone: str, name: str, discord_tag: str, is_time: bool, fix_ip: str = None, telegramm: int = None) -> None:
        self.id = id
        self.pc = pc
        self.phone = phone
        self.name = name
        self.discord = discord_tag
        self.is_time = is_time
        self.fix_ip = fix_ip
        self.telegramm = telegramm


original_print = print


class computers:
    """Stores multiple computer-phone address pairs.
    Can only send a wake package to a given PC, if the phone address is provided, and the PC wasn't waken before, or it were restored.
    """
    TIMES = {"pbt": 5, "pbst": 7, "msrt": 30, "st": 60,
             "stsd": 1}  # [Pass by time, Pass by shut off time, Manual state reset time, Shutdown time, Shutdown time signal delta]

    def __init__(self, send=None):
        self.stored: dict[str, computer] = {}
        self.id = 0x0
        self.send = send
        self.random_welcome: list = []
        with open("welcomes.txt", 'r', encoding="utf-8") as f:
            self.random_welcome: list = f.read(-1).split('\n')

    def ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """
        # Option for the number of packets as a function of
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, '1', host]
        with open(devnull, 'a') as dnull:
            tmp = subprocess.call(command, stdout=dnull) == 0
        return tmp

    def add_new(self, address, key, name, dc=None, id=None, ip=None, tg=None):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        address == address.replace("-", ":")
        key == key.replace("-", ":")
        if not self.is_MAC(address):
            return "PC"  # TypeError("'address' should be a MAC address")
        if not self.is_MAC(key) or self.is_time(key):
            # TypeError("'KEY' should be a MAC address or time intervall (0:00-12:00)")
            return "KEY"
        if key in self.stored:
            return "USED"  # KeyError("'KEY' already used for a computer.")
        self.stored[key] = computer(
            self.id if id is None else id, address, key, name, dc, self.is_time(key), ip, tg)
        if id is None:
            self.id += 0x1
        return False

    def get_UI_list(self):
        """Returns a list for the UI containing the following format:
        name - offline/WOL sent
        """
        ret = []
        for item in self.stored.values():
            ret.append(f"{item.name} - {'WOL sent' if item.was_wakened and (not item.was_online or (item.wake_time is not None and datetime.now() - item.wake_time < timedelta(minutes=2))) else 'Online' if item.is_online else 'Offline'}")
        return ret

    def __len__(self):
        return len(self.stored)

    def __getitem__(self, key):
        if isinstance(key, int):
            if key < len(self.stored):
                return self.get_UI_list()[key]
            else:
                raise StopIteration()
        if key in self.stored:
            return self.stored[key]
        else:
            return None

    def changed(self, data):
        del self.stored[self.get_by_id(data[2])]
        self.add_new(address=data[1], key=data[0],
                     name=data[3], dc=data[4], id=data[2], tg=data[5])

    def remove(self, other):
        del self.stored[other]

    def get_by_name(self, name):
        name = name.strip()
        print(f"Searching for {name}")
        for key, values in self.stored.items():
            if values.name == name or values.discord == name or values.telegramm == name:
                return key
        else:
            return False

    def get_by_id(self, id):
        for key, value in self.stored.items():
            if value.id == id:
                return key

    def iterate(self, resoults):
        if resoults == {}:
            return
        for phone, data in self.stored.items():
            PC_Online = (data.pc.upper() in resoults)
            self.stored[phone].is_online = PC_Online
            if PC_Online and not self.stored[phone].was_online:
                self.stored[phone].was_online = True
            if PC_Online and self.stored[phone].pc_ip is None:
                self.stored[phone].pc_ip = resoults[self.stored[phone].pc]
            elif not PC_Online:
                self.stored[phone].pc_ip = None
            if data.is_time:
                try:
                    tmp = phone.split("-")
                except:
                    tmp = [phone, None]
                now = datetime.now().strftime("%H:%M")
                if tmp[0] == now:
                    self.wake(phone)
                elif tmp[1] == now:
                    if not das:
                        shutdown_pc(phone)
                    self.reset_state(phone, FULL)
                continue
            if phone.upper() in resoults:  # Wake, if not online
                data.phone_last_online = datetime.now()
                if not data.was_wakened and not data.manually_turned_off:
                    if PC_Online:
                        data.was_wakened = True
                        data.wake_time = datetime.now()
                    else:
                        self.wake(phone)
                elif data.was_wakened and not PC_Online and data.was_online:
                    self.reset_state(phone, PARTIAL)
            elif data.was_wakened and (data.phone_last_online is None or datetime.now()-data.phone_last_online > timedelta(minutes=computers.TIMES["pbt"])):
                self.reset_state(phone, TINY)  # Pass by time
                if PC_Online and data.wake_time is not None and datetime.now()-data.wake_time <= timedelta(minutes=computers.TIMES["pbst"]):
                    if not das:
                        shutdown_pc(phone)  # Pass by shut off time
            elif data.phone_last_online is not None and datetime.now()-data.phone_last_online >= timedelta(minutes=computers.TIMES["msrt"]) and data.manually_turned_off:
                self.reset_state(phone, SMALL)  # Manual state reset time
            # Shutdown time
            elif data.phone_last_online is not None and datetime.now()-data.phone_last_online >= timedelta(minutes=computers.TIMES["st"]):
                # Shutdown time signal delta
                if data.pc_ip is not None and (data.last_signal is None or datetime.now()-data.last_signal > timedelta(minutes=computers.TIMES["stsd"])):
                    if not das:
                        shutdown_pc(phone)
                    self.stored[phone].last_signal = datetime.now()
                self.reset_state(phone, FULL)

    def wake_everyone(self):
        for key in self.stored.keys():
            self.wake(key)

    def get_random_welcome(self):
        if len(self.random_welcome) == 0:
            with open("welcomes.txt", 'r', encoding="utf-8") as f:
                self.random_welcome: list = f.read(-1).split('\n')
        return random.choice(self.random_welcome)

    def wake(self, phone, automatic=True):
        if automatic and (datetime.now().time() < dont_wake_before or datetime.now().time() > dont_wake_after):
            self.reset_state(phone, PARTIAL)
            return
        print(f"Waking {self.stored[phone].name}")
        send_magic_packet(self.stored[phone].pc, ip_address="192.168.0.255")
        self.stored[phone].was_wakened = True
        self.stored[phone].wake_time = datetime.now()
        if self.send is not None and automatic:
            self.send(self.get_random_welcome(),
                      user=self.stored[phone].discord)
        elif self.send is not None:
            return "Done"

    def reset_state(self, phone, size):
        if size is TINY:
            self.stored[phone].was_wakened = False
            print(f"{self.stored[phone].name} offline for 5 minutes.")
        elif size is SMALL:
            self.stored[phone].manually_turned_off = False
            print(f"{self.stored[phone].name} PC can be wakened")
        elif size is PARTIAL:
            self.stored[phone].was_online = False
            self.stored[phone].manually_turned_off = True
            print(f"{self.stored[phone].name} PC went offline.")
        elif size is FULL:
            self.stored[phone].phone_last_online = None
            print(f"{self.stored[phone].name} state reseted")

    def save_to_json(self):
        out = [{'phone': phone, 'pc': values.pc, 'name': values.name, "dc": values.discord,
                'telegramm': values.telegramm} for phone, values in self.stored.items()]
        if path.exists('export.json'):
            copy("export.json", "export.json.bck")
        with open('export.json', 'w', encoding='utf-8') as f:
            json.dump(out, f)

    def import_from_json(self):
        with open("export.json", 'r', encoding='utf-8') as f:
            tmp = json.load(f)
        for item in tmp:
            self.add_new(item["pc"], item['phone'], item["name"], (item['dc']
                         if 'dc' in item else None), ip=(item['ip'] if 'ip' in item else None), tg=(item['telegramm'] if 'telegramm' in item else None))

    def is_MAC(self, _input):
        _input.replace("-", ':').replace(".", ':').replace(" ", ':')
        if re.match(r"([a-fA-F0-9]{2}[:-]){5}([a-fA-F0-9]{2})", _input) is None:
            return False
        return True

    def is_time(self, _input):
        if re.match(r"^((([0-1]{0,1}\d)|(2[0-3])):([0-5]\d)-(([0-1]{0,1}\d)|(2[0-3])):([0-5]\d)){1}", _input) is None and re.match(r"^((([0-1]{0,1}\d)|(2[0-3])):([0-5]\d)){1}", _input) is None:
            return False
        return True

class NotDelayException(Exception):
    message: str

    def __init__(self, message):
        super(message)
        self.message = message

class Delay:
    min_shutdown_dilay = 10
    default_shutdown_delay = 30
    now = 0
    secunds: int

    def convertable_to_int(data):
        try:
            _ = int(data)
            return True
        except:
            return False

    def is_delay(data):
        try:
            Delay(data)
            return True
        except NotDelayException:
            return False

    def __init__(self, input_string: str):
        actual_delay: int = -1
        if input_string is None:
            actual_delay = Delay.default_shutdown_delay
        elif input_string.lower() == "now":
            self.secunds = Delay.now
            return
        elif "h" in input_string or "m" in input_string or "s" in input_string:
            if 'h' in input_string:
                try:
                    actual_delay += int(input_string.split('h')[0])*60*60
                    input_string = input_string.split('h')[1]
                except:
                    pass
            if 'm' in input_string:
                try:
                    actual_delay += int(input_string.split('m')[0])*60
                    input_string = input_string.split('m')[1]
                except:
                    pass
            if 's' in input_string or input_string != '':
                try:
                    actual_delay += int(input_string.split('s')[0])
                except:
                    pass
            if actual_delay == -1:
                actual_delay = Delay.default_shutdown_delay
            else:
                actual_delay += 1
        elif Delay.convertable_to_int(input_string):
            actual_delay = int(input_string)
        else:
            raise NotDelayException()
        if actual_delay < Delay.min_shutdown_dilay:
            actual_delay = Delay.min_shutdown_dilay
        self.secunds = actual_delay

loop_run = True
dont_wake_after = dtime.fromisoformat("22:00")
dont_wake_before = dtime.fromisoformat("06:00")

_api: API = None
check_loop: threading.Thread = None
pcs: computers = None
ip = None
das = True

TINY = 0
SMALL = 1
PARTIAL = 2
FULL = 3

def restart():
    from os import system as run
    from platform import system
    ext = "sh" if system() == 'Linux' else "exe"
    run(f"./restarter.{ext}")

def retrive_confirmation(socket: socket.socket, name: str, delay: int):
    start_time = time.time()
    socket.settimeout(float(delay))
    while time.time() - start_time < delay:
        try:
            r = socket.recv(1).decode("utf-8")
            print(f"{name} Command status retrived")
            if r == '1':
                ansv = "PC executed the command"
            else:
                ansv = "PC interrupted the command"
            break
        except:
            time.sleep(0.1)
    else:
        ansv = "socket timed out"
    print(f"{name} {ansv}")
    api_send(ansv, user=pcs[pcs.get_by_name(name)].discord)

SHUTDOWN = 0
SLEEP = 1
RESTART = 2

def shutdown_pc(phone, delay=None, _command=SHUTDOWN, user=None, interface=Interface.Discord):
    try:
        if user is None:
            user = globals()['pcs'][phone].discord
        print(f'Shutdown {phone}')
        if phone not in pcs.stored:
            phone = pcs.get_by_name(phone)
        if phone not in pcs.stored:
            print(f"User  not found {phone}")
            return
        IP = pcs[phone].pc_ip if pcs[phone].fix_ip is None else pcs[phone].fix_ip
        if IP is None:
            print(f"IP not found for {phone} PC")
            api_send(f"IP not found for {phone} PC",
                     user=user, interface=interface)
            return
        try:
            actual_delay = Delay(delay)
        except NotDelayException as e:
            print(f"{delay} not a correct delay value!")
            api_send(f"{delay} not a correct delay value!",
                     user=user, interface=interface)
            return
        try:
            _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _socket.connect((IP, 666))
            command = "SHUTDOWN" if _command is SHUTDOWN else "SLEEP" if _command is SLEEP else 'RESTART'
            send(_socket, sha256(
                f"{command}{globals()['pcs'][phone].pc.lower()}".encode("utf-8")).hexdigest())
            send(_socket, actual_delay.secunds)
            try:
                _socket.recv(5).decode("utf-8")
                api_send(
                    f"Initiated '{command.lower()}' command!", user=user, interface=interface)
                print(f"{phone} ACK arrived!")
                t = threading.Thread(target=retrive_confirmation, args=[_socket, globals()[
                                     'pcs'][phone].name, actual_delay.secunds*2, ])
                t.name = f"Confirmation {globals()['pcs'][phone].name}"
                t.start()
            except TimeoutError:
                print(
                    f"Acknolagement didn't arrive for {globals()['pcs'][phone].name}!")
                api_send(
                    f"Pc did not react to the {command.lower()} command!", user=user, interface=interface)
        except Exception as ex:
            print(f"Exception in shutdown_pc send: {ex}")
            api_send(
                f"Excepption during shutdown sending: {ex}", user=user, interface=interface)
    except Exception as ex:
        print(f"Exception in shutdown_pc: {ex}")

def scan(_ip, pre_scann=False):
    ip = _ip.split(".")
    del ip[-1]
    ip = '.'.join(ip)
    ip = [f"{ip}.{i}" for i in range(2, 254)]
    start = time.time()
    ip_s = []
    mc = {}
    if pre_scann:
        arpsim.pre_check(ip)
    ip_s = arpsim.arp_scan()
    for pcip in ip_s:
        if len(pcip) != 2:
            continue
        if pcip[0] != _ip:
            mc[pcip[1]] = pcip[0]
    finish = time.time()
    #print(f"Finished under {finish-start} s")
    return [mc, start, finish]

def dump_to_file(arg):
    """Dumps the arg to a file. arg must be json-like.
    """
    with open("DUMP.txt", "w") as f:
        json.dump(arg, f)

def send(socket, msg):
    msg = json.dumps(msg)
    while True:
        tmp = ''
        if len(msg) > 9:
            tmp = msg[9:]
            msg = msg[:9]
        socket.send(str(len(msg)).encode(encoding='utf-8'))
        socket.send(msg.encode(encoding="utf-8"))
        if tmp == '':
            tmp = '\n'
        if msg == '\n':
            break
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
        ret = scan(ip, counter % 50 == 0)
        pcs.iterate(ret[0])
        # _avg.append(ret[2]-ret[1])
        if counter == 200:
            get_ip()
            counter = -1
            #print(f"Average scan time: {avg(_avg)}s")
            #_avg = []
        counter += 1
        time.sleep(1)

def main():
    global loop_run
    while True:
        try:
            time.sleep(0.3)
        except KeyboardInterrupt:
            break
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

def delete(name):
    pcs.remove(pcs.get_by_name(name))

def save_data():
    pcs.save_to_json()
    save()

def update(*_):
    import updater
    if updater.main():
        _api.close("Update")
        restart()

def api_send(msg, user=None, interface=Interface.Discord):
    try:
        _api.send_message(message=msg, interface=interface, destination=user)
    except Exception as ex:
        print("API exception!")
        print(ex)

def api_sleep(message):
    get_api_shutdown_sleep(message, SLEEP)

def get_target_name(data: list):
    if pcs.get_by_name(data[0]):
        name = data[0]
        n = 1
    else:
        name = data[1]
        n = 0
    return [name, n]

def get_target_name_discord_tag(id: str, data: list):
    name = _api.get_username(id)
    if Delay.convertable_to_int(data[0]):
        n = 0
    else:
        n = 1
    return [name, n]

def determine_delay_for_api_call(delay: list, has_user: bool, user_id: str):
    name = None
    actual_delay = None
    if has_user:
        name, n = get_target_name_discord_tag(user_id, delay)
    else:
        name, n = get_target_name(delay)
    if len(delay) > 1:
        actual_delay = delay[n]
    return [name, actual_delay]

def is_directed_command(delay):
    if delay is None:
        return False
    if " " in delay:
        return True
    if Delay.is_delay(delay):
        return False
    return True

def get_api_shutdown_sleep(message: Message, command):
    try:
        requester = message.sender
        delay = message.content if message.content != "" else None
        has_user = message.contains_user()
        if has_user or is_directed_command(delay):
            if _api.is_admin(requester):
                requester, delay = determine_delay_for_api_call(
                    delay.split(" "), has_user, message.get_contained_user_id())
            else:
                print("User is not admin!")
                api_send(
                    "Only admins allowed to shutdown/sleep other users!", user=requester)
                return
        shutdown_pc(requester, delay, _command=command,
                    user=message.sender, interface=message.interface)
    except Exception as ex:
        print(f"Exception in get_api_shutdown_sleep: {ex}")

def api_shutdown(message):
    get_api_shutdown_sleep(message, SHUTDOWN)

def api_wake(message: Message):
    try:
        print(f"Wake {message.sender}")
        user = pcs.get_by_name(message.sender)
        if not user:
            api_send("Your account is not connected to any PC on the list",
                     message.sender, message.interface)
            return
        api_send(pcs.wake(user, False), message.sender, message.interface)
    except Exception as ex:
        print(f"Exception in api_wake: {ex}")

def status(message):
    if _api.valid:
        if (not _api.send_message(pcs.get_UI_list(), destination=message.channel)):
            _api.send_message(pcs.get_UI_list(), destination=message.sender)

def Computers_test(computers: computers):
    for line in Computers_functions:
        _ = getattr(computers, line)
    for line in Computers_should_not_contain:
        if line in computers.__dict__.items():
            raise Exception("Unused function!")
    for _, data in computers.stored.items():
        for line in Computers_data_keys:
            getattr(data, line)
        break

def init_api():
    global _api
    _api = API("Waker", "ef6a9df062560ce93e1236bce9dc244a6223f1f68ba3dd6a6350123c7719e78c",
               update_function=update)
    _api.validate()
    _api.create_function(
        "wake", "Wakes up the user's connected PC\nUsage: &wake\nCategory: NETWORK", api_wake)
    _api.create_function(
        "shutdown", "Shuts down the user's connected PC\nUsage: &shutdown <delay in either secunds, or xhymzs format, where x,y,z are numbers. default: 30s>\nCategory: NETWORK", api_shutdown)
    _api.create_function(
        "shtd", "Same as shutdown\nUsage: &shtd <delay in either secunds, or xhymzs format, where x,y,z are numbers. default: 30s>\nCategory: NETWORK", api_shutdown)
    _api.create_function(
        "sleep", "Sends the user's connected PC to sleep\nUsage: &sleep <delay in either secunds, or xhymzs format, where x,y,z are numbers. default: 30s>\nCategory: NETWORK", api_sleep)
    _api.create_function(
        "PCStatus", "Shows the added PC's status\nCategory: NETWORK", status)

def print(data):
    original_print(f"[{datetime.now()}]: {data}")

def setup():
    global check_loop
    global pcs
    if path.exists("pcs"):
        with open("pcs", 'br') as f:
            pcs = pickle.load(f)
    else:
        pcs = computers(api_send)
        if path.exists('export.json'):
            pcs.import_from_json()
            save()
    try:
        print("Testing the integrity...")
        Computers_test(pcs)
        print("Test succeeded")
    except Exception as ex:
        print("Test failed, reimporting...")
        pcs = computers(api_send)
        if path.exists('export.json'):
            pcs.import_from_json()
            save()
        print("Reimport finished")
    check_loop = threading.Thread(target=loop)
    check_loop.name = "Wake check loop"
    check_loop.start()

get_ip()

Computers_functions = [
    "stored",
    "id",
    "window",
    "send",
    "set_window",
    "ping",
    "add_new",
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
    "is_time"]
Computers_should_not_contain = [
    "print_import_message"
]
Computers_data_keys = [
    "pc",
    "is_online",
    "was_wakened",
    "id",
    "name",
    "phone_last_online",
    "was_online",
    "wake_time",
    "discord",
    "pc_ip",
    "last_signal",
    "manually_turned_off",
    "is_time",
    "telegramm"]

init_api()
setup()

try:
    main()
except Exception as ex:
    if _api.valid:
        _api.close("Fatal exception occured")
    input(f"Excepton: {ex}\nPress return to exit!")
finally:
    if _api.valid:
        _api.close("Closed")
