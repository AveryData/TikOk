#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Apr  4 10:48:45 2020

@author: averysmith
"""

import pyaudio
import numpy as np
import pylab

CHUNK = 2**11
RATE = 44100

p=pyaudio.PyAudio()
stream=p.open(format=pyaudio.paInt16,channels=1,rate=RATE,input=True,
              frames_per_buffer=CHUNK)


for i in range(int(10*44100/1024)): #go for a few seconds
    data = np.fromstring(stream.read(CHUNK),dtype=np.int16)

    peak=np.average(np.abs(data))*2
    bars="#"*int(70*peak/2**16)
    print("%04d  %s"%(i,bars))

stream.stop_stream()
stream.close()
p.terminate()
