import os
import time, sys
from socket import *
from RxP import RxP
from threads import RecvThread, SendThread

def main() :
	# check if no enough number of arguments
    if len(sys.argv) < 4 :
        print >> sys.stderr, 'illegal number of arguments'
        sys.exit()

    # check if input contains ':' to separate ip and port
    if ':' not in sys.argv[1] :
        print "use : to split address and port number"
        sys.exit()

    address = sys.argv[1].split(':', 1)
    # check if port number is not digit
    if not address[1].isdigit() :
        print "invaild port number"
        sys.exit()
    # setup ip address
    serverIP = address[0]
    if address[0] == "localhost" :
        serverIP = "127.0.0.1"
    # use tryNumber to count down number of try after not reciving response
    tryNumber = 3
    # make up our query from arguments
    query = "(queryExecution) "
    for q in sys.argv[2::] :
        query += q + ' '

    # set timeout for socket 
    desPort = int(address[1])
    hostAddress = '127.0.0.1'
    window = 2

    rxpProtocol = RxP(hostAddress, 8888, serverIP, desPort, None, True)
    clientProtocol = RecvThread(rxpProtocol)
    clientProtocol.start()
    rxpProtocol.connect()
    rxpProtocol.setWindowSize(window)
    rxpProtocol.setTimeOut(2)
    while True :
        try:
            # Send data
            rxpProtocol.sendAll(query)
            # receive data and server address
            data = rxpProtocol.recv()
            # print what we get from server
            print data.replace("\n", "")
            break
        except Exception :
            # when timeout, we re-try for three times
            if tryNumber != 0 :
                print "The server has not answered in the last two seconds."
                print "retrying..."
                tryNumber = tryNumber - 1
            else :
                # after three re-try we give up
                print "error: can not get response"
                break
    # close socket when we finish
    if rxpProtocol != None:
        rxpProtocol.close()
        clientProtocol.stop()
        rxpProtocol.socket.close()
        rxpProtocol = None

if __name__ == "__main__": main()