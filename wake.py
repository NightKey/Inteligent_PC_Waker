from enum import Enum
from shutil import copy
from typing import Union, Dict

try:
    from wakeonlan import send_magic_packet
    from dataclasses import dataclass, field
    import re
    import socket
    import threading
    import time
    import pickle
    import json
    import random
    from smdb_api import API, Message, Interface
    from smdb_logger import Logger, LEVEL
    from os import path, devnull
    import platform    # For getting the operating system name
    import subprocess  # For executing a shell command
    from datetime import datetime, timedelta
    from datetime import time as dtime
    from hashlib import sha256
    from arpsim import scan_local
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

@dataclass
class User:
    name: str
    discord: str
    telegram: str
    phone: str

class Status(Enum):
    ONLINE = 0
    WAKING = 1
    M_SHUTTING_DOWN =  2
    A_SHUTTING_DOWN = 3
    MANUALLY_OFF =  4
    AUTOMATIC_OFF =  5

@dataclass
class PC:
    id: int
    MAC_address: str
    owner: User
    ip_address: Union[str, None] = field(init=False, default=None)
    status: Status = field(init=False, default=Status.AUTOMATIC_OFF)
    last_online: datetime = field(init=False, default=datetime(2024, 12, 1))

    def update_status(self, new_status: Status):
        if(self.status == Status.ONLINE and new_status in [Status.MANUALLY_OFF, Status.AUTOMATIC_OFF]):
            self.last_online = time.time()
        self.status = new_status
    
    def update_owner(self, new_owner: User):
        self.owner = new_owner
    
    def update_ip(self, new_ip: str):
        self.ip_address = new_ip

