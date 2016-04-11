#!/usr/bin/env python

from time import time

# RxP Timer class, deal with time out issues
class RxPTimer:
    
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
