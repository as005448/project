#!/usr/bin/env python
import sys
import time as stime
from time import time
from threads import SendThread
from socket import *
from collections import deque
from crc import crc16xmodem
import unicodedata, sys
import Queue
import threading

class rtp:
    dataMax = 255  # total bytes in a packet

    # refer to rtpHeader class for more info
    def __init__(self, hostAddress, hostPort, destAddress, destPort, udpSocket, isClientSocket):
        self.dict = dict()
        self.hostAddress = hostAddress
        self.destAddress = destAddress
        self.hostPort = hostPort
        self.destPort = destPort
        self.isClientSocket = isClientSocket
        if (udpSocket is None) :
            self.socket = socket(AF_INET, SOCK_DGRAM)
            self.socket.bind((self.hostAddress, self.hostPort))
        else :
            self.socket = udpSocket
        self.header = rtpHeader(destPort, destPort, 0, 0)
        self.cntBit = 0  # stands for connection state(3 way handshake)
        self.getBit = 0  # get file
        self.postBit = 0  # post file
        self.queryBit = 0
        self.rtpWindow = rtpWindow()
        self.timer = timer()
        self.buffer = deque()  # buffer to store data
        self.output = None  # output file
        self.recvFileIndex = 0  # current index of receiving file
        self.threads = []  # supports multiple get request
        self.timeout = 3 * 60
        self.newConnectionQueue = Queue.Queue()
        self.messageQueue = Queue.Queue()
        self.lock = threading.Lock()
    #  When user type in "connect" command Establish handshake connection with
    #  host by sending SYN messages. Handling the time out situation 
    #  cntBit = 0 : listening for connection 
    #  cntBit = 1 : received first SYN = 1 packet
    def connect(self):
        print 'Start to connect'
        self.header.cnt = True
        self.header.syn = True
        self.header.seqNum = 0
        self.send(None)
        self.timer.start()
        tryNumber = 3
        print 'Send first SYN segment with SYN = 1'

        while self.cntBit == 0 and tryNumber != 0:
            if self.timer.isTimeout():
                tryNumber = tryNumber - 1
                self.header.syn = True
                self.header.seqNum = 0
                self.send(None)
                print 'Resend first SYN segment with SYN = 1'
                self.timer.start()

        if tryNumber == 0 and self.cntBit == 0:
            raise Exception('can not connect to the server')

        tryNumber = 3
        while self.cntBit == 1 and tryNumber != 0:
            if self.timer.isTimeout():
                tryNumber = tryNumber - 1
                self.header.syn = False
                self.header.seqNum = 1
                self.send(None)
                print 'Resend segment with SYN = 0'
                self.timer.start()

        if tryNumber == 0 and self.cntBit == 1:
            raise Exception('can not connect to the server')
        self.header.cnt = False
        print '>>>>>>>>>>>Connection established<<<<<<<<<<<<<'

    #  When receive "disconnect" command,it will close connection. 
    #  cntBit = 2 : connection established. 
    #  cntBit = 3 : closing wait
    def close(self):
        self.header.cnt = True
        self.header.fin = True
        self.header.seqNum = 0
        self.send(None)
        print 'Send first FIN segment with FIN = 1'
        self.timer.start()

        while self.cntBit == 2:
            if self.timer.isTimeout():
                self.header.fin = True
                self.header.seqNum = 0
                self.send(None)
                print 'Resend first FIN segment with FIN = 1'
                self.timer.start()

        while self.cntBit == 3:
            if self.timer.isTimeout():
                self.header.fin = False
                self.header.seqNum = 1
                self.send(None)
                print 'Resend first FIN segment with FIN = 0'
                self.timer.start()

        self.header.cnt = False
        print '>>>>>>>>>Connection Closed<<<<<<<<<<<<'
        self.reset()

    # Listening the incoming request including connect request, get, post, and
    # data action by checking the received packet contents
    def listen(self, event):
        print 'start to listen'
        while True and not event.stopped():
            self.socket.settimeout(1)
            try:
                recvPacket, address = self.socket.recvfrom(900)
            except IOError:
                continue
            packet = bytearray(recvPacket)

            if self.validateChecksum(packet):
                clientSocket = None
                if self.isClientSocket:
                    clientSocket = self
                else:
                    clientSocket = self.acceptPackage(address)

                tempHeader = clientSocket.getHeader(packet)
                if tempHeader.cnt:
                    print 'Received control packet'
                    connectState = clientSocket.recvCntPkt(packet)
                    if connectState == 2 and not self.isClientSocket:
                        self.newConnectionQueue.put(self.dict[address])
                    elif connectState == 3 and not self.isClientSocket:
                        self.dict.pop(address, None)
                elif tempHeader.get:
                    print 'Received get packet'
                    clientSocket.recvGetPkt(packet)
                elif tempHeader.post:
                    print 'Received post packet'
                    clientSocket.recvPostPkt(packet)
                elif tempHeader.dat:
                    print 'Received data packet'
                    clientSocket.recvDataPkt(packet)
                elif tempHeader.query:
                    print 'Received query packet'
                    clientSocket.recvQueryPkt(packet)
            else:
                print 'Received corrupted data, packet dropped.'

    def acceptPackage(self, address):
        clientSocket = None
        if address in self.dict:
            clientSocket = self.dict[address]
        else:
            clientSocket = rtp(self.hostAddress, self.hostPort, address[0], address[1], self.socket, False)
            self.dict[address] = clientSocket
            print 'create ClientSocket'
        return clientSocket

    def accept(self):
        return self.newConnectionQueue.get(block=True)

    def setTimeOut(self, timeout):
        self.timeout = timeout

    def recv(self):
        return self.messageQueue.get(block=True, timeout=self.timeout)

    def sendAll(self, data):

        tryNumber = 20
        if self.cntBit == 2:
            nameBytes = bytearray(data)
            self.header.query = True
            self.header.seqNum = 0
            self.send(nameBytes)
            self.header.query = False
            print 'Sending Query request'
            self.timer.start()

            while self.queryBit == 0 and tryNumber != 0:
                if self.timer.isTimeout():
                    tryNumber = tryNumber - 1
                    self.header.query = True
                    self.header.seqNum = 0
                    self.send(nameBytes)
                    self.header.query = False
                    print 'Resend Query request'
                    self.timer.start()

            if self.queryBit == 0 and tryNumber == 0:
                raise Exception('send unsuccess')
        else:
            print 'No connection found'

    # reset all setting
    def reset(self):
        self.rtpWindow = rtpWindow()
        self.timer = timer()
        self.cntBit = 0
        self.getBit = 0
        self.postBit = 0
        self.buffer = deque()
        self.recvFileIndex = 0
        self.output = None

    #  client uses getFile method to get a file from server side protocol sends
    #  the requested file to client side
    def getFile(self, filename):
        if self.cntBit == 2:
            self.lock.acquire()
            nameBytes = bytearray(filename)
            self.header.get = True
            self.header.seqNum = 0
            self.send(nameBytes)
            self.header.get = False
            self.lock.release()
            print 'Sending Get request'
            self.timer.start()

            while self.getBit == 0:
                if self.timer.isTimeout():
                    self.lock.acquire()
                    self.header.get = True
                    self.header.seqNum = 0
                    self.send(nameBytes)
                    self.header.get = False
                    self.lock.release()
                    print 'Resend Get request'
                    self.timer.start()
            print 'Start to receive file'

        else:
            print 'No connection found'

    # Protocol send incoming data into Datagrams through UDP socket the data
    # need to be add check sum before sending
    def send(self, data):
        print 'sending seq#: %d' % self.header.seqNum
        self.header.ack = False
        datagram = self.pack(self.header.getHeader(), data)
        datagram = self.addChecksum(datagram)
        self.socket.sendto(datagram, (self.destAddress, self.destPort))

    # Getting header's ack number and add check sum to this ack number then
    # send new ACK through UDP socket
    def sendAck(self):
        print 'acking num: %d' % self.header.ackNum
        self.header.ack = True
        datagram = self.addChecksum(self.header.getHeader())
        self.socket.sendto(datagram, (self.destAddress, self.destPort))

    # Getting the header information from received data
    def getHeader(self, datagram):
        tmpHeader = rtpHeader()
        tmpHeader.headerFromBytes(datagram)
        return tmpHeader

    # Packing header array and data array into a new array, so that we can send
    # this new data to the UDP socket
    def pack(self,header, data):
        if data:
            result = header + data
            return result
        else:
            return header

    # Sending file to the server.
    def postFile(self, filename, event):
        if self.cntBit == 2:
            self.lock.acquire()
            nameBytes = bytearray(filename)
            self.header.post = True
            self.header.seqNum = 0
            self.send(nameBytes)
            self.header.post = False
            self.lock.release()
            print 'Sending Post request'
            self.timer.start()

            while self.postBit == 0 and not event.stopped():
                if self.timer.isTimeout():
                    self.lock.acquire()
                    self.header.post = True
                    self.header.seqNum = 0
                    self.send(nameBytes)
                    self.header.post = False
                    self.lock.release()
                    print 'Resend Post request'
                    self.timer.start()
            if event.stopped():
                print 'Post file interrupted'
                return

            try:
                readFile = open(filename, "rb")
            except:
                print ("file not found. Please type in correct filename")
                sys.exit()
            fileBytes = bytearray(readFile.read())
            bufferSize = rtp.dataMax - rtpHeader.headerLen
            fileSize = len(fileBytes)
            fileIndex = 0
            self.timer.start()

            while (fileIndex < fileSize or len(self.buffer) > 0) and not event.stopped():
                if self.timer.isTimeout():
                    self.rtpWindow.nextToSend = self.rtpWindow.startWindow
                    self.timer.start()
                    for i in range(len(self.buffer)):
                        if fileIndex >= fileSize:
                            if i == len(self.buffer) - 1:
                                self.header.end = True
                        seq = self.rtpWindow.nextToSend
                        self.lock.acquire()
                        self.header.seqNum = seq
                        self.header.dat = True
                        try:
                            self.send(self.buffer[i])
                        except:
                            print ("Corruption or Reodring rate too high, connection fails")
                            sys.exit()
                        self.header.dat = False
                        self.header.end = False
                        self.lock.release()
                        self.rtpWindow.nextToSend = seq + 1

                if self.rtpWindow.nextToSend <= self.rtpWindow.endWindow and fileIndex < fileSize:
                    data = []
                    if fileIndex + bufferSize > fileSize:
                        data = fileBytes[fileIndex:fileSize]
                    else:
                        data = fileBytes[fileIndex:fileIndex + bufferSize]
                    fileIndex += bufferSize

                    if fileIndex >= fileSize:
                        self.header.end = True
                    seq = self.rtpWindow.nextToSend
                    self.lock.acquire()
                    self.header.seqNum = seq
                    self.header.dat = True
                    self.send(data)
                    self.header.dat = False
                    self.header.end = False
                    self.lock.release()
                    self.rtpWindow.nextToSend = seq + 1
                    self.buffer.append(data)

            readFile.close()
            self.postBit = 0
            self.getBit = 0
            self.header.end = False
            print '>>>>>>>>>>>File transfer completed<<<<<<<<<<<<'

            if event.stopped():
                print 'Post file interrupted'
        else:
            print 'No connection found'

    # Handle received data transmission packet.
    def recvDataPkt(self, packet):
        self.lock.acquire()
        tmpHeader = self.getHeader(packet)
        if tmpHeader.ack:
            print 'Received Data ACK Num: %d' % tmpHeader.ackNum

            if tmpHeader.ackNum == self.rtpWindow.startWindow:
                self.timer.start()
                self.rtpWindow.startWindow += 1
                self.rtpWindow.endWindow += 1
                self.buffer.popleft()
        else:
            if self.output == None:
                print 'Output is not ready'
            else:
                if self.recvFileIndex == tmpHeader.seqNum:
                    content = packet[rtpHeader.headerLen:]
                    self.output.write(content)
                    self.recvFileIndex += 1
                    self.output.flush()

                    if tmpHeader.end:
                        self.output.close()
                        print '>>>>>>>>>>>>File transfer completed<<<<<<<<<<<<<'

                seq = tmpHeader.seqNum
                if self.recvFileIndex > seq:
                    self.header.ackNum = seq
                elif self.recvFileIndex < seq:
                    if self.recvFileIndex != 0:
                        self.header.ackNum = self.recvFileIndex - 1
                    else:
                        self.header.ackNum = 0
                self.header.dat = True
                self.sendAck()
                self.header.dat = False
        self.lock.release()

    # Handle get file packet
    def recvGetPkt(self, packet):
        self.lock.acquire()
        tmpHeader = self.getHeader(packet)
        seq = tmpHeader.seqNum
        self.header.ackNum = seq
        
        if tmpHeader.ack:
            self.getBit = 1
        else:
            if self.getBit == 0:
                content = packet[rtpHeader.headerLen:]
                uniFilename = self.bytesToString(content)
                filename = unicodedata.normalize('NFKD', uniFilename).encode('utf-8','ignore')
                self.getBit = 1
                sendTread = SendThread(self, filename)
                self.threads.append(sendTread)
                sendTread.start()
            self.header.get = True
            self.sendAck()
            self.header.get = False
        self.lock.release()

    # Handle query packet
    def recvQueryPkt(self, packet):
        self.lock.acquire()
        tmpHeader = self.getHeader(packet)
        seq = tmpHeader.seqNum
        self.header.ackNum = seq

        if tmpHeader.ack:
            self.queryBit = 1
        else:
            content = packet[rtpHeader.headerLen:]
            query = self.bytesToString(content)
            self.messageQueue.put(query)
            self.header.query = True
            self.sendAck()
            self.header.query = False
        self.lock.release()

    # Handle post file packet
    def recvPostPkt(self, packet):
        self.lock.acquire()
        content = packet[rtpHeader.headerLen:]
        tmpHeader = self.getHeader(packet)
        seq = tmpHeader.seqNum
        self.header.ackNum = seq

        if self.postBit == 0:
            if tmpHeader.ack:
                self.postBit = 1
            else:
                content = packet[rtpHeader.headerLen:]
                fileType = self.bytesToString(content).split('.', 1)[1]
                if self.isClientSocket:
                    filename = 'get_F' + '.' + fileType
                else:
                    filename = 'post_G' + '.' + fileType
                print filename
                try:
                    self.output = open(filename, "ab")
                except:
                    print ("file not found. Please type correct filename")
                    sys.exit()
                self.header.post = True
                print 'sending post ack'
                self.sendAck()
                self.header.post = False
        self.lock.release()
    # receive connection establishment packet
    # 3 way handshake
    # closing wait
    # connectState == 1, nothing special
    # connectState == 2, connection established
    # connectState == 3, disconnected
    def recvCntPkt(self, packet):
        self.lock.acquire()
        connectState = 1
        tmpHeader = self.getHeader(packet)
        seq = tmpHeader.seqNum
        self.header.ackNum = seq

        if self.cntBit == 0:
            if tmpHeader.syn:
                print 'Received connection request SYN segment with SYN = 1'
                self.header.cnt = True
                self.sendAck()
                self.cntBit = 1
            elif self.header.syn and tmpHeader.ack:
                self.header.syn = False
                self.header.seqNum = 1
                self.send(None)
                print 'Received first SYN ack, sending second msg[SYN=0]'
                self.cntBit = 1
            elif not tmpHeader.fin and not tmpHeader.ack:
                print 'server received SYN from client, and sent back ACK to client'
                self.header.cnt = True
                self.sendAck()
                self.header.cnt = False
        elif self.cntBit == 1:
            if not tmpHeader.ack and not tmpHeader.syn:
                self.cntBit = 2
                self.sendAck()
                self.header.cnt = False
                connectState = 2
                print '>>>>>>>>>>>>Connection established<<<<<<<<<<<<<'
            if tmpHeader.seqNum == 0 and tmpHeader.syn:
                print 'Second SYN initialization'
                self.header.cnt = True
                self.sendAck()
                self.header.cnt = False
            if tmpHeader.ack:
                self.cntBit = 2
        elif self.cntBit == 2:
            if tmpHeader.fin:
                print 'Received connection closing request with FIN = 1'
                self.header.cnt = True
                self.sendAck()
                self.cntBit = 3
            elif self.header.fin and tmpHeader.ack:
                self.header.fin = False
                self.header.seqNum = 1
                self.send(None)
                print 'Received first FIN ack, sending second packet with FIN = 0'
                self.cntBit = 3
            elif not tmpHeader.ack and not tmpHeader.syn:
                self.header.cnt = True
                self.sendAck()
                self.header.cnt = False
        elif self.cntBit == 3:
            if not tmpHeader.ack and not tmpHeader.fin:
                self.cntBit = 0
                self.sendAck()
                self.header.cnt = False
                self.reset()
                connectState = 3
                print '>>>>>>>>>Connection Close<<<<<<<<<<<'
            elif not tmpHeader.seqNum and tmpHeader.fin:
                self.header.cnt = True
                self.sendAck()
                self.header.cnt = False
            elif tmpHeader.ack:
                self.cntBit = 0
        self.lock.release()
        return connectState

    # set the window size for protocol
    def setWindowSize(self, windowSize):
        if self.cntBit == 2:
            self.rtpWindow.windowSize = windowSize
            print 'The window size is set to: %d' % windowSize
        else:
            print 'Please initialize connection.'

    # Convert the ASCII byte[] data into String
    def bytesToString(self, data):
        return data.decode('utf-8')

    # Before sending the packet, we have to add a check sum field into each
    # packet to make sure the correction of data
    def addChecksum(self, packet):
        data = ''
        packet[14] = 0
        packet[15] = 0
        for byte in packet:
            data += str(byte)
        checksum = crc16xmodem(data)
        packet[14] = checksum >> 8
        packet[15] = checksum & 0xFF
        return packet

    # Using this check sum function to check every received packet's corruption
    def validateChecksum(self, packet):
        correct = False
        data = ''
        firstB = packet[14]
        secondB = packet[15]
        packet[14] = 0
        packet[15] = 0
        for byte in packet:
            data += str(byte)
        checksum = crc16xmodem(data)
        msb = checksum >> 8
        lsb = checksum & 0xFF
        if msb == firstB and lsb == secondB:
            correct = True
        return correct