class Computers:
    """Stores multiple computer-phone address pairs.
    Can only send a wake package to a given PC, if the phone address is provided, and the PC wasn't waken before, or it were restored.
    """
    TIMES = {"pbt": 5, "pbst": 7, "msrt": 30, "st": 60,
             "stsd": 1}  # [Pass by time, Pass by shut off time, Manual state reset time, Shutdown time, Shutdown time signal delta]

    VERSION = 1.0

    def __init__(self, send=None, version: float = VERSION):
        self.stored: dict[str, PC] = {}
        self.id = 0x0
        self.send = send
        self.random_welcome: list = []
        self.version = version
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

    def add_new(self, pc_mac: str, phone_mac: str, user_name: str, discord_id=None, user_id=None, pc_ip=None, telegram_id=None):
        """
        Adds a new PHONE-PC connection. One phone can only be used to power on one PC
        """
        pc_mac = pc_mac.replace("-", ":")
        phone_mac = phone_mac.replace("-", ":")
        if not self.is_MAC(pc_mac):
            return "PC"
        if not self.is_MAC(phone_mac) or self.is_time(phone_mac):
            return "KEY"
        if phone_mac in self.stored:
            return "USED"
        self.stored[phone_mac] = PC(self.id if user_id is None else user_id, pc_mac, User(user_name, discord_id, telegram_id, phone_mac))
        if user_id is None:
            self.id += 0x1
        return False

    def get_UI_list(self):
        """Returns a list for the UI containing the following format:"""
        ret = []
        for item in self.stored.values():
            ret.append(f"{item.owner.name} - {item.status.name}")
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
        self.add_new(pc_mac=data[1], phone_mac=data[0],
                     user_name=data[3], discord_id=data[4], user_id=data[2], telegram_id=data[5])

    def remove(self, other):
        del self.stored[other]

    def get_by_name(self, name: str):
        name = name.strip()
        print(f"Searching for {name}")
        for key, values in self.stored.items():
            if values.owner.name == name or values.owner.discord == name or values.owner.telegram == name:
                return key
        else:
            return False

    def get_by_id(self, id):
        for key, value in self.stored.items():
            if value.id == id:
                return key

    def iterate(self, results: Dict[str, str]):
        if results == {}:
            return
        for phone, data in self.stored.items():
            PC_Online = (data.MAC_address.upper() in results)
            if PC_Online:
                data.status = Status.ONLINE
                if data.status == Status.A_SHUTTING_DOWN:
                    data.status = Status.AUTOMATIC_OFF
            else:
                if data.status == Status.A_SHUTTING_DOWN:
                    data.status = Status.AUTOMATIC_OFF
                else:
                    data.status = Status.MANUALLY_OFF
            if PC_Online and data.ip_address is None:
                data.ip_address = results[data.MAC_address]
            elif not PC_Online:
                data.ip_address = None
            if phone.upper() in results:  # Wake, if not online
                data.last_online = datetime.now()
                if data.status == Status.AUTOMATIC_OFF:
                    self.wake(phone)
                elif data.status == Status.WAKING:
                    if not PC_Online:
                        self.reset_state(phone, Reset.FORCE_MANUAL_OFF)
                    else:
                        data.status = Status.ONLINE
            elif data.status in [Status.ONLINE, Status.WAKING] and (data.last_online is None or datetime.now()-data.last_online > timedelta(minutes=Computers.TIMES["pbt"])):
                shutdown_pc(phone)  # Pass by shut off time
                logger.info(f"Shutting down {data.owner.name}, phone offline for {Computers.TIMES['pbt']} minutes.")
            elif data.last_online is not None and datetime.now()-data.last_online >= timedelta(minutes=Computers.TIMES['msrt']) and data.status == Status.MANUALLY_OFF:
                self.reset_state(phone, Reset.FORCE_AUTO_OFF)  # Manual state reset time
            # Shutdown time
            elif data.last_online is not None and datetime.now()-data.last_online >= timedelta(minutes=Computers.TIMES["st"]):
                # Shutdown time signal delta
                self.reset_state(phone, Reset.FULL)

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
            self.reset_state(phone, Reset.FORCE_MANUAL_OFF)
            return
        logger.info(f"Waking {self.stored[phone].owner.name}")
        tmp = ip.split(".")[:-1]
        tmp.append("255")
        send_magic_packet(self.stored[phone].MAC_address, ip_address=".".join(tmp))
        self.stored[phone].status = Status.WAKING
        if self.send is not None and automatic:
            self.send(self.get_random_welcome(), user=self.stored[phone].owner.discord)
        elif self.send is not None:
            return "Done"

    def reset_state(self, phone, size):
        if size is Reset.FORCE_AUTO_OFF:
            self.stored[phone].status = Status.AUTOMATIC_OFF
            logger.debug(f"{self.stored[phone].owner.name} PC can be wakened")
        elif size is Reset.FORCE_MANUAL_OFF:
            self.stored[phone].status = Status.MANUALLY_OFF
            logger.debug(f"{self.stored[phone].owner.name} PC went offline.")
        elif size is Reset.FULL:
            self.stored[phone].last_online = None
            logger.debug(f"{self.stored[phone].owner.name} state reseted")

    def save_to_json(self):
        out = [{'phone': phone, 'pc': values.MAC_address, 'name': values.owner.name, "dc": values.owner.discord,
                'telegramm': values.owner.telegram} for phone, values in self.stored.items()]
        if path.exists('export.json'):
            copy("export.json", "export.json.bck")
        with open('export.json', 'w', encoding='utf-8') as f:
            json.dump(out, f)

    def import_from_json(self):
        with open("export.json", 'r', encoding='utf-8') as f:
            tmp = json.load(f)
        for item in tmp:
            self.add_new(item["pc"], item['phone'], item["name"], (item['dc']
                         if 'dc' in item else None), pc_ip=(item['ip'] if 'ip' in item else None), telegram_id=(item['telegramm'] if 'telegramm' in item else None))

    def is_MAC(self, _input: str):
        _input.replace("-", ':').replace(".", ':').replace(" ", ':')
        if re.match(r"([a-fA-F0-9]{2}[:-]){5}([a-fA-F0-9]{2})", _input) is None:
            return False
        return True

    def is_time(self, _input: str):
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
    seconds: int

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
            self.seconds = Delay.now
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
        self.seconds = actual_delay

loop_run = True
dont_wake_after = dtime.fromisoformat("22:00")
dont_wake_before = dtime.fromisoformat("06:00")
logger = Logger(level=LEVEL.TRACE)

_api: API = None
check_loop: threading.Thread = None
pcs: Computers = None
ip: str = None

class Reset(Enum):
    FORCE_AUTO_OFF = 0
    FORCE_MANUAL_OFF = 1
    FULL = 2

def restart():
    from os import system as run
    from platform import system
    ext = "sh" if system() == 'Linux' else "exe"
    run(f"./restarter.{ext}")

def retrive_confirmation(socket: socket.socket, name: str, delay: float):
    start_time = time.time()
    socket.settimeout(delay)
    data = pcs[pcs.get_by_name(name)]
    while time.time() - start_time < (delay * 3):
        try:
            r = socket.recv(1).decode("utf-8")
            logger.info(f"{name} Command status retrived")
            if r == '1':
                ansv = "PC executed the command"
                if data.status == Status.A_SHUTTING_DOWN:
                    data.status = Status.AUTOMATIC_OFF
                else: 
                    data.status = Status.MANUALLY_OFF
            else:
                ansv = "PC interrupted the command"
                data.status = Status.ONLINE
            break
        except:
            time.sleep(0.1)
    else:
        ansv = "socket timed out"
        data.status = Status.ONLINE
    logger.info(f"{name} {ansv}")
    api_send(ansv, user=data.owner.discord)

