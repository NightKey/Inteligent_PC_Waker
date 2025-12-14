from os import system as run
from time import sleep
from platform import system
import socket
import json
import threading
import tkinter as tk
from uuid import getnode as get_mac
from hashlib import sha256

def gma() -> str:
    address = hex(get_mac())[2:]
    return ":".join(f"{address[i]}{address[i+1]}" for i in range(0, len(address), 2))

DO = True
DONT = False
IP = None
MAC = gma()
COMMAND = None
THREAD_RUNNING = False
window = None

class UI:
    def __init__(self, text, delay):
        try:
            self.counter = int(delay)
        except Exception:
            self.counter = 30

        self.text = text
        self.is_running = True
        self.closed = False
        self.result = DONT

        self.root = tk.Tk()
        self.root.title("Warning")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.withdraw()

        frame1 = tk.Frame(self.root)
        frame1.pack(padx=10, pady=5)

        tk.Label(frame1, text=f"The pc will {text} after").pack(side="left")
        self.counter_label = tk.Label(frame1, text=str(self.counter))
        self.counter_label.pack(side="left", padx=5)
        tk.Label(frame1, text="seconds").pack(side="left")

        frame2 = tk.Frame(self.root)
        frame2.pack(pady=5)

        tk.Button(frame2, text=f"{text} now", command=lambda: self.work("SKIP")).pack(side="left", padx=5)
        tk.Button(frame2, text="Cancel", command=lambda: self.work("CANCLE")).pack(side="left", padx=5)

        frame3 = tk.Frame(self.root)
        frame3.pack(pady=5)

        self.amount = tk.StringVar(value="1")
        self.type_ = tk.StringVar(value="s")

        tk.OptionMenu(frame3, self.amount, "1", "5", "10", "20", "50").pack(side="left")
        tk.OptionMenu(frame3, self.type_, "s", "m", "h").pack(side="left")
        tk.Button(frame3, text="Increment", command=lambda: self.work("INC")).pack(side="left", padx=5)
        tk.Button(frame3, text="Decrement", command=lambda: self.work("DEC")).pack(side="left", padx=5)

    def _on_close(self):
        self.last_event = "CANCLE"

    def request_close(self):
        self.is_running = False

    def request_time_change(self, time):
        self.counter += time

    def count_down(self):
        self.counter -= 1
        self.root.after(0, lambda: self.counter_label.config(text=str(self.counter)))
        if self.counter <= 0:
            self.result = DO
            self.close()
        return self.result

    def close(self):
        if not self.is_running and self.closed: return
        self.is_running = False
        self.closed = True
        self.root.withdraw()
        self.root.destroy()

    def work(self, event):
        if event in ("CANCLE", "WINDOW_CLOSED"):
            self.close()
            self.result = DONT

        elif event == "INC":
            time = int(self.amount.get())
            if self.type_.get() == "m":
                time *= 60
            elif self.type_.get() == "h":
                time *= 3600
            self.request_time_change(time)

        elif event == "DEC":
            time = int(self.amount.get())
            if self.type_.get() == "m":
                time *= 60
            elif self.type_.get() == "h":
                time *= 3600
            self.request_time_change(-time)

        elif event == "SKIP":
            self.close()
            self.result = DO

    def show(self):
        self.root.deiconify()
        self.root.mainloop()


def counter(window):
    while THREAD_RUNNING:
        if window.count_down():
            print("Count down finished!")
        sleep(1)


def get_ip():
    global IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    IP = s.getsockname()[0]
    s.close()


def retrive(_socket: socket):
    ret = ""
    try:
        while True:
            try:
                size = int(_socket.recv(1).decode('utf-8'))
                data = _socket.recv(size).decode('utf-8')
                if data == '\n':
                    break
                ret += data
            except TimeoutError:
                pass
            except Exception as ex:
                print(f"Exception occured during retriving: {ex}")
        print(f'Message: {ret}')
        return json.loads(ret)
    except Exception as ex:
        print(ex)
        return None


def execute_command(connection):
    global window
    if COMMAND is not None:
        globals()["THREAD_RUNNING"] = False
        window.request_close()
        try:
            connection.send('1'.encode(encoding='utf-8'))
            print("Command finish sent")
            while not window.closed:
                sleep(1)
        except Exception as ex:
            print("Command ACK failed")
            print(ex)
        run(COMMAND)


if __name__ == "__main__":
    shutdown = sha256(f"SHUTDOWN{MAC}".encode('utf-8')).hexdigest()
    _sleep = sha256(f"SLEEP{MAC}".encode('utf-8')).hexdigest()
    restart = sha256(f"RESTART{MAC}".encode('utf-8')).hexdigest()
    print(f"Shutdown: {shutdown}")
    print(f'Sleep: {_sleep}')
    print(f'Restart: {restart}')
    print(f'MAC: {MAC}')
    get_ip()
    _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _socket.bind((IP, 666))
    _socket.listen()
    while True:
        conn, _ = _socket.accept()
        command = retrive(conn)
        conn.settimeout(0.5)
        delay = retrive(conn)
        if command == shutdown:
            if system() == "Windows":
                globals()["COMMAND"] = "shutdown /s /t 10"
            else:
                globals()["COMMAND"] = "sleep 10; systemctl poweroff"
            globals()["THREAD_RUNNING"] = True
            window = UI("Shutdown", delay)
        elif command == _sleep:
            if system() == 'Windows':
                globals()[
                    "COMMAND"] = "timeout 10 & rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
            else:
                globals()["COMMAND"] = "sleep 10; systemctl suspend"
            globals()["THREAD_RUNNING"] = True
            window = UI("Sleep", delay)
        elif command == restart:
            if system() == "Windows":
                globals()["COMMAND"] = "shutdown /r /t 10"
            else:
                globals()["COMMAND"] = "sleep 10; systemctl reboot"
            globals()["THREAD_RUNNING"] = True
            window = UI("Restart", delay)
        conn.send('1'.encode(encoding='utf-8'))
        print("ACK sent")
        print(f"Selected command: {COMMAND}")
        if delay == 0:
            window.close()
            execute_command(conn)
        else:
            bg = threading.Thread(target=counter, args=[window, ])
            bg.name = "COUNTER"
            bg.start()
            window.show()
            if window.result:
                print("WindowShow returned True")
                execute_command(conn)
                window.close()
            else:
                print("WindowShow returned False")
                window.close()
                conn.send('0'.encode(encoding='utf-8'))
                globals()["COMMAND"] = None
                globals()["THREAD_RUNNING"] = False
                del bg
