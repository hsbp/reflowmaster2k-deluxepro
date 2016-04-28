import time

class Logger(object):

    def __init__(self, enabled):
        self._fileName = "log_%s" % time.strftime("%H-%M-%S")
        self._fileCreated = False
        self._header = []
        self._entry = {}
        self._enabled = enabled

    def _createFile(self):
        with open(self._fileName, "w"):
            pass
        self._fileCreated = True

    def _appendEntry(self):
        if not self._enabled:
            return
        if not self._fileCreated:
            self._createFile()
        headerChanged = False
        for key in self._entry.keys():
            if key not in self._header:
                self._header.append(key)
                headerChanged = True
        if headerChanged:
            with open(self._fileName, "r+") as file:
                file.readline()
                log = file.read()
                file.seek(0)
                file.write(";".join(str(key) for key in self._header) + "\n")
                file.write(log)
                file.truncate()
        with open(self._fileName, "a") as file:
            for key in self._header:
                if key in self._entry:
                    file.write(str(self._entry[key]))
                file.write(";")
            file.write("\n")

    def new(self, entry):
        if self._entry:
            self._appendEntry()
            self._entry = {}
        self.extend(entry)

    def extend(self, entry):
        self._entry.update(entry)
