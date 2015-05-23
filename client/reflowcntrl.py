import serial
import shh
import pid

class ReflowControl:

    def __init__(self, portName, A, B, C, D):
        self._shhConverter = shh.SteinHaart(A, B, C, D)
        self._pid = pid.Pid(self._update, self._outChanged)
        self._portName = portName
        self._serial = serial.Serial(port=self._portName, baudrate=57600)
        self._serialBuffer = ""
        self._ktyTemp = 23.0
        self._uRef = 5.0
        self._iRef = 0.002
        self._adcComp = 6.0 / 5.0

    def _update(self):
        return self._ktyTemp

    def _outChanged(self, toValue):
        self._serial.write(chr(toValue))

    def do(self):
        try:
            while True:
                self._serialBuffer += self._serial.read(3)
                while self._serialBuffer and self._serialBuffer[0] != chr(0xFF):
                        self._serialBuffer = self._serialBuffer[1:]
                while len(self._serialBuffer) > 2:
                    if ord(self._serialBuffer[2]) & 0xF0 == 0:
                        adcValue = ord(self._serialBuffer[2]) << 8
                        adcValue += ord(self._serialBuffer[1])
                        ktyRes = (self._uRef * adcValue / 1023.0 * self._adcComp) / self._iRef
                        self._ktyTemp = self._shhConverter.rToTempCelsius(ktyRes)
                        if not self._pid.isRunning:
                            self._pid.start()
                        print("ADC: ", adcValue, "R: ", ktyRes, "t: ", self._ktyTemp)
                        self._serialBuffer = self._serialBuffer[2:]
                    else:
                        self._serialBuffer = self._serialBuffer[1:]
        except KeyboardInterrupt:
            self._pid.stop()

if __name__ == '__main__':
    shhcoeffs = (0.049182398851342568, -0.015880288085651714, 0.0018439776862060255, -7.5225149204180178e-05)
    controller = ReflowControl("/dev/tty.SLAB_USBtoUART", *shhcoeffs)
    controller.do()