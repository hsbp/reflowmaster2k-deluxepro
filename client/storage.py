import os
import threading

class StorageException(Exception):
    pass

class Storage():

    def __init__(self):
        self._fileName = ".reflowcntrlrc"
        self._entries = {}
        self._fileLock = threading.Lock()
        self.load()

    def load(self):
        if not os.access(self._fileName, os.R_OK):
            raise StorageException("Could not open settings file: %s" % self._fileName)
        with self._fileLock:
            self._entries.clear()
            with open(self._fileName) as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    key, value = line.split(" ", 1)
                    key = key.lower()
                    try:
                        self._entries[key].append(value)
                    except KeyError:
                        self._entries[key] = [value]

    def _toFloat(self, value):
        return float(value)

    def _getNumeric(self, key, expectedLen):
        numVals = []
        rawVals = self._getVal(key, expectedLen)
        try:
            for vals in rawVals:
                numVals.append(map(self._toFloat, vals))
            return numVals
        except (ValueError, TypeError):
            pass

    def _getVal(self, key, expectedLen):
        vals = []
        with self._fileLock:
            try:
                for rawVals in self._entries[key]:
                    rawVals = rawVals.split(" ")
                    assert(len(rawVals) == expectedLen)
                    vals.append(rawVals)
                return vals
            except (KeyError, AssertionError):
                pass

    def getSerial(self):
        with self._fileLock:
            for serial in self._entries.get("serial", []):
                if os.access(serial, os.W_OK | os.R_OK):
                    return serial

    def getPidCoeffs(self):
        val = self._getNumeric("pidcoeffs", 3)
        if val is not None:
            return val[0]

    def getShhCoeffs(self):
        val = self._getNumeric("shhcoeffs", 4)
        if val is not None:
            return val[0]

    def getUref(self):
        val = self._getNumeric("uref", 1)
        if val is not None:
            return val[0][0]

    def getIref(self):
        val = self._getNumeric("iref", 1)
        if val is not None:
            return val[0][0]

    def getAdcComp(self):
        val = self._getNumeric("adccomp", 1)
        if val is not None:
            return val[0][0]

    def getProfiles(self):
        def splitAtColon(val):
            vals = val.split(":", 1)
            if len(vals) != 2:
                vals = ("", "")
            return vals
        profiles = []
        profileKeys = ("name", "rampup", "ts", "Tsmin", "Tsmax", "tl", "Tl", "tp", "Tp", "rampdown")
        rawProfiles = self._getVal("profile", 10)
        if rawProfiles is not None:
            for rawProfile in rawProfiles:
                profile = {}
                for key, value in map(splitAtColon, rawProfile):
                    if key not in profileKeys:
                        continue
                    try:
                        profile[key] = float(value)
                    except ValueError:
                        if key == "name":
                            profile[key] = value
                missing = False
                for key in profileKeys:
                    if key not in profile:
                        missing = True
                        break
                if missing:
                    continue
                if profile["name"].startswith("_"):
                    profile["name"] = profile["name"][1:]
                    profiles.insert(0, profile)
                else:
                    profiles.append(profile)
        if profiles:
            return profiles

    def save(self, key, values, append=False):
        if not os.access(self._fileName, os.R_OK | os.W_OK):
            raise StorageException("Could not open settings file: %s" % self._fileName)
        key = key.lower()
        newValue = "%s %s" % (key, " ".join("%s" % value for value in values))
        lines = []
        stage = 0
        with self._fileLock:
            with open(self._fileName, "r+") as file:
                for line in file.read().split("\n"):
                    if line.startswith(key + " "):
                        stage = 1
                        if not append:
                            lines.append(newValue)
                        else:
                            lines.append(line)
                    else:
                        if stage == 1 and append:
                            stage = 2
                            lines.append(newValue)
                        lines.append(line)
                if append and stage < 2:
                    lines.append(newValue)
                file.seek(0)
                file.truncate()
                file.write("\n".join(lines))


if __name__ == '__main__':
    s = Storage()
    s.load()
    print(s.getSerial())
    print(s.getPidCoeffs())
    print(s.getShhCoeffs())
    print(s.getUref())
    print(s.getIref())
    print(s.getAdcComp())
    print(s.getProfiles())
    #s.save("profile", [2.0, 23.1, 1], True)
    pass