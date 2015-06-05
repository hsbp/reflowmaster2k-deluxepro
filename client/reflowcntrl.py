import serial
import shh
import pid
import sys
import os
import threading
import uif
import visualizer
import time
import random

class ReflowControl:

    def __init__(self, portName, shhCoeffs=None, pidCoeffs=None, profile=None):
        self._shhConverter = None
        if shhCoeffs is None:
            shhCoeffs = (0.049182398851342568, -0.015880288085651714, 0.0018439776862060255, -7.5225149204180178e-05)
        if pidCoeffs is None:
            pidCoeffs = (30.0, 2.0, 7.0)
        if profile is None:
            profile = {"rampup": 6, "ts": 2 * 60, "Tsmin": 135, "Tsmax": 155, "tl": 150, "Tl": 183, "tp": 30, "Tp": 225, "rampdown": 10}
        self._profile = profile
        self._shhConverter = shh.SteinHaart(*shhCoeffs)
        self._pid = pid.Pid(self._updateTemp, self._setPwm, pidCoeffs)
        self._portName = portName
        if self._portName:
            self._serial = serial.Serial(port=self._portName, baudrate=57600)
        self._serialBuffer = ""
        self._ktyTemp = 23.0
        self._uRef = 5.0
        self._iRef = 0.002
        self._adcComp = 6.0 / 5.0
        self._readAdcThread = None
        self._stopReq = threading.Event()
        self._undoReq = threading.Event()
        self._stopReq.clear()
        self._adcValue = 350
        self._uif = uif.Uif(self)
        self._graph = None
        self._new = False
        self._visuBuff = []
        self._refData = []

    def _updateTemp(self):
        ktyRes = (self._uRef * self._adcValue / 1023.0 * self._adcComp) / self._iRef
        self._ktyTemp = self._shhConverter.rToTempCelsius(ktyRes)
        if self._serial.isOpen():
            self._uif.disp("in", "ADC: ", self._adcValue, "R: ", ktyRes, "t: ", self._ktyTemp, "Buff: ", self._serial.inWaiting(), "New: ", self._new)
        self._new = False
        return self._ktyTemp

    def _setPwm(self, toValue):
        self._serial.write(chr(int(round(toValue))))
        self._uif.disp("out", "PWM: ", toValue)

    def _convertToSteps(self, begin, end, duration, timebase):
        delta = end - begin
        stepNo = int(round(duration / timebase))
        stepNo = 1 if stepNo == 0 else stepNo
        stepWidth = delta / float(stepNo)
        steps = [begin + i * stepWidth for i in range(stepNo)]
        steps[-1] = end
        return steps

    def _profileToTt(self, profile, timebase=0.5):
        steps = []
        ambient = 25
        # Ambient to preheat
        rampupTime = (profile["Tsmin"] - ambient) / profile["rampup"]
        steps.extend(self._convertToSteps(ambient, profile["Tsmin"], rampupTime, timebase))
        # Preheat
        steps.extend(self._convertToSteps(profile["Tsmin"], profile["Tsmax"], profile["ts"], timebase))
        # Preheat to Liquidous
        tlTotpTime = tpTotlTime = (profile["tl"] - profile["tp"]) / 2.0
        deltaTsTl = profile["Tl"] - profile["Tsmax"]
        slopeTsTl = deltaTsTl / float(tlTotpTime)
        durTsmaxTl = slopeTsTl * deltaTsTl
        steps.extend(self._convertToSteps(profile["Tsmax"], profile["Tl"], durTsmaxTl, timebase))
        # Liquidous to Peak
        steps.extend(self._convertToSteps(profile["Tl"], profile["Tp"], tlTotpTime, timebase))
        # Reflow
        steps.extend(self._convertToSteps(profile["Tp"], profile["Tp"], profile["tp"], timebase))
        # Back to Liquidous
        steps.extend(self._convertToSteps(profile["Tp"], profile["Tl"], tpTotlTime, timebase))
        # Cool down
        coolDowmTime = (profile["Tl"] - ambient) / profile["rampdown"]
        steps.extend(self._convertToSteps(profile["Tl"], ambient, coolDowmTime, timebase))
        return steps

    def _sflush(self):
        self._serial.read(self._serial.inWaiting())

    def _readAdc(self):
        frameLen = 3
        try:
            while not self._stopReq.isSet():
                self._sflush()
                self._serialBuffer = self._serial.read(frameLen)
                while ord(self._serialBuffer[0]) != 0xFF or ord(self._serialBuffer[2]) & 0xF0 != 0x00:
                    self._serialBuffer = self._serialBuffer[1:] + self._serial.read(1)
                    assert(len(self._serialBuffer) == 3)
                adcValue = ord(self._serialBuffer[2]) << 8
                adcValue += ord(self._serialBuffer[1])
                self._adcValue = adcValue
                self._new = True
        except serial.SerialException, e:
            if e.message.count("Bad file descriptor"):
                pass
                # The port was closed in self.stop(). Hopefully.
            else:
                raise

    def _do(self):
        self._workerThread.start()
        i = 0
        refLen = len(self._refData)
        while not self._undoReq.isSet() and i < refLen:
            self._pid.inputx = self._refData[i]
            i += 1
            time.sleep(0.5)

    def _undo(self):
        self._undoReq.isSet()
        self._workerThread.join()

    def start(self):
        self._readAdcThread = threading.Thread(target=self._readAdc)
        self._readAdcThread.start()
        self._pid.start()
        self._uif.start()
        self._workerThread = threading.Thread(target=self._do)
        self._refData = self._profileToTt(self._profile)
        self._do()
        self._graph = visualizer.Visualizer(0.5, 1, self._refData, self.gen)

        self._graph._axes.set_ylim([80, 250])
        #self._graph._axes.set_xlim([0, 300])
        self._graph.start()

    def gen(self):
        if len(self._visuBuff) > len(self._refData) - 1:
            self._visuBuff = self._visuBuff[1:]
        self._visuBuff.append(self._ktyTemp)
        return self._visuBuff

    def stop(self):
        self._stopReq.set()
        self._serial.close()  # Raises exception in readAdcThread
        self._readAdcThread.join()
        self._pid.stop()
        self._uif.stop()
        self._graph.stop()

if __name__ == '__main__':
    if len(sys.argv)>1 and os.access(sys.argv[1], os.W_OK | os.R_OK):
        serialport=sys.argv[1]
    else:
        serialport="/dev/tty.SLAB_USBtoUART"
        serialport="/dev/tty.Bluetooth-Incoming-Port"
        #serialport = "/dev/tty.usbserial-A6004adL"
    controller = ReflowControl(serialport)
    controller.start()
