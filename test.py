# from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QApplication, QGraphicsScene, QMainWindow
from PyQt5 import uic
from PyQt5.QtCore import QObject, QThread, pyqtSignal

import pyqtgraph as pg
import numpy as np

import threading
import sys
import time
import os
ui_path = os.path.dirname(os.path.abspath(__file__))


class Mainwin(QMainWindow):
    def __init__(self):
        self.app = QApplication(sys.argv)
        super(Mainwin, self).__init__()
        # self.ui_path = os.path.dirname(os.path.abspath(__file__))
        uic.loadUi(os.path.join(ui_path, "MainWin.ui"), self)
        self.show()

        # Initialize the showing window
        # Create a roi
        self.data = self.data_fetch()
        roi_size = (20, 20)
        roi_position = (0, 0)
        self.roi = pg.RectROI(roi_position, roi_size, pen=(0, 9))

        self.img1 = pg.ImageItem()
        scene1 = QGraphicsScene()
        widget1 = pg.GraphicsLayoutWidget()
        p1 = widget1.addPlot()
        p1.addItem(self.img1)
        p1.addItem(self.roi)
        s = self.GraphicsWin.size()
        widget1.resize(s*0.99)
        scene1.addWidget(widget1)
        self.GraphicsWin.setScene(scene1)

        scene2 = QGraphicsScene()
        widget2 = pg.GraphicsLayoutWidget()
        self.p2 = widget2.addPlot()
        s = self.GraphicsSecWin.size()
        widget2.resize(s*0.99)
        scene2.addWidget(widget2)
        self.GraphicsSecWin.setScene(scene2)

        self.roi.sigRegionChanged.connect(self.update_secondWindow)
        # self.btn_changeImg.clicked.connect(self.update_mainWindow)

        self.CameraSelection.currentIndexChanged.connect(self.update_graph)

        self.btn_calculation.clicked.connect(self.runTask)

    def update_mainWindow(self):
        self.img1.setImage(self.data)
        self.update_secondWindow()

    def update_secondWindow(self):
        self.dataROI = self.roi.getArrayRegion(self.data, self.img1)
        self.slices = self.dataROI.sum(axis=1)
        self.p2.plot(self.slices, pen=(0, 0, 255), clear=True)

    def data_fetch(self):
        cam_type = self.CameraSelection.currentText()
        if (cam_type == "Camera 1"):
            arr = np.ones((100, 100), dtype=float)
            arr[45:55, 45:55] = 0
            arr[25, :] = 5
            arr[:, 25] = 5
            arr[75, :] = 5
            arr[:, 75] = 5
            arr[50, :] = 10
            arr[:, 50] = 10
            arr += np.sin(np.linspace(0, 20, 100)).reshape(1, 100)
            arr += np.random.normal(size=(100, 100))
        elif (cam_type == "Camera 2"):
            arr = np.random.normal(size=(200, 100))
            arr[20:80, 20:80] += 2
            arr = pg.gaussianFilter(arr, (3, 3))
            arr += np.random.normal(size=(200, 100))*0.1
        else:
            arr = np.zeros((100, 100))
        return arr

    def update_graph(self):
        self.data = self.data_fetch()
        self.update_mainWindow()

    def runTask(self):
        self.calmode = Calculation()
        self.calmode.setup(self)
        self.thread = QThread()
        self.thread.start()
        self.calmode.moveToThread(self.thread)
        self.thread.started.connect(self.calmode.calculation)

        self.calmode.finished.connect(self.thread.quit)
        self.calmode.showPos.connect(
            lambda pos: update_position(self.iterationShowing, pos))
        self.calmode.plotImg.connect(self.Calmode_update_graph)
        self.calmode.progress.connect(
            lambda pos, progress: update_progress(self.calmode.displayResWin.iterationShowing, self.calmode.displayResWin.progressBar, pos, progress))

    def Calmode_update_graph(self):
        self.update_mainWindow()

# Show the result in Calculation window


class CalcuWin(QMainWindow):
    def __init__(self):
        super(CalcuWin, self).__init__()
        uic.loadUi(os.path.join(ui_path, "Calculation.ui"), self)
        self.show()
        self.setWindowTitle("Calculation Window")


