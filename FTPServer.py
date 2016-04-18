#!/usr/bin/env python

import sys
from socket import *
from RxP import RxP
from threads import RecvThread

#  FxAServer
#  deals with the server side command line arguments and supports the following functions:
#  start server
#  Window (w) - change window size, default window size = 2
#  terminate - terminate the server
# host port, window size

def main():

    print ("Server Starts")

    # Handling the argument
    arg = sys.argv
    if len(arg) != 3:
        print 'Invalid command. Please try again.'
        sys.exit()

    log = "output-server.txt"

    #pass the command line arguments
    try:
        hostPort = int(arg[1])
    except ValueError:
        print 'Invalid command. Please try again.'
        sys.exit()
    # validate
    if not 0 < hostPort < 65536:
        print 'Invalid port number. Please try again.'
        sys.exit()

    #Server IP address
    serverIP = '127.0.0.1'
    # validate
    if not _validIP(serverIP):
        print 'IP address is not valid, please try again'
        sys.exit()

    window = arg[2]
    # netEmu port number
    # try:
    #     netEmuPort = int(arg[3])
    # except ValueError:
    #     print 'Invalid command. Please try again.'
    #     sys.exit()
    # validate
    # if not 0 < netEmuPort < 65536:
    #     print 'Invalid port number. Please try again.'
    #     sys.exit()


    rxpProtocol = RxP(serverIP, hostPort, 0, 0, None, False)
    serverProtocol = RecvThread(rxpProtocol)
    serverProtocol.start()
    rxpProtocol.setWindowSize(window)
    # execute user's commend
    while (True):
        Sinput = raw_input("close - to terminate the server\n")
        if Sinput.__eq__("close"):
            rxpProtocol.close()
            serverProtocol.stop()
            for thread in rxpProtocol.threads:
                thread.stop()
            print ("Server is closed")
            break


# check IP format validation
def _validIP(address):
    parts = address.split(".")
    if len(parts) != 4:
        return False
    for num in parts:
        try:
            part = int(num)
        except ValueError:
            print 'Invalid IP. Please try again.'
            sys.exit()
        if not 0 <= part <= 255:
            return False
    return True


if __name__ == "__main__":
    main()