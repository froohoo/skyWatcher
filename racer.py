#!/usr/bin/env python3

from jpegsockets import JpegReceiver
from datetime import datetime

HOST = '10.42.0.1'
PORT = 65432

jpr = JpegReceiver(HOST, PORT)

jpr.run()
start = datetime.now()
count = 0
while True:
    (host,jpeg) = jpr.q.get()
    if count%100: 
        count += 1
    else:
        print("FPS: {0:.2f}".format(count/(datetime.now()-start).total_seconds()))
        count = 1
        start = datetime.now()
        