class Command(Enum):
    SHUTDOWN = 0
    SLEEP = 1
    RESTART = 2

def shutdown_pc(phone: str, delay: Union[Delay, None] = None, _command = Command.SHUTDOWN, user: Union[Delay, None] = None, interface = Interface.Discord):
    try:
        if phone not in pcs.stored:
            logger.info(f"User  not found {phone}")
            return
        data = pcs[phone]
        IP = data.ip_address
        if IP is None:
            logger.info(f"IP not found for {data.owner.name} PC")
            api_send(f"IP not found for {data.owner.name} PC", user=user, interface=interface)
            return
        try:
            actual_delay = Delay(delay)
        except NotDelayException as e:
            logger.info(f"{delay} not a correct delay value!")
            api_send(f"{delay} not a correct delay value!", user=user, interface=interface)
            return
        try:
            _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _socket.connect((IP, 666))
            command = _command.name
            send(_socket, sha256(f"{command}{data.MAC_address.lower()}".encode("utf-8")).hexdigest())
            send(_socket, actual_delay.seconds)
            try:
                _socket.recv(5).decode("utf-8")
                api_send(f"Initiated '{command.lower()}' command!", user=user, interface=interface)
                logger.info(f"{data.owner.name} ACK arrived!")
                t = threading.Thread(target=retrive_confirmation, args=[_socket, data.owner.name, float(actual_delay.seconds*2), ])
                t.name = f"Confirmation {data.name}"
                t.start()
            except TimeoutError:
                logger.warning(f"Acknolagement didn't arrive for {data.owner.name}!")
                api_send(f"Pc did not react to the {command.lower()} command!", user=user, interface=interface)
        except Exception as ex:
            logger.error(f"Exception in shutdown_pc send: {ex}")
            logger.debug(f"IP address: {IP}")
            api_send(f"Excepption during shutdown sending: {ex}", user=user, interface=interface)
    except Exception as ex:
        logger.error(f"Exception in shutdown_pc: {ex}")

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

def loop():
    global ip
    counter = 0
    while loop_run:
        ret = scan_local(ip, 254)
        pcs.iterate(ret)
        if counter == 200:
            get_ip()
            counter = -1
        counter += 1
        time.sleep(1)

def main():
    global loop_run
    while True:
        try:
            time.sleep(1)
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
        if(user is not None):
            _api.send_message(message=msg, interface=interface, destination=user)
    except Exception as ex:
        logger.error(f"API exception: {ex}")

def api_sleep(message):
    get_api_shutdown_sleep(message, Command.SLEEP)

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
                logger.warning(f"User `{_api.get_username(requester)}` is not admin!")
                api_send("Only admins allowed to shutdown/sleep other users!", user=requester)
                return
        shutdown_pc(requester, delay, _command=command,
                    user=requester, interface=message.interface)
    except Exception as ex:
        logger.error(f"Exception in get_api_shutdown_sleep: {ex}")

def api_shutdown(message):
    get_api_shutdown_sleep(message, Command.SHUTDOWN)

def api_wake(message: Message):
    try:
        logger.info(f"Wake {message.sender}")
        user = pcs.get_by_name(message.sender)
        if not user:
            api_send("Your account is not connected to any PC on the list", message.sender, message.interface)
            return
        api_send(pcs.wake(user, False), message.sender, message.interface)
    except Exception as ex:
        logger.error(f"Exception in api_wake: {ex}")

def status(message: Message):
    if _api.valid:
        if (not _api.send_message(pcs.get_UI_list(), destination=message.channel)):
            _api.send_message(pcs.get_UI_list(), destination=message.sender)

def Computers_test(computers: Computers):
    return computers.version == Computers.VERSION

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

def setup():
    global check_loop
    global pcs
    if path.exists("pcs"):
        try:
            with open("pcs", 'br') as f:
                pcs = pickle.load(f)
        except:
            pcs = Computers(api_send)
            if path.exists('export.json'):
                pcs.import_from_json()
                save()
    else:
        pcs = Computers(api_send)
        if path.exists('export.json'):
            pcs.import_from_json()
            save()
    try:
        logger.info("Testing the integrity...")
        Computers_test(pcs)
        logger.debug("Test succeeded")
    except Exception as ex:
        logger.warning("Test failed, reimporting...")
        pcs = Computers(api_send)
        if path.exists('export.json'):
            pcs.import_from_json()
            save()
        logger.info("Reimport finished")
    check_loop = threading.Thread(target=loop)
    check_loop.name = "Wake check loop"
    check_loop.start()

get_ip()
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
