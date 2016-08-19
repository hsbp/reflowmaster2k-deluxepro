import multiprocessing
import Queue
import time

class Visualizer:

    def __init__(self):
        self._drawProcess = multiprocessing.Process(target=self._draw)
        self._graphData = multiprocessing.Queue()
        self._stopReq = multiprocessing.Event()
        self._exitReq = multiprocessing.Event()
        self._clearReq = multiprocessing.Event()
        self._clearDone = multiprocessing.Event()
        self._drawLive = multiprocessing.Event()
        self._scrollLive = multiprocessing.Event()
        self._startTime = 0
        self._processStarted = False

    def _draw(self):
        from matplotlib import pyplot as plot
        fig, axes = plot.subplots()
        fig.canvas.set_window_title('Reflow process')
        fig.canvas.mpl_connect('close_event', self._onClosed)
        plot.ion()
        plot.grid()
        plot.show()
        while not self._exitReq.is_set():
            refDataX, refDataY = self._graphData.get()
            refDataLen = len(refDataX)
            liveDataX = []
            liveDataY = []
            axes.plot(refDataX, refDataY, "b-")
            liveDataLine, = axes.plot(liveDataX, liveDataY, "r-")
            axes.set_xlim([0, refDataX[-1] * 1.1])
            axes.set_ylim([min(refDataX) * 0.9, max(refDataY) * 1.1])
            plot.draw()
            while not self._stopReq.is_set():
                try:
                    while True:
                        newPoint = self._graphData.get(block=False)
                        liveDataY.append(newPoint[1])
                        liveDataX.append(newPoint[0])
                        liveDataLine.set_xdata(liveDataX)
                        liveDataLine.set_ydata(liveDataY)
                except Queue.Empty:
                    pass
                plot.pause(1)
            while not self._clearReq.is_set():
                plot.pause(1)
            for line in axes.lines:
                line.remove()
            plot.draw()
            self._clearQueue()
            self._clearReq.clear()
            self._clearDone.set()

    def _onClosed(self, event):
        pass

    def _clearQueue(self):
        while not self._graphData.empty():
            try:
                self._graphData.get(block=False)
            except Queue.Empty:
                continue

    def _clearPlot(self):
        self.disableLive()
        self._clearReq.set()
        self._clearDone.wait()
        self._clearDone.clear()

    def init(self, refData):
        if self._processStarted:
            self._clearPlot()
        self._clearQueue()
        self._graphData.put(refData)
        if not self._processStarted:
            self._processStarted = True
            self._drawProcess.start()

    def enableLive(self):
        self._startTime = 0
        self._stopReq.clear()
        self._drawLive.set()
        self._startTime = time.time()

    def disableLive(self):
        self._stopReq.set()
        self._drawLive.clear()

    def scrollLive(self, enable):
        if enable:
            self._scrollLive.set()
        else:
            self._scrollLive.clear()

    def update(self, value):
        elapsed = time.time() - self._startTime
        if self._drawLive.is_set():
            self._graphData.put((elapsed, value))

    def stop(self):
        self.disableLive()
        self._clearReq.set()
        self._exitReq.set()
