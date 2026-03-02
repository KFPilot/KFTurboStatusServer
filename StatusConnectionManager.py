#!/usr/bin/env python3

# Killing Floor Turbo Status Connection Manager
# Accepts connections on a defined port and prints received payloads.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import signal
import sys
import json
import socket
import threading
from argparse import ArgumentParser

parser = ArgumentParser(description="Killing Floor Turbo Status Connection Manager. Accepts connections and prints received payloads.")
parser.add_argument("-p", "--port", dest="port", type=int, required=True,
                    help="Port to bind to (required).", metavar="PORT")
parser.add_argument("-c", "--con", dest="maxcon", type=int,
                    help="Max number of connections for the server socket. Default is 10.", metavar="CON", default=10)

try:
    args = parser.parse_args()
except SystemExit as e:
    if e.code != 0:
        print("\nError: Missing required arguments or invalid inputs.")
        exit(1)

ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ServerSocket.bind(("0.0.0.0", int(args.port)))
ServerSocket.listen(int(args.maxcon))

def ShutdownServer(signal_received, frame):
    print("Shutting down server...")
    ServerSocket.close()
    sys.exit(0)

signal.signal(signal.SIGINT, ShutdownServer)
signal.signal(signal.SIGTERM, ShutdownServer)

def HandleConnection(ClientSocket, Address):
    print("Started thread for connection at "+str(Address))
    Buffer = ""
    try:
        while (True):
            Data = ClientSocket.recv(8192)
            StringData = Data.decode('utf-8')

            if (StringData == ""):
                break

            Buffer += StringData
            Lines = Buffer.split("\r\n")
            Buffer = Lines.pop()

            for Line in Lines:
                Line = Line.strip()

                if (Line == "" or Line == "keepalive"):
                    continue

                try:
                    JsonData = json.loads(Line)
                    print(json.dumps(JsonData, indent=2))
                except Exception:
                    print(Line)
    except Exception as Error:
        print("Error "+str(Error)+" occurred for connection at "+str(Address))
    print("Stopping thread for connection at "+str(Address))

def StartServer():
    print("Started server on port "+str(args.port)+" and waiting for connections...")
    while (True):
        (ClientSocket, Address) = ServerSocket.accept()
        print("Accepted connection...")
        ClientSocket.settimeout(30)
        ConnectionThread = threading.Thread(target=HandleConnection, args=(ClientSocket, Address))
        ConnectionThread.daemon = True
        ConnectionThread.start()

try:
    ServerThread = threading.Thread(target=StartServer)
    ServerThread.daemon = True
    ServerThread.start()
except:
    ShutdownServer(None, None)

# Keep main thread alive.
import time
while (True):
    time.sleep(1)