class timer:
    
    def __init__(self):
        self.time = 0
        self.timeout = 0.6

    def start(self):
        self.time = time()

#   calculate the time difference between current time
#   and the time when timer starts, in seconds
    def getTime(self):
        return self.time - time()

#   Checks if timeout occurs
    def isTimeout(self):
        if time() - self.time < self.timeout:
            return False
        else:
            return True

#!/usr/bin/env python

# header class for rtp
class rtpHeader:
    headerLen = 17 # header length

    def __init__(self, sourcePort=-1, destPort=-1, seqNum=0, ackNum=0):
        self.sourcePort = sourcePort # The port number of the packet source
        self.destPort = destPort # The port number of the packet destination
        self.seqNum = seqNum # Current sequence number
        self.ackNum = ackNum # Current ack number
        self.ack = False # bit to indicate package is ack package
        self.end = False # bit to indicate if the package is the last package
        self.dat = False # bit to indicate if the package is data package
        self.cnt = False # bit to indicate if the package contains connection data
        self.syn = False # bit to initiate a connection
        self.fin = False # bit to close a connection
        self.get = False # bit for get file request
        self.post = False # bit for post file request
        self.checksum = 0 # Checksum field
        self.query = False
        self.header = bytearray(17) # Byte array of header for sending

    # convert all instance variables of rtp header into byte array
    def setHeader(self):
        self.header[0] = (self.sourcePort >> 8) & 0xFF
        self.header[1] = self.sourcePort & 0xFF
        self.header[2] = (self.destPort >> 8) & 0xFF
        self.header[3] = self.destPort & 0xFF
        self.header[4] = (self.seqNum >> 24) & 0xFF
        self.header[5] = (self.seqNum >> 16) & 0xFF
        self.header[6] = (self.seqNum >> 8) & 0xFF
        self.header[7] = self.seqNum & 0xFF
        self.header[8] = (self.ackNum) >> 24 & 0xFF
        self.header[9] = (self.ackNum) >> 16 & 0xFF
        self.header[10] = (self.ackNum) >> 8 & 0xFF
        self.header[11] = self.ackNum & 0xFF
        self.header[12] = rtpHeader.headerLen & 0xFF
        self.header[13] = 0

        if self.fin:
            self.header[13] = self.header[13] | 0x1
        if self.syn:
            self.header[13] = self.header[13] | 0x2
        if self.cnt:
            self.header[13] = self.header[13] | 0x4
        if self.ack:
            self.header[13] = self.header[13] | 0x10
        if self.end:
            self.header[13] = self.header[13] | 0x20
        if self.get:
            self.header[13] = self.header[13] | 0x40
        if self.post:
            self.header[13] = self.header[13] | 0x80
        if self.dat:
            self.header[13] = self.header[13] | 0x8

        self.header[14] = (self.checksum >> 8) & 0xFF
        self.header[15] = self.checksum & 0xFF
        if self.query:
            self.header[16] = 0x1
        return self.header
    
    # given a byte array, convert it into a rtpHeader
    def headerFromBytes(self, header):
        self.sourcePort = (header[0] << 8 | (0 | 0xFF)) & header[1]
        self.destPort = (header[2] << 8 | (0 | 0xFF)) & header[3]
        self.seqNum = header[4] << 24 | header[5] << 16 | header[6] << 8 | (0 | 0xFF) & header[7]
        self.ackNum = header[8] << 24 | header[9] << 16 | header[10] << 8 | (0 | 0xFF) & header[11]

        if header[13] & 0x1 == 0x1:
            self.fin = True
        if header[13] & 0x2 == 0x2:
            self.syn = True
        if header[13] & 0x4 == 0x4:
            self.cnt = True
        if header[13] & 0x8 == 0x8:
            self.dat = True
        if header[13] & 0x10 == 0x10:
            self.ack = True
        if header[13] & 0x20 == 0x20:
            self.end = True
        if header[13] & 0x40 == 0x40:
            self.get = True
        if header[13] & 0x80 == 0x80:
            self.post = True
        self.checksum = header[14] << 8 | (0 | 0xFF) & header[15]
        if header[16] == 0x1:
            self.query = True

    def getHeader(self):
        return self.setHeader()

    def setHeaderFromBytes(self, header):
        self.header = header

class rtpWindow:

    def __init__(self):
        self.windowSize = 2
        self.startWindow = 0
        self.endWindow = self.windowSize - 1
        self.nextToSend = 0

