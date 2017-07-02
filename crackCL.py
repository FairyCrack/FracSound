#!/usr/bin/env python

import pyopencl as cl
import numpy as np

class CL:
    def __init__(self):
        found = False
        for platf in cl.get_platforms():
            for dev in  platf.get_devices():
                try:
                    self.ctx = cl.Context([dev])
                except:
                    print "DEVICE NOT AVAILABLE:", platf, dev, "\n"
                    continue
                else:
                    found = True
                    print "USING DEVICE:\n", dev, "\n"
                    break
            if found:
                self.queue = cl.CommandQueue(self.ctx)
                break
        if not found:
            print "NO DEVICE AVAILABLE"

    def loadProgram(self, str):
        try:
            #create the program
            self.program = cl.Program(self.ctx, str).build()
            return True
        except Exception as e:
            print "CL ERROR:\n", e, "\n"
        return False
        
    def setBuffers(self, data, out):
        mf = cl.mem_flags
        self.data = data
        self.inBuffers = []
        self.out = out
        self.outBuffers = []
        
        #create OpenCL buffers
        for v in data:
            self.inBuffers.append(cl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=v))
        
        for v in out:
            self.outBuffers.append(cl.Buffer(self.ctx, mf.WRITE_ONLY, v.nbytes))

    def execute(self, name, worksize):
        try:
            param = self.inBuffers+self.outBuffers
            #execute kernel
            if len(name) < 16:
                eval("self.program."+name)(self.queue, worksize, None, *param )
            #read output buffers
            for i,v in enumerate(self.outBuffers):
                cl.enqueue_read_buffer(self.queue, v, self.out[i]).wait()
        except Exception as e:
            print "CL ERROR:\n", e, "\n"
            
