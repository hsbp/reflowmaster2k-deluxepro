import threading

class Uif(object):

    def __init__(self, controller):
        self._cntrlr = controller
        self._listenerThread = None
        self._stopReq = threading.Event()
        self._dispState = {}

    def _notfound(self, _dummy):
        print("Command not found")

    def _failed(self, exception):
        print("Failed: %s" % exception)

    def _pidparam(self, prop, param):
        if param == "":
            print(getattr(self._cntrlr._pid, prop))
        else:
            try:
                param = float(param)
            except Exception as e:
                self._failed(e)
                return
            setattr(self._cntrlr._pid, prop, param)

    def _cmd_kp(self, param):
        """
        Sets or returns the PID's proportional coefficient
        """
        self._pidparam("kp", param)

    def _cmd_ki(self, param):
        self._pidparam("ki", param)

    def _cmd_kd(self, param):
        self._pidparam("kd", param)

    def _cmd_spt(self, param):
        self._pidparam("setPoint", param)

    def _cmd_in(self, param):
        self._pidparam("inputx", param)

    def _cmd_out(self, param):
        self._pidparam("output", param)

    def _cmd_pidm(self, param):
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
            print(state)
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
        if param == "":
            print("%0.1f" % (self._cntrlr._pid.output * 100 / self._cntrlr._pid.maxOut))
        else:
            out = float(param) / 100 * self._cntrlr._pid.maxOut
            self._cntrlr._pid.output = out

    def _cmd_disp(self, param):
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
            print(manstr)

    def _cmd_man(self, param):
        """
        man [command]
        command: name of the command which's man string to get
        Without parameter lists the available commands.
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
        print(manstr)

    def _cmd_quit(self, param):
        self._cntrlr.stop()

    def disp(self, key, *args):
        try:
            self._dispState[key]
        except:
            self._dispState[key] = "off"
        if self._dispState[key] != "off":
            print(", ".join(str(arg) for arg in args))
            if self._dispState[key] == "oneshot":
                self._dispState[key] = "off"

    def listen(self):
        try:
            while not self._cntrlr._stopReq.isSet():
                val = raw_input("> ")
                if val:
                    val = val.split(" ", 1)
                    if len(val) > 1:
                        cmd, params = val
                    else:
                        cmd = val[0]
                        params = ""
                    cmdProcessor = getattr(self, "_cmd_" + cmd.strip().lower(), self._notfound)
                    cmdProcessor(params.strip())
        except KeyboardInterrupt:
            self._cntrlr.stop()

    def start(self):
        self._listenerThread = threading.Thread(target=self.listen)
        self._listenerThread.start()

    def stop(self):
        self._stopReq.set()
        #self._listenerThread.join()

