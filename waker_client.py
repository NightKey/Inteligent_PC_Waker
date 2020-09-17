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
        self.window = sg.Window("Warning", layout)
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
    global ip
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()

def retrive(socket):
    ret = ""
    try:
        while True: 
            size = int(socket.recv(1).decode('utf-8'))
            data = socket.recv(size).decode('utf-8')
            if data == '\n':
                break
            ret += data
        return json.loads(ret)
    except Exception as ex:
        print(ex)
        return None

def execute_command():
    if COMMAND is not None: run(COMMAND)

if __name__ == "__main__":
    while True:
        get_ip()
        _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _socket.bind((IP, 666))
        command = retrive(_socket)
        if command == sha256(f"SHUTDOWN{MAC}").hexdigest():
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
        elif command == sha256(f"SLEEP{MAC}").hexdigest():
            globals()["COMMAND"] = "shutdown /h /t 0"
            globals()["THREAD_RUNNING"] = True
            window = UI("sleep")
            bg = threading.Thread(target=counter, args=[window,])
            bg.name = "COUNTER"
            bg.start()
            if window.show(): execute_command()
            else:
                globals()["COMMAND"] = None
                globals()["THREAD_RUNNING"] = True