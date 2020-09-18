from os import system as run
from time import sleep
import socket, json, threading
import PySimpleGUI as sg
from getmac import get_mac_address as gma
from hashlib import sha256

DO = True
DONT = False
IP = None
MAC = gma()
COMMAND = None
THREAD_RUNNING = False

class UI:
    def __init__(self, text):
        self.counter = 30
        layout = [
            [sg.Text(f"The pc will {text} after"), sg.Text(str(self.counter), key="COUNTER"), sg.Text("secunds")],
            [sg.Button(f"{text} now", key="SKIP"), sg.Button("Cancle", key="CANCLE")]
        ]
        self.window = sg.Window("Warning", layout, finalize=True)
        self.read = self.window.read
        self.is_running = True
        
    def count_down(self):
        self.counter -= 1
        if self.counter < 0:
            return DO
        self.window["COUNTER"].Update(str(self.counter))
        return DONT

    def close(self):
        self.is_running = False
        self.window.Close()

    def work(self, event):
        if event == sg.WINDOW_CLOSED or event == "CANCLE":
            self.close()
            return DONT
        elif event == "SKIP":
            self.close()
            return DO

    def show(self):
        event, _ = self.read()
        return self.work(event)

def counter(window):
    while THREAD_RUNNING:
        if not window.count_down():
            sleep(1)
        else:
            execute_command()

def get_ip():
    global IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    IP = s.getsockname()[0]
    s.close()

def retrive(_socket):
    ret = ""
    try:
        while True: 
            size = int(_socket.recv(1).decode('utf-8'))
            data = _socket.recv(size).decode('utf-8')
            if data == '\n': break
            ret += data
        print(f'Message: {ret}')
        return json.loads(ret)
    except Exception as ex:
        print(ex)
        return None

def execute_command():
    if COMMAND is not None:
        globals()["THREAD_RUNNING"] = False
        run(COMMAND)

if __name__ == "__main__":
    shutdown=sha256(f"SHUTDOWN{MAC}".encode('utf-8')).hexdigest()
    print(f'Shutdown: {shutdown}')
    _sleep=sha256(f"SLEEP{MAC}".encode('utf-8')).hexdigest()
    print(f'Sleep: {_sleep}')
    print(f'MAC: {MAC}')
    get_ip()
    _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _socket.bind((IP, 666))
    _socket.listen()
    while True:
        conn, _ = _socket.accept()
        command = retrive(conn)
        if command == shutdown:
            globals()["COMMAND"] = "shutdown /s /t 0"
            globals()["THREAD_RUNNING"] = True
            window = UI("shutdown")
            bg = threading.Thread(target=counter, args=[window,])
            bg.name = "COUNTER"
            bg.start()
            if window.show(): execute_command()
            else:
                globals()["COMMAND"] = None
                globals()["THREAD_RUNNING"] = True
        elif command == _sleep:
            globals()["COMMAND"] = "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
            globals()["THREAD_RUNNING"] = True
            window = UI("sleep")
            bg = threading.Thread(target=counter, args=[window,])
            bg.name = "COUNTER"
            bg.start()
            if window.show(): execute_command()
            else:
                globals()["COMMAND"] = None
                globals()["THREAD_RUNNING"] = True