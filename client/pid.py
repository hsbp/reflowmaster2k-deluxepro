"""
Based on http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/
"""

import time
import threading

class Pid(object):

    class Modes:
        AUTO_READ = 1
        AUTO_CALC = 2
        AUTO_OUT = 4
        AUTO_FULL = AUTO_READ | AUTO_CALC | AUTO_OUT
        MANUAL = 0
        DIRECT = 0
        REVERSE = 1

    def __init__(self, updateCallback=None, outputChangedCallback=None, coeffs=None):
        if coeffs is None:
            coeffs = (1, 0, 0)
        self._kp, self._ki, self._kd = coeffs
        self._oki = self._ki
        self._okd = self._kd

        self._sampleTime = 1
        self._cntrlDir = Pid.Modes.DIRECT
        self._cntrlMode = Pid.Modes.AUTO_FULL

        self._input = 0
        self._output = 0
        self._setpoint = 0

        self._iterm = 0
        self._lastInput = 0
        self._outMin = 0
        self._outMax = 255

        self._updateCallback = updateCallback
        self._outputChangedCallback = outputChangedCallback
        self._stopReq = threading.Event()
        self._updateThread = None

    @property
    def kp(self):
        return self._kp

    @kp.setter
    def kp(self, val):
        self._kp = val

    @property
    def ki(self):
        return self._oki

    @ki.setter
    def ki(self, val):
        self._oki = val
        if self._cntrlDir == Pid.Modes.REVERSE:
            val *= -1
        self._ki = val * self._sampleTime

    @property
    def kd(self):
        return self._okd

    @kd.setter
    def kd(self, val):
        self._okd = val
        if self._cntrlDir == Pid.Modes.REVERSE:
            val *= -1
        self._kd = val / self._sampleTime

    @property
    def sampleTime(self):
        return self._sampleTime

    @sampleTime.setter
    def sampleTime(self, val):
        ratio = val / self._sampleTime
        self._ki *= ratio
        self._kd /= ratio
        self._sampleTime = val

    @property
    def cntrlDir(self):
        return self._cntrlDir

    @cntrlDir.setter
    def cntrlDir(self, val):
        if val != self._cntrlDir:
            self._kp *= -1
            self._ki *= -1
            self._kd *= -1
        self._cntrlDir = val

    @property
    def cntrlMode(self):
        return self._cntrlMode

    @cntrlMode.setter
    def cntrlMode(self, val):
        if self._cntrlMode ^ val:
            self.initialize()
        self._cntrlMode = val

    @property
    def maxOut(self):
        return self._outMax

    @maxOut.setter
    def maxOut(self, val):
        self._outMax = val
        self._output = self._clamp(self._output, self._outMin, self._outMin)
        self._iterm = self._clamp(self._iterm, self._outMin, self._outMin)

    @property
    def minOut(self):
        return self._outMin

    @minOut.setter
    def minOut(self, val):
        self._outMin = val
        self._output = self._clamp(self._output, self._outMin, self._outMin)
        self._iterm = self._clamp(self._iterm, self._outMin, self._outMin)

    @property
    def inputx(self):
        return self._input

    @inputx.setter
    def inputx(self, val):
        if not self._cntrlMode & Pid.Modes.AUTO_READ:
            self._input = val

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, val):
        if not self._cntrlMode & Pid.Modes.AUTO_CALC:
            self._output = val

    @property
    def setPoint(self):
        return self._setpoint

    @setPoint.setter
    def setPoint(self, val):
        self._setpoint = val

    @property
    def isRunning(self):
        return not self._stopReq.isSet()

    def _clamp(self, val, low, high):
        if val > high:
            val = high
        elif val < low:
            val = low
        return val

    def initialize(self):
        self._lastInput = self._input
        self._iterm = self._clamp(self._output, self._outMin, self._outMax)

    def compute(self):
        error = self._setpoint - self._input
        self._iterm = self._clamp(self._ki * error, self._outMin, self._outMax)
        dInput = self._input - self._lastInput
        pidResult = self._kp * error + self._iterm - self._kd * self._kd * dInput
        self._output = self._clamp(pidResult, self._outMin, self._outMax)
        self._lastInput = self._input

    def _update(self):
        self._stopReq.clear()
        lastOutput = ~self._output
        while not self._stopReq.isSet():
            begin = time.time()
            if self._cntrlMode & Pid.Modes.AUTO_READ and self._updateCallback is not None:
                self._input = self._updateCallback()
            if self.cntrlMode & Pid.Modes.AUTO_CALC:
                self.compute()
            if self._cntrlMode & Pid.Modes.AUTO_OUT and \
               self._outputChangedCallback is not None and \
               self._output != lastOutput:
                self._outputChangedCallback(self._output)
            lastOutput = self._output
            while time.time() < begin + self._sampleTime:
                time.sleep(0.05)
                if self._stopReq.isSet():
                    break

    def start(self):
        if not self._stopReq.isSet():
            self.initialize()
            self._updateThread = threading.Thread(target=self._update)
            self._updateThread.start()

    def stop(self):
        self._stopReq.set()
        self._updateThread.join()
