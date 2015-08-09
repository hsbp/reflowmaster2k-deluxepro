import random
import serial
import time

class FakeSerial():

    def __init__(self):
        self._data = ""
        self._open = True

    def _genFrame(self):
        adcValue = random.randint(350, 1023)
        self._data = "\xFF" + chr(adcValue & 0xFF) + chr((adcValue >> 8) & 0xFF)

    def _checkOpen(self):
        if not self._open:
            raise serial.SerialException("Bad file descriptor")

    def inWaiting(self):
        self._checkOpen()
        return len(self._data)

    def write(self, b):
        pass

    def read(self, n):
        self._checkOpen()
        if not self._data:
            self._genFrame()
        val = self._data[:n]
        self._data = self._data[n:]
        for c in val:
            time.sleep(0.001)
        return val

    def close(self):
        self._open = False