#!/usr/bin/env python

import crackCL
import os
import sys
import struct
import Queue
import time
import wave
import numpy as np
from scipy import interpolate
import pyaudio
from threading import Thread
from PyQt4 import QtCore, QtGui, uic


BASE_DIR = os.path.dirname(os.path.realpath(__file__))+"/"
qtCreatorFile = BASE_DIR + "view/main_view.ui"
 
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)
 
class FracSound(QtGui.QMainWindow, Ui_MainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)
        
        self.draw_area_ratio = float(self.draw_area.size().height())/self.draw_area.size().width()
        
        self.cl = crackCL.CL()
        self.sp = SamplePlayer()
        self.path = self.mkPath()
        self.domain = [-0.5,0,4,self.draw_area_ratio*4]
        self.points = []
        self.pathColor = QtGui.QColor(255,0,0)
        self.programLoaded = False
        self.baseFreq = self.base_freq_box.value()
        self.resizing = False
        self.anotherResize = False
        
        #ui handling
        self.installEventFilter(self)
        self.base_freq_box.valueChanged.connect(self.setBaseFreq)
        self.forward_opt.clicked.connect(self.sp.setForward)
        self.reverse_opt.clicked.connect(self.sp.setReverse)
        self.alternate_opt.clicked.connect(self.sp.setAlternate)
        self.play_button.installEventFilter(self)
        self.draw_area.installEventFilter(self)  
        self.file_button.installEventFilter(self)
        self.rec_button.installEventFilter(self)
        self.del_path_button.installEventFilter(self)
        self.del_point_button.installEventFilter(self)
    
    #top level application logic
    def eventFilter(self, o, e):
        '''
        if e.type() == :
            if self.wasResized:
                self.wasResized = False
                print "YO"
                self.updateImg()
                self.repaint()
        '''
        if o.objectName() == "draw_area":
            if e.type() == QtCore.QEvent.Resize:
                self.draw_area_ratio = float(self.draw_area.size().height())/self.draw_area.size().width()
                self.domain[3] = self.domain[2]*self.draw_area_ratio
                
                def endResize():
                    if self.anotherResize:
                        upd()
                    else:
                        self.resizing = False
                def upd():
                    self.anotherResize = False
                    self.resizeTimer = QtCore.QTimer()
                    self.resizeTimer.singleShot(500, endResize)
                    self.updateImg()
                    o.repaint()
                if not self.resizing:
                    self.resizing = True
                    upd()
                else:
                    self.anotherResize = True
                    
            elif e.type() == QtCore.QEvent.Paint:
                qp = QtGui.QPainter()
                qp.begin(o)
                if self.programLoaded == True:
                    qp.drawImage(QtCore.QPoint(0,0), self.frac_img)
                else:
                    clear_color = QtGui.QColor(0,0,0)
                    qp.fillRect(QtCore.QRect(0,0,self.draw_area.size().width(),self.draw_area.size().height()),clear_color)
                pen = QtGui.QPen(self.pathColor)
                qp.setPen(pen)
                qp.drawPath(self.path.getQtPath())
                pen.setWidth(4)
                qp.setPen(pen)
                for p in self.path.points:
                    qp.drawPoint(QtCore.QPointF(*self.posFromDomain(p)))
                qp.end()
                return True
            elif e.type() == QtCore.QEvent.Wheel:
                scale = 0.001* e.delta()
                mPos = self.posInDomain(e.pos())
                self.domain[2] -= self.domain[2]*scale
                self.domain[3] -= self.domain[3]*scale
                self.domain[0] += abs(scale)*(mPos[0]-self.domain[0])
                self.domain[1] += abs(scale)*(mPos[1]-self.domain[1])
                
                self.updateImg()
                o.repaint()
                return True
            elif e.type() == QtCore.QEvent.MouseButtonRelease:
                self.path.addPoints([self.posInDomain(e.pos())])
                self.updateSnd()
                o.repaint()
                return True
                
        elif o.objectName() == "rec_button":
            if e.type() == QtCore.QEvent.MouseButtonRelease and self.programLoaded:
                fName = BASE_DIR + "out.wav"

                if not self.sp.recording:
                    print "WRITING WAVE FILE:\n", os.path.abspath(fName), "\n"
                    self.outFile = wave.open(fName, 'wb')
                    self.outFile.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
                    self.sp.recTo(self.outFile)
                    o.setText("Recording ...")
                else:
                    self.sp.recEnd()
                    self.outFile.close()
                    o.setText("Record")
                return True
        
        elif o.objectName() == "play_button":
            if e.type() == QtCore.QEvent.MouseButtonRelease and self.programLoaded:
                if self.sp.playing:
                    self.sp.stop()
                    o.setText("Play")
                else:
                    self.updateSnd()
                    self.sp.play()
                    o.setText("Stop")
                return True
                
        elif o.objectName() == "file_button":
            if e.type() == QtCore.QEvent.MouseButtonRelease:
                f = QtGui.QFileDialog.getOpenFileName(directory=BASE_DIR + "programs/")
                
                if self.loadProgram(f): 
                    self.file_line.setText(f)
                else:
                    self.file_line.setText("NO PROGRAM")
                self.updateImg()
                self.repaint()
                return True
                
        elif o.objectName() == "del_path_button":
            if e.type() == QtCore.QEvent.MouseButtonRelease:
                self.path.clear()
                self.updateSnd()
                self.repaint()
                return True
                
        elif o.objectName() == "del_point_button":
            if e.type() == QtCore.QEvent.MouseButtonRelease:
                self.path.delPoint()
                self.updateSnd()
                self.repaint()
                return True
                
        return False
     
    def updateImg(self):
        if self.programLoaded:
            x = self.domain[0]
            y = self.domain[1]
            w = self.domain[2]
            h = self.domain[3]
            xArray = np.linspace(x-w/2.0, x+w/2.0, self.draw_area.size().width(), dtype=np.float32)
            yArray = np.linspace(y-h/2.0, y+h/2.0, self.draw_area.size().height(), dtype=np.float32)
            q = Queue.Queue()
            t = Thread(target=renderImg, args=(self.cl, xArray, yArray, q))
            t.start()
            self.frac_img = q.get()
            
    def updateSnd(self):
        if self.programLoaded:
            a = self.path.getArrays(44100/self.baseFreq)
            q = Queue.Queue()
            t = Thread(target=renderSnd, args=(self.cl, a[0].astype(np.float64), a[1].astype(np.float64), q))
            t.start()
            self.sp.setSample(q.get())
        
    def loadProgram(self, file):
        if file: 
            with open(file, 'r') as f:
                fstr = "".join(f.readlines())
                f.close()
                if self.cl.loadProgram(fstr):
                    self.programLoaded = True
                    return True
        return False
  
    def posInDomain(self, pos):
        x = self.domain[0] + (float(pos.x())/self.draw_area.size().width()-0.5)*self.domain[2]
        y = self.domain[1] + (float(pos.y())/self.draw_area.size().height()-0.5)*self.domain[3]
        return (x,y)
        
    def posFromDomain(self, pos):
        x = ((pos[0]-self.domain[0])/self.domain[2]+0.5)*self.draw_area.size().width()
        y = ((pos[1]-self.domain[1])/self.domain[3]+0.5)*self.draw_area.size().height()
        return (x,y) 
        
    def setBaseFreq(self, f):
        self.baseFreq = f
        self.updateSnd()
        
    def mkPath(instPass):
        FS = instPass
        class Path:
            def __init__(self):
                self.points = []
                self.qtPath = QtGui.QPainterPath()
                self.qtFactor = 100
                
            def getQtPath(self):
                l = len(self.points)
                if l > 0:
                    self.qtPath = QtGui.QPainterPath()
                    ts = np.linspace(0, l-1, (l-1)*self.qtFactor, endpoint=True)
                    self.qtPath.moveTo(QtCore.QPointF(*FS.posFromDomain(self.points[0])))
                    for t in ts[1:]:
                        self.qtPath.lineTo(QtCore.QPointF(*FS.posFromDomain([self.xSpline(t),self.ySpline(t)])))
                return self.qtPath
            
            def getArrays(self,samples):
                l = len(self.points)
                if l > 1:
                    xfunc = np.vectorize(self.xSpline)
                    yfunc = np.vectorize(self.ySpline)
                    ts = np.linspace(0, l-1, samples, endpoint=True)
                    return (xfunc(ts),yfunc(ts))
                return (np.zeros(1),np.zeros(1))
            def addPoints(self,pList):
                self.points.extend(pList)
                l = len(self.points)
                deg = 3
                if l <= deg: deg = l-1
                if deg <  1: return
                
                a = np.array(self.points)
                t = np.arange(len(self.points))
                self.xSpline = interpolate.InterpolatedUnivariateSpline(t,a[:,0],k=deg)
                self.ySpline = interpolate.InterpolatedUnivariateSpline(t,a[:,1],k=deg)
            
            def delPoint(self):
                l = len(self.points)
                if l < 1: return
                self.points.pop()
                l -= 1
                deg = 3
                if l <= deg: deg = l-1
                if deg <  1: 
                    self.xSpline = None
                    self.ySpline = None
                    return
                
                a = np.array(self.points)
                t = np.arange(len(self.points))
                self.xSpline = interpolate.InterpolatedUnivariateSpline(t,a[:,0],k=deg)
                self.ySpline = interpolate.InterpolatedUnivariateSpline(t,a[:,1],k=deg)
                
            def clear(self):
                self.points = []
                self.xSpline = None
                self.ySpline = None
                self.qtPath = QtGui.QPainterPath()
        return Path()
    
