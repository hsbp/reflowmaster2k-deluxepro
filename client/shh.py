import math

class SteinHaart:

    def __init__(self, A=0, B=0, C=0, D=0):
        self.setCoeffs(A, B, C, D)

    def setCoeffs(self, A, B, C, D):
        self._A = A
        self._B = B
        self._C = C
        self._D = D

    def rToTempKelvin(self, resInOhm):
        lnR = math.log(resInOhm)
        t = 1 / (self._A + self._B * lnR + self._C * lnR**2 + self._D * lnR**3)
        return t

    def rToTempCelsius(self, resInOhm):
        t = self.rToTempKelvin(resInOhm) - 273.15
        return t