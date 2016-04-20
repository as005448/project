import os
import time, sys
from socket import *
from rtp import rtp
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
    hostAddress = '127.0.0.2'
    window = 2

    rtpProtocol = rtp(hostAddress, 7778, serverIP, desPort, None, True)
    clientProtocol = RecvThread(rtpProtocol)
    clientProtocol.start()
    try:
        rtpProtocol.connect()
    except Exception, e:
        print e
        clientProtocol.stop()
        rtpProtocol.socket.close()
        rtpProtocol = None
        return

    rtpProtocol.setWindowSize(window)
    rtpProtocol.setTimeOut(2)
    while True:
        try:
            # Send data
            rtpProtocol.sendAll(query)
            # receive data and server address
            data = rtpProtocol.recv()
            # print what we get from server
            print data[17::]
            break
        except Exception, e:
            print e
    # close socket when we finish
    if rtpProtocol != None:
        rtpProtocol.close()
        clientProtocol.stop()
        rtpProtocol.socket.close()
        rtpProtocol = None

if __name__ == "__main__": main()