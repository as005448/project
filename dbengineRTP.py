import os
import traceback
import time, sys
from socket import *
from rtp import rtp
from threads import RecvThread, SendThread

# hard code database!
database = {"903076259" : {"first_name" : "Anthony", "last_name" : "Peterson", "quality_points" : "231", "gpa_hours" : "63", "gpa" : "3.666667", "id" : "903076259"},
            "903084074" : {"first_name" : "Richard", "last_name" : "Harris", "quality_points" : "236", "gpa_hours" : "66", "gpa" : "3.575758", "id" : "903084074"},
            "903077650" : {"first_name" : "Joe", "last_name" : "Miller", "quality_points" : "224", "gpa_hours" : "65", "gpa" : "3.446154", "id" : "903077650"},
            "903083691" : {"first_name" : "Todd", "last_name" : "Collins", "quality_points" : "218", "gpa_hours" : "56", "gpa" : "3.892857", "id" : "903083691"},
            "903082265" : {"first_name" : "Laura", "last_name" : "Stewart", "quality_points" : "207", "gpa_hours" : "64", "gpa" : "3.234375", "id" : "903082265"},
            "903075951" : {"first_name" : "Marie", "last_name" : "Cox", "quality_points" : "246", "gpa_hours" : "63", "gpa" : "3.904762", "id" : "903075951"},
            "903084336" : {"first_name" : "Stephen", "last_name" : "Baker", "quality_points" : "234", "gpa_hours" : "66", "gpa" : "3.545455", "id" : "903084336"},
}

def main() :
    # handle illegal numer of arguments
    if len(sys.argv) != 2 :
        print >> sys.stderr, 'illegal number of arguments'
        sys.exit()

    port = sys.argv[1]
    # check if port number is not digit
    if not port.isdigit() :
        print >> sys.stderr, 'illegal port number'
        sys.exit()

    port = int(sys.argv[1])
    serverIP = '127.0.0.1'
    # hard-code database
    
    window = 2
    # Create a UDP socket
    rtpProtocol = rtp(serverIP, port, 0, 0, None, False)
    serverProtocol = RecvThread(rtpProtocol)
    serverProtocol.start()
    rtpProtocol.setWindowSize(window)
    
    while True:
        clientSocket = rtpProtocol.accept()
        try:
            data = clientSocket.recv()
            # if header of message is not "queryExecutionRequest", send error message
            if "queryExecution" not in data:
                clientSocket.sendAll("(queryExecution) unknown request. please send query execution request\n")
                continue
            # execute query and send back result
            print data[17::]
            result = execute(data[17::])
            clientSocket.sendAll(result)
        except Exception, exc:
            print(traceback.format_exc())
    
    rtpProtocol.close()
    serverProtocol.stop()
    for thread in rtpProtocol.threads:
        thread.stop()


def execute(query) :
    ret = '(queryExecution) From server: '
    query = query.strip().split(' ')
    
    # handle id not in database
    if query[0] not in database:
        return '(queryExecution) From server: the student ID is not present in this database'
        
    row = database[query[0]]
    # loop to output all required attributes
    for coln in range(1, len(query)) :
        col = query[coln].lower()
        # handle attribute not in databse
        if col not in row:
            return '(queryExecution) From server: non-existing attribute "' + col + '"'

        ret += col + ': ' + row[col] + ', '
    
    return bytearray(ret[:-2], 'utf8')

if __name__ == "__main__": main()