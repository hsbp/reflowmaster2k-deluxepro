"""
Based on http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/
"""

import time
import threading

class Pid:

    class Modes:
        AUTO = 1
        MANUAL = 0
        DIRECT = 0
        REVERSE = 1

    def __init__(self, updateCallback=None, outputChangedCallback=None):
        self._kp = 1
        self._ki = 0
        self._kd = 0

        self._oki = 0
        self._okd = 0

        self._sampleTime = 1
        self._cntrlDir = Pid.Modes.DIRECT
        self._cntrlMode = Pid.Modes.AUTO

        self._input = 0
        self._output = 0
        self._setpoint = 0

        self._iterm = 0
        self._lastInput = 0
        self._outMin = 0
        self._outMax = 255

        self._updateCallback = updateCallback
        self._outputChangedCallback = outputChangedCallback
        self._isRunning = False
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

    @ki.setter
    def ki(self, val):
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
        isAuto = val == Pid.Modes.AUTO
        if isAuto != self._inAuto:
            self.initialize()
        self._inAuto = isAuto

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
        self._input = val

    @property
    def output(self):
        return self._input

    @output.setter
    def output(self, val):
        if self._cntrlMode == Pid.Modes.MANUAL:
            self._input = val

    @property
    def setPoint(self):
        return self._setpoint

    @setPoint.setter
    def setPoint(self, val):
        self._setpoint = val

    @property
    def isRunning(self):
        return self._isRunning

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
        while self._isRunning:
            begin = time.time()
            if self._updateCallback is not None:
                self._input = self._updateCallback()
            lastOutput = self._output
            if self._cntrlMode == Pid.Modes.AUTO:
                self.compute()
            if self._outputChangedCallback is not None and self._output != lastOutput:
                self._outputChangedCallback(self._output)
            while time.time() < begin + self._sampleTime:
                time.sleep(self._sampleTime / 100)

    def start(self):
        if not self._isRunning:
            self.initialize()
            self._updateThread = threading.Thread(target=self._update)
            self._updateThread.start()

    def stop(self):
        if self._isRunning:
            self._isRunning = False
            self._updateThread.join()
