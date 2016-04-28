from pypid.backend import Backend as _Backend
from pypid.backend import ManualMixin as _ManualMixin
from pypid.backend import PIDMixin as _PIDMixin
from pypid.backend import TemperatureMixin as _TemperatureMixin
from pypid import LOG as _LOG

class RflwmstrBackend (_Backend, _ManualMixin, _PIDMixin, _TemperatureMixin):
    """Temperature control backend for a Reflowmaster2000+ deluxe pro

    * PV: process temperature
    * PV-units: degrees Celsius
    * MV: ovens heater power
    * MV-units: PWM units
    """
    pv_units = 'C'
    mv_units = 'unit'

    def __init__(self, pid):
        self._pid = pid

    def get_pv(self):
        "Return the current process variable in PV-units"
        #_LOG.debug('PV: %s' % self._pid.inputx)
        return self._pid.inputx

    def set_max_mv(self, max):
        "Set the max manipulated variable in MV-units"
        self._pid.maxOut = max

    def get_max_mv(self):
        "Get the max manipulated variable MV-units"
        return self._pid.maxOut

    def get_mv(self):
        """Return the calculated manipulated varaible in MV-units

        The returned current is not the actual MV, but the MV that the
        controller calculates it should generate.  For example, if the
        voltage required to generate an MV current exceeds the
        controller's max voltage, then the physical current will be
        less than the value returned here.
        """
        return self._pid.output

    def get_modes(self):
        "Return a list of control modes supported by this backend"
        return ("PID", "manual")

    def get_mode(self):
        "Return the current control mode"
        mode = "manual"
        if self._pid.cntrlMode > self._pid.Modes.AUTO_OUT:
            mode = "PID"
        return mode

    def set_mode(self, mode):
        "Set the current control mode"
        if mode == "PID":
            self._pid.cntrlMode = self._pid.Modes.AUTO_FULL
        elif mode == "manual":
            self._pid.cntrlMode = self._pid.Modes.AUTO_READ | self._pid.Modes.AUTO_OUT
        else:
            raise ValueError("Invalid control mode %s" % mode)

    def set_mv(self, pwm):
        "Set the desired manipulated variable in MV-units"
        self._pid.output = pwm

    def set_setpoint(self, setpoint):
        "Set the process variable setpoint in PV-units"
        self._pid.setPoint = setpoint

    def get_setpoint(self):
        "Get the process variable setpoint in PV-units"
        return self._pid.setPoint

    def get_up_gains(self):
        return (self._pid.kp, self._pid.ki, self._pid.kd)

    def set_up_gains(self, proportional=None, integral=None, derivative=None):
        if proportional is not None:
            self._pid.kp = proportional
        if integral is not None:
            self._pid.ki = integral
        if derivative is not None:
            self._pid.kd = derivative

    def get_down_gains(self):
        return (-self._pid.kp, -self._pid.ki, -self._pid.kd)

    def set_down_gains(self, proportional=None, integral=None, derivative=None):
        pass

    def get_feedback_terms(self):
        return (self.get_mv(), self._pid.setPoint - self.get_pv(), self._pid._iterm, self._pid._dterm)

    def clear_integral_term(self):
        """Reset the integral feedback turn (removing integrator windup)

        Because the proportional term provides no control signal when
        the system exactly matches the setpoint, a P-only algorithm
        will tend to "droop" off the setpoint.  The equlibrium
        position is one where the droop-generated P term balances the
        systems temperature leakage.  To correct for this, we add the
        integral feedback term, which adjusts the control signal to
        minimize long-term differences between the output and setpoint.

        One issue with the integral term is "integral windup".  When
        the signal spends a significant time away from the setpoint
        (e.g. during a long ramp up to operating temperature), the
        integral term can grow very large, causing overshoot once the
        output reaches the setpoint.  To allow our controller to avoid
        this, this method manually clears the intergal term for the
        backend.
        """
        self._pid._iterm = 0