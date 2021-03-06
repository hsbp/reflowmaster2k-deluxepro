import sys
import threading
import readchar

class Uif(object):

    def __init__(self, controller):
        self._cntrlr = controller
        self._listenerThread = None
        self._stopReq = threading.Event()
        self._dispState = {}
        self._lineBufferRLock = threading.RLock()
        self._msgLock = threading.Lock()
        self._lineBuffer = ""

    def _notfound(self, _dummy):
        self.msg("Command not found")

    def _failed(self, exception):
        self.msg("Failed: %s" % exception)

    def _pidparam(self, prop, param):
        if param == "":
            self.msg(getattr(self._cntrlr._pid, prop))
        else:
            try:
                param = float(param)
            except Exception as e:
                self._failed(e)
                return
            setattr(self._cntrlr._pid, prop, param)

    def _cmd_kp(self, param):
        """
        Displays or sets the PID's proportional coefficient.
        """
        self._pidparam("kp", param)

    def _cmd_ki(self, param):
        """
        Displays or sets the PID's integral coefficient.
        """
        self._pidparam("ki", param)

    def _cmd_kd(self, param):
        """
        Displays or sets the PID's derivate coefficient.
        """
        self._pidparam("kd", param)

    def _cmd_spt(self, param):
        """
        Displays or sets the target temperature in Celsius degrees.
        """
        self._pidparam("setPoint", param)

    def _cmd_in(self, param):
        """
        Displays or sets the PID's input value. Set takes effect only if the pid's AUTO_READ flag is cleared.
        Refer to "pidm" command.
        """
        self._pidparam("inputx", param)

    def _cmd_out(self, param):
        """
        Displays or sets the PID's output value. Set takes effect only if the pid's AUTO_CALC flag is cleared.
        Refer to "pidm" command.
        """
        self._pidparam("output", param)

    def _cmd_pidm(self, param):
        """
        Displays or sets the PID's mode flags. These flags are:
        read: If set, the PID periodically calls its update callback, and uses the returned value as the current input.
        out: If set, the PID periodically calls its output changed callback.
        calc: Enables the actual PID algorithm. If celared the output keeps its last state, which is overridable with
              the "out" command.
        full: The same as if the previous three flags would be set.
        To set a flag type its name after the pidm command, you can specify multiple ones separated by spaces. If one or
        more is omitted, then that flag(s) will be cleared.
        """
        pidModes = self._cntrlr._pid.Modes
        autoModes = {pidModes.AUTO_READ: "read", pidModes.AUTO_CALC: "calc", pidModes.AUTO_OUT: "out"}
        if param == "":
            currentMode = self._cntrlr._pid.cntrlMode
            if currentMode == pidModes.MANUAL:
                state = "manual"
            elif currentMode == pidModes.AUTO_FULL:
                state = "auto: full"
            else:
                state = "auto: "
                for modeId, modeName in autoModes.items():
                    if currentMode & modeId:
                        state += modeName + " "
            self.msg(state)
        else:
            mode = pidModes.MANUAL
            param = param.lower()
            if param.count("full"):
                mode = pidModes.AUTO_FULL
            else:
                for modeId, modeName in autoModes.items():
                    if param.count(modeName):
                        mode |= modeId
            self._cntrlr._pid.cntrlMode = mode

    def _cmd_pwr(self, param):
        """
        Displays or sets the PID's output value in percentage, relative to the maximal output value.
        Set takes effect only if the pid's AUTO_CALC flag is cleared. Refer to "pidm" command.
        """

        if param == "":
            self.msg("%0.1f" % (self._cntrlr._pid.output * 100 / self._cntrlr._pid.maxOut))
        else:
            out = float(param) / 100 * self._cntrlr._pid.maxOut
            self._cntrlr._pid.output = out

    def _cmd_disp(self, param):
        """
        If called without parameters displays the "dispable" properties.
        If called with the prop name, without further parameters, then prints it one time.
        If called with the prop name and "on" afterwards then periodically prints the prop until called the same prop
        name with "off" parameter.
        """
        if param:
            if param.count(" "):
                key, toState = param.split(" ", 2)
            else:
                key = param
                toState = "oneshot"
            try:
                self._dispState[key] = toState
            except Exception, e:
                self._failed(e)
        else:
            manstr = "\n\t".join(self._dispState.keys())
            if not manstr:
                manstr = "There are no dispable props"
            else:
                manstr = "Dispable properties:\n\t" + manstr
            self.msg(manstr)

    def _cmd_quit(self, param):
        """
        Quits the program.
        """
        self._cntrlr.stop()

    def _cmd_bake(self, param):
        """
        Starts the baking process.
        """
        self._cntrlr.bake()

    def _cmd_stop(self, param):
        """
        Stops the baking process.
        """
        self._cntrlr.stopBake()

    def _cmd_load(self, param):
        """
        Loads reflow profile
        """
        if param:
            self._cntrlr.loadProfile(param.strip().lower())
        else:
            self.msg("Avaiable profiles:\n")
            for profile in self._cntrlr._profiles:
                self.msg("\t" + profile["name"])

    def _cmd_save(self, param):
        """
        Saves to the .reflowcntrlrc file
        """
        if param:
            if param == "pidcoeffs":
                self._cntrlr.savePidCoeffs()
        else:
            self.msg("You can save:\n\tpidcoeffs")

    def _cmd_tune(self, param):
        self._cntrlr.autoTune(param)

    def _cmd_draw(self, param):
        if param:
            enbable = bool(param)
        else:
            enbable = True
        self._cntrlr.draw(enbable)

    def _cmd_man(self, param):
        """
        man [command]
        command: name of the command which's man string to get
        Without parameter lists the available commands. Parameters separated by spaces.
        """
        manstr = ""
        if param:
            docstr = getattr(self, "_cmd_" + param.lower().strip(), self._notfound).__doc__
            if docstr:
                manstr = docstr
            else:
                manstr = "Ooops, somebody was too fukken lazy to write the doc string."
        else:
            prefix = "_cmd_"
            prefixLen = len(prefix)
            funclist = []
            funcs = dir(self)
            for func in funcs:
                if func.startswith(prefix):
                    funclist.append(func[prefixLen:])
            manstr = "Avaiable commands:\n\t" + "\n\t".join(funclist)
        self.msg(manstr)

    def disp(self, key, *args):
        try:
            self._dispState[key]
        except:
            self._dispState[key] = "off"
        if self._dispState[key] != "off":
            def pack(x):
                try:
                    None in x
                except:
                    x = (x,)
                return x
            self.msg("\t".join(": ".join(str(sarg) for sarg in pack(arg)) for arg in args))
            if self._dispState[key] == "oneshot":
                self._dispState[key] = "off"

    def msg(self, msg):
        with self._msgLock:
            self._removePrompt()
            print(msg)
            self._addPrompt()

    def _removePrompt(self):
        linebuff = self._getLineBuffer()
        sys.stdout.write("\r" + " " * (len(linebuff) + 2) + "\r")
        sys.stdout.flush()

    def _addPrompt(self):
        linebuff = self._getLineBuffer()
        sys.stdout.write("\r> " + linebuff)
        sys.stdout.flush()

    def _getLineBuffer(self):
        with self._lineBufferRLock:
            val = self._lineBuffer
        return val

    def _clearLineBuffer(self):
        with self._lineBufferRLock:
            self._lineBuffer = ""

    def _execCommand(self, val):
        val = val.split(" ", 1)
        if len(val) > 1:
            cmd, params = val
        else:
            cmd = val[0]
            params = ""
        cmdProcessor = getattr(self, "_cmd_" + cmd.strip().lower(), self._notfound)
        cmdProcessor(params.strip())

    def listen(self):
        escapeState = 0
        historyState = 0
        history = []
        try:
            while not self._stopReq.isSet():
                self._addPrompt()
                while True:
                    c = readchar.getch()
                    if c == "\x1b": # ESC
                        if escapeState > 0:
                            escapeState = 0
                        else:
                            escapeState = 1
                    elif escapeState == 2:
                        escapeState = 0
                        lastHistoryState = historyState
                        if c == "A":
                            historyState -= 1
                        elif c == "B":
                            if historyState < -1:
                                historyState += 1
                        with self._lineBufferRLock:
                            self._removePrompt()
                            try:
                                self._lineBuffer = history[historyState]
                            except IndexError:
                                historyState = lastHistoryState
                            self._addPrompt()
                    elif escapeState == 1:
                        if c == "[":
                            escapeState = 2
                        else:
                            escapeState = 0
                    elif c == "\x03": # Ctrl-C
                        raise KeyboardInterrupt
                    elif c == "\x1a": # Ctrl-Z
                        raise SystemExit
                    elif c in "\x08\x7f": # Backspace / Del
                        with self._lineBufferRLock:
                            self._removePrompt()
                            self._lineBuffer = self._lineBuffer[:-1]
                            self._addPrompt()
                    elif c in "\r\n":
                        print("")
                        historyState = 0
                        break
                    else:
                        with self._lineBufferRLock:
                            self._lineBuffer += c
                        sys.stdout.write(c)
                val = self._getLineBuffer()
                self._clearLineBuffer()
                if val:
                    history.append(val)
                    self._execCommand(val)
        except KeyboardInterrupt:
            self._cntrlr.stop()

    def start(self):
        self._listenerThread = threading.Thread(target=self.listen)
        self._listenerThread.start()

    def stop(self):
        self._cntrlr.stopBake()
        self._stopReq.set()
