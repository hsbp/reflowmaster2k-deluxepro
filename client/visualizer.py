import reflowcntrl
import threading
from matplotlib import pyplot as plot

class Visualizer:

    def __init__(self, timebase, updateInterval, refData, updateCallback):
        self._updateInterval = updateInterval
        self._timebase = timebase
        self._refData = refData
        self._refDataLen = len(self._refData)
        self._liveData = None
        self._xdata = [i * self._timebase for i in range(self._refDataLen)]  # Linspace?
        self._updateCallback = updateCallback

        self._fig, self._axes = plot.subplots()
        self._liveDataLine = None
        plot.ion()

        self._drawThread = threading.Thread(target=self._draw)
        self._stopReq = threading.Event()

    def _draw(self):
        while not self._stopReq.isSet():
            self._liveData = self._updateCallback()
            liveDataLen = len(self._liveData)
            self._liveDataLine.set_ydata(self._liveData)
            self._liveDataLine.set_xdata(self._xdata[:liveDataLen])
            plot.draw()
            plot.pause(self._updateInterval)

    def start(self):
        self._axes.plot(self._xdata, self._refData, "b-")
        self._liveDataLine, = self._axes.plot([], [], "r-")
        plot.grid()
        plot.show()
        self._draw()
        #self._drawThread.start()

    def stop(self):
        self._stopReq.set()
        #self._drawThread.join()


if __name__ == '__main__':
    r = reflowcntrl.ReflowControl("")
    refData = r._profileToTt(reflowcntrl.profile)
    i = 0

    def gen():
        global i
        i += 1
        return refData[:i]

    v = Visualizer(0.5, 1, refData, gen)
    v.start()
    print("hello")