# Do the calculation task
class Calculation(QObject):
    finished = pyqtSignal()
    showPos = pyqtSignal(int)
    plotImg = pyqtSignal()
    progress = pyqtSignal(int, int)

    def setup(self, mainWin):
        self.mainWin = mainWin
        self.displayResWin = CalcuWin()
        self.end = self.mainWin.Iteration.value()
        print(self.end)

    def calculation(self):
        self.flag_start_motor = True
        self.step = 0

        self.flag_thread_shutter = True
        self.cond_shutter = 0
        self.flag_start_shutter = False
        self.speed_shutter = 0

        self.flag_thread_camera = True
        self.flag_start_camera = False

        self.flag_thread_plotResult = True
        self.flag_start_plotResult = False

        t0 = threading.Thread(target=self.thread_motor)
        t1 = threading.Thread(target=self.thread_shutter)
        t2 = threading.Thread(target=self.thread_camera)
        t3 = threading.Thread(target=self.thread_plotResult)

        t0.start()
        t1.start()
        t2.start()
        t3.start()
        t0.join()
        print("All threads finished!!!!")
        self.finished.emit()

    # (Task) Move the main motor

    def thread_motor(self):
        while self.step <= self.end:
            if self.flag_start_motor:
                print("Thread Motor")
                time.sleep(1)
                self.step += 1
                self.showPos.emit(self.step)
                self.cond_shutter = 0
                self.flag_start_shutter = True
                self.flag_start_motor = False

        self.flag_thread_shutter = False
        self.flag_thread_camera = False
        self.flag_thread_plotResult = False

    # (Task1) Control the shutter
    def thread_shutter(self):
        while self.flag_thread_shutter:
            if self.flag_start_shutter:
                if self.cond_shutter == 0:
                    self.flag_start_shutter = False
                    print("Thread Shutter 0")
                    self.flag_start_camera = True
                    time.sleep(1)
                else:
                    self.flag_start_shutter = False
                    print("Thread Shutter 1")
                    self.speed_shutter += 1
                    self.flag_start_camera = True
                    time.sleep(1)
                # self.flag_start_motor = True

    # (Task2) Control the camera to get the image
    def thread_camera(self):
        while self.flag_thread_camera:
            # if self.flag_start_camera:
            if self.flag_start_camera and self.flag_start_motor == False:
                if self.cond_shutter == 0:
                    self.flag_start_camera = False
                    print("Thread Camera")
                    time.sleep(1)
                    arr = np.ones((100, 100), dtype=float)
                    arr[45:55, 45:55] = 0
                    arr[25, :] = 5
                    arr[:, 25] = 5
                    arr[75, :] = 5
                    arr[:, 75] = 5
                    arr[50, :] = 10
                    arr[:, 50] = 10
                    arr += np.sin(np.linspace(0, 20, 100)).reshape(1, 100)
                    arr += np.random.normal(size=(100, 100))
                    self.data_open = arr
                    self.mainWin.data = self.data_open
                    self.plotImg.emit()
                    self.cond_shutter = 1
                    self.flag_start_shutter = True
                else:
                    self.flag_start_camera = False
                    print("Thread Camera")
                    time.sleep(1)
                    arr = np.random.normal(size=(200, 100))
                    arr[20:80, 20:80] += 2
                    arr = pg.gaussianFilter(arr, (3, 3))
                    arr += np.random.normal(size=(200, 100))*0.1
                    self.data_close = arr
                    self.mainWin.data = self.data_close
                    self.plotImg.emit()
                    self.flag_start_plotResult = True

    def thread_plotResult(self):
        while self.flag_thread_plotResult:
            if self.flag_start_plotResult:
                print("Thread PlotResult")
                self.flag_start_plotResult = False
                self.progress.emit(self.step, self.speed_shutter*10)
                self.flag_start_motor = True


def update_position(iterationShowing, pos):
    iterationShowing.display(pos)


def update_progress(iterationShowing, progressBar, pos, progress):
    iterationShowing.display(pos)
    progressBar.setValue(progress)

# def Calmode_update_graph(Mainwin):
#     Mainwin.update_mainWindow()


if __name__ == '__main__':
    app = QApplication([])
    window = Mainwin()
    sys.exit(app.exec_())
