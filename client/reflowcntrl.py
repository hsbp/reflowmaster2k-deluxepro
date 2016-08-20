import time
import serial
import threading

import shh
import pid
import uif
import visualizer
import storage
import emulator
import pidtuner
import log

class ReflowControl:

    def __init__(self, portName=None, shhCoeffs=None, pidCoeffs=None, profile=None, uRef=None, iRef=None, adcComp=None):
        self._uif = uif.Uif(self)
        self._storage = None
        if not all((portName, shhCoeffs, pidCoeffs, profile, uRef, iRef, adcComp)):
            try:
                self._storage = storage.Storage()
            except storage.StorageException as e:
                self._uif.msg(e.message)
                quit()
        if uRef is None:
            uRef = self._storage.getUref()
        if iRef is None:
            iRef = self._storage.getIref()
        if adcComp is None:
            adcComp = self._storage.getAdcComp()
        if portName is None:
            portName = self._storage.getSerial()
        if shhCoeffs is None:
            shhCoeffs = self._storage.getShhCoeffs()
        if pidCoeffs is None:
            pidCoeffs = self._storage.getPidCoeffs()
        if profile is None:
            profile = self._storage.getProfiles()[0]
        self._uRef = uRef
        self._iRef = iRef
        self._adcComp = adcComp
        self._currentProfile = profile
        if self._storage is None:
            self._profiles = {self._currentProfile}
        else:
            self._profiles = self._storage.getProfiles()
        self._portName = portName
        self._shhConverter = shh.SteinHaart(*shhCoeffs)
        self._pid = pid.Pid(self._updateTemp, self._setPwm, pidCoeffs)
        #self._pid.cntrlMode = self._pid.Modes.AUTO_OUT | self._pid.Modes.AUTO_READ #| self._pid.Modes.AUTO_CALC
        self._pid.sampleTime = 0.5
        self._pidTuner = pidtuner.PidTuner(self._pid)
        self._serialBuffer = ""
        if self._portName is not None:
            self._serial = serial.Serial(port=self._portName, baudrate=57600)
        else:
            self._serial = emulator.FakeSerial()
            self._uif.msg("!!! No available serial port found. Using emulated input data !!!")
        self._adcValue = 350
        self._readAdcThread = None
        self._adcLock = threading.Lock()
        self._stopAdcReq = threading.Event()
        self._stopBakeReq = threading.Event()
        self._startDraw = threading.Event()
        self._baking = threading.Event()
        self._graph = None
        self._new = False
        self._pid.attachCallback(self._pid.CallbackType.CALC, self._pidCalcDone)
        self._logger = log.Logger()
        self._logger._enabled = False#True

    def _convertToSteps(self, begin, end, duration, timebase):
        #duration *= 1.4
        delta = end - begin
        stepNo = int(round(duration / timebase))
        stepNo = 1 if stepNo == 0 else stepNo
        stepWidth = delta / float(stepNo)
        steps = [begin + i * stepWidth for i in range(stepNo)]
        steps[-1] = end
        return steps

    def _profileToTt(self, profile, timebase=0.5):
        steps = []
        ambient = 50
        # Preamble
        steps.extend(self._convertToSteps(50, 50, 30, timebase))
        # Ambient to preheat
        rampupTime = (profile["Tsmin"] - ambient) / profile["rampup"]
        steps.extend(self._convertToSteps(ambient, profile["Tsmin"], rampupTime, timebase))
        # Preheat
        steps.extend(self._convertToSteps(profile["Tsmin"], profile["Tsmax"], profile["ts"], timebase))
        # Preheat to Liquidous
        tlTotpTime = tpTotlTime = (profile["tl"] - profile["tp"]) / 2.0
        deltaTsmaxTl = profile["Tl"] - profile["Tsmax"]
        deltaTlTp = profile["Tp"] - profile["Tl"]
        slopeTsmaxTl = slopeTlTp = deltaTlTp / float(tlTotpTime)
        durTsmaxTl = deltaTsmaxTl * (slopeTsmaxTl * 2.0)
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
        timestamps = tuple(timebase * i for i in range(len(steps)))
        return (timestamps, steps)

    def _updateTemp(self):
        adcValue = self._getAdcValue()
        ktyRes = ((self._uRef * adcValue) / (1023.0 * self._adcComp)) / self._iRef
        ktyTemp = self._shhConverter.rToTempCelsius(ktyRes)
        self._uif.disp("in", ("ADC", adcValue), ("R", "%.2f" % ktyRes), ("T", "%.2f" % ktyTemp), self._new)
        self._logger.new({"ADC": adcValue, "R": "%.2f" % ktyRes, "T": "%.2f" % ktyTemp})
        self._graph.update(ktyTemp)
        self._new = False
        return ktyTemp

    def _pidCalcDone(self, err, pterm, iterm, dterm, output):
        self._uif.disp("pid", ("e", "%.2f" % err), ("p", "%.2f" % pterm), ("i", "%.2f" % iterm), ("d", "%.2f" % -dterm), ("o", "%.2f" % output))
        self._logger.extend({"p": pterm, "i": iterm, "d": dterm, "o": output})

    def _setPwm(self, toValue):
        try:
            self._serial.write(chr(int(round(toValue))))
        except serial.SerialException:
            pass
        self._uif.disp("out", "PWM: ", toValue)

    def _sflush(self):
        self._serial.read(self._serial.inWaiting())

    def _getAdcValue(self):
        with self._adcLock:
            adcValue = self._adcValue
        return adcValue

    def _readAdc(self):
        frameLen = 3
        try:
            while not self._stopAdcReq.isSet():
                self._sflush()
                self._serialBuffer = self._serial.read(frameLen)
                while ord(self._serialBuffer[0]) != 0xFF or ord(self._serialBuffer[2]) & 0xF0 != 0x00:
                    self._serialBuffer = self._serialBuffer[1:] + self._serial.read(1)
                    assert(len(self._serialBuffer) == frameLen)
                adcValue = ord(self._serialBuffer[2]) << 8
                adcValue += ord(self._serialBuffer[1])
                with self._adcLock:
                    self._adcValue = adcValue
                self._new = True
        except serial.SerialException, e:
            if self._stopAdcReq.isSet() and "Bad file descriptor" in e.message:
                pass  # The port was closed in self._stopAdc(). Hopefully.
            else:
                raise

    def _stopAdc(self):
        self._stopAdcReq.set()
        self._serial.close()  # Intentionally raises exception in readAdcThread
        self._readAdcThread.join()

    def _initProfile(self):
        self._refData = self._profileToTt(self._currentProfile)
        #timestamps, steps = self._refData
        #l = (len(steps)) // 3
        #x  =timestamps[l:]
        #self._refData = (x, steps[:len(x)])
        self._graph.init(self._refData)

    def loadProfile(self, name):
        if self._baking.isSet():
            self._uif.msg("Can not load profile while reflow is in progress.")
            return
        found = False
        for profile in self._profiles:
            if profile["name"] == name:
                self._currentProfile = profile
                found = True
                break
        if found:
            self._initProfile()
        else:
            self._uif.msg("Profile %s not found." % name)

    def savePidCoeffs(self):
        pidCoeffs = (self._pid.kp, self._pid.ki, self._pid.kd)
        try:
            self._storage.save("pidcoeffs", pidCoeffs)
        except storage.StorageException as e:
            self._uif.msg(e.message)

    def bake(self):
        if not self._baking.isSet():
            self._baking.set()
            self._stopBakeReq.clear()
            self._graph.init(self._refData)
            self._bakingProcessThread = threading.Thread(target=self._bakingProcess)
            self._bakingProcessThread.start()
            self._graph.enableLive()

    def stopBake(self):
        if self._baking.isSet() and not self._stopBakeReq.isSet():
            self._stopBakeReq.set()
            self._bakingProcessThread.join()
            self._stopBakeReq.clear()

    def _bakingProcess(self):
        self._uif.msg("Reflow started")
        for setPoint in self._refData[1]:
            if self._stopBakeReq.isSet():
                break
            self._pid._setpoint = setPoint + 7
            time.sleep(0.5)
        self._pid.setPoint = 0
        self._graph.disableLive()
        self._baking.clear()
        self._uif.msg("Reflow finished")

    def autoTune(self, mode):
        if mode == "s":
            self._pidTuner.test_controller_step_response()
        elif mode == "b":
            self._pidTuner.test_controller_bang_bang_response()

    def draw(self, enable=False):
        if enable:
            self._graph.init(self._refData)
            self._graph.enableLive()
        else:
            self._graph.disableLive()

    def start(self):
        self._setPwm(0)
        self._readAdcThread = threading.Thread(target=self._readAdc)
        self._graph = visualizer.Visualizer()
        self._initProfile()
        self._readAdcThread.start()
        self._pid.start()
        self._uif.start()

    def stop(self):
        self.stopBake()
        self._pid.stop()
        self._graph.stop()
        self._stopAdc()
        self._uif.stop()

if __name__ == '__main__':
    controller = ReflowControl()
    controller.start()
