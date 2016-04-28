# Copyright (C) 2011-2012 W. Trevor King <wking@tremily.us>
#
# This file uses parts from pypid.
#
# pypid is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# pypid is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# pypid.  If not, see <http://www.gnu.org/licenses/>.

import pypid.controller
import pypid.rules
import ppidbackend

class PidTuner():

    def __init__(self, pid):
        TEMP_MIN = 20
        TEMP_MAX = 300
        self._pid = pid
        self._backend = ppidbackend.RflwmstrBackend(self._pid)
        self._controller = pypid.controller.Controller(self._backend, min=TEMP_MIN, max=TEMP_MAX)

    def test_controller_step_response(self):
        try:
            self._backend.set_mode('PID')
            max_MV = self._backend.get_max_mv()
            MVa = 0.4 * max_MV
            MVb = 0.5 * max_MV
            step_response = self._controller.get_step_response(mv_a=MVa, mv_b=MVb, tolerance=1.5, stable_time=4.)
            process_gain, dead_time, decay_time, max_rate = \
                self._controller.analyze_step_response(step_response, mv_shift=MVb-MVa)
            print(('step response: process gain {:n}, dead time {:n}, decay time {:n}, max-rate {:n}').format(
                    process_gain, dead_time, decay_time, max_rate))
            for name, response_fn, modes in [
                ('Zeigler-Nichols', pypid.rules.ziegler_nichols_step_response,
                 ['P', 'PI', 'PID']),
                ('Cohen-Coon', pypid.rules.cohen_coon_step_response,
                 ['P', 'PI', 'PID']), # 'PD'
                ('Wang-Juan-Chan', pypid.rules.wang_juang_chan_step_response,
                 ['PID']),
                ]:
                for mode in modes:
                    p, i, d = response_fn(process_gain=process_gain, dead_time=dead_time, decay_time=decay_time, mode=mode)
                    print('{} step response {}: p {:n}, i {:n}, d {:n}'.format(name, mode, p, i, d))
        finally:
            pass

    def test_controller_bang_bang_response(self):
        try:
            self._backend.set_setpoint(50)  # TODO: Figure out what the fuck is this
            dead_band = 3 * self._controller.estimate_pv_sensitivity()
            bang_bang_response = self._controller.get_bang_bang_response(dead_band=dead_band)
            amplitude, period = self._controller.analyze_bang_bang_response(bang_bang_response)
            print('bang-bang response: amplitude {:n}, period {:n}'.format(amplitude, period))
            for name, response_fn, modes in [
                ('Zeigler-Nichols', pypid.rules.ziegler_nichols_bang_bang_response,
                 ['P', 'PI', 'PID'])
                ]:
                for mode in modes:
                    p, i, d = response_fn(amplitude=amplitude, period=period, mode=mode)
                    print('{} bang-bang response {}: p {:n}, i {:n}, d {:n}'.format(name, mode, p, i, d))
        finally:
            pass