class SamplePlayer:
    def __init__(self, channels=1, rate=44100):
        self.channels = channels
        self.rate = rate
        self.mode = "f"
        self.altFlag = False
        self.playing = False
        self.recording = False
    def setForward(self):
        self.mode = "f"
    def setReverse(self):
        self.mode = "r"
    def setAlternate(self):
        self.mode = "a"
    def setSample(self, arr):
        self.sample = arr
    def callback(self, in_data, frame_count, time_info, status):
        data = np.zeros(frame_count, dtype=np.int16)
        if self.mode == "f":
            data = self.sample.take(range(self.frame,self.frame+frame_count), mode="wrap")
            self.frame += frame_count
        elif self.mode == "r":
            data = self.sample.take(range(self.frame,self.frame-frame_count,-1), mode="wrap")
            self.frame -= frame_count
        elif self.mode == "a":
            fbSample = np.concatenate((self.sample,self.sample[::-1]))
            data = fbSample.take(range(self.frame,self.frame+frame_count), mode="wrap")
            self.frame += frame_count
        
        if self.recording:
            self.wave.writeframes(data.tobytes())
            
        return (data.astype(np.int16), pyaudio.paContinue)
        
    def play(self):
        self.frame = 0
        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(format=self.pa.get_format_from_width(2),
                                    channels=self.channels,
                                    rate=self.rate,
                                    output=True,
                                    stream_callback=self.callback)
        self.stream.start_stream()
        self.playing = True
    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
        self.playing = False
        if self.recording:
            self.recEnd()
    def recTo(self, wave):
        self.wave = wave
        self.recording = True
    def recEnd(self):
        self.recording = False
        
def renderImg(cl, xArray, yArray, queue):
    d = [xArray,yArray]
    o = np.zeros( (xArray.size,yArray.size) , np.int32)
    cl.setBuffers(d,[o])
    cl.execute("img", o.shape)
    imgData =  o.ravel()
    queue.put(QtGui.QImage(imgData, xArray.size, yArray.size, QtGui.QImage.Format_RGB32))

def renderSnd(cl, xArray, yArray, queue):
    d = [xArray,yArray]
    o = np.zeros( xArray.size , np.int16)
    cl.setBuffers(d,[o])
    cl.execute("snd", o.shape)
    sndData =  o.ravel()
    queue.put(sndData)

def writeWav(fName, data):
    print "WRITING WAVE FILE:\n", os.path.abspath(fName)
    f = wave.open(fName, 'w')
    f.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
    f.writeframes(data)
    f.close()
    pa = pyaudio.PyAudio()
    stream = pa.open(format=pa.get_format_from_width(2),
                    channels=1,
                    rate=44100,
                    output=True)
    stream.write(data)
    stream.stop_stream()
    stream.close()
    pa.terminate()
    
    print "WRITE FINISHED\n"
    
if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    w = FracSound()
    w.show()
    sys.exit(app.exec_())
   
    
