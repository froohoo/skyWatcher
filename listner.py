#!/usr/bin/env python3

# Project Libraries
from datetime import datetime
from jpegreceiver import JpegReceiver
from motionextractor import MotionExtractor
import helpers

# External Libraries
import numpy as np
import os.path as path
import imutils
import toml
import cv2

# read from config
try: 
    c = toml.load('skyWatcher.toml')
except FileNotFoundError:
    print("[ERROR] skyWatcher.toml not found")
    raise 

# over-ride config with command line args if present
args = helpers.getArgs(c)

annotater = helpers.ImageAnnotater(c)
print("[INFO] initializing annotation registration database...")
annotater.init_regDB()
print("[INFO] initializing annotation OpenSky client...")
annotater.init_openSky()
print("[INFO] spawning worker thread to handle annotations...")
annotater.run()
print("[INFO] spawning worker thread to receive jpeg's from clients")
jpegRecv = JpegReceiver(args['host'], args['socket'])
jpegRecv.run()
print("[INFO] initializing motion detector and mobileNet model...")
CLASSES = c['mobileNet']['CLASSES']
motionDetector = MotionExtractor()
net=cv2.dnn.readNetFromCaffe(args["prototxt"], args["model"])
CONSIDER = set(c['mobileNet']['CONSIDER'])
objcount = {obj: 0 for obj in CONSIDER}
frameDict = {}

ESTIMATED_NUM_PIS = 2
ACTIVE_CHECK_PERIOD = 10
ACTIVE_CHECK_SECONDS = ESTIMATED_NUM_PIS * ACTIVE_CHECK_PERIOD
lastActive = {}
lastActiveCheck = datetime.now()

mW = args["montageW"]
mH = args["montageH"]

print("[INFO] detecting: {}...".format(", ".join(obj for obj in CONSIDER)))

while True:
    (rpiName, jpeg) = jpegRecv.q.get()
    raw_frame = cv2.imdecode(np.fromstring(jpeg, np.uint8), cv2.IMREAD_COLOR) 
    if raw_frame is None: continue
    frame = raw_frame.copy()
    if rpiName not in lastActive.keys():
        print("[INFO] receiving data from {}...".format(rpiName))
    else:
        print("{0:.1f} FPS".format(1/(datetime.now() - lastActive[rpiName]).total_seconds()))
    lastActive[rpiName] = datetime.now()
    frame = motionDetector.getMotionCrop(frame)
    guiframe=frame.copy() 
    (h,w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300,300)), 
            0.007843, (300,300), 127.5)

    net.setInput(blob)
    detections = net.forward()
    objCount = {obj: 0 for obj in CONSIDER}

    for i in np.arange(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > args["confidence"]:
            idx = int(detections[0,0,i,1])
            if CLASSES[idx] in CONSIDER:
                print("[INFO] detection event...")
                d = helpers.Detection(frame,detections[0,0,i,3:7])
                annotater.q.put(d)
                box = detections[0,0,i,3:7] * np.array([w,h,w,h])
                (startX, startY, endX, endY) = box.astype("int")
                cv2.rectangle(guiframe, (startX, startY), (endX, endY), 
                        (255,0,0), 2)
                
                

    cv2.putText(guiframe,rpiName, (10,25), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0, 255), 2)
    label=", ".join("{}: {}".format(obj, count) for (obj, count) in
            objCount.items())
    cv2.putText(guiframe, label, (10, h-20), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
    label="Raw Image: " + str(raw_frame.shape)
    cv2.putText(raw_frame, label, (10,30), 
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 6)
    frameDict[rpiName+" raw"] = raw_frame
    frameDict[rpiName+" detections"] = guiframe
    frameDict[rpiName+" foreground"] = motionDetector.getForeground()
    montages = imutils.build_montages(frameDict.values(), (w,h), (mW, mH))

    for (i, montage) in enumerate(montages):
        cv2.imshow("Aircrafct Detection Monitor({})".format(i), 
                montage)
    key = cv2.waitKey(1) & 0xFF

    if (datetime.now() - lastActiveCheck).seconds > ACTIVE_CHECK_SECONDS:
        for(rpiName, ts) in list(lastActive.items()):
            if(datetime.now() - ts).seconds > ACTIVE_CHECK_SECONDS:
                print("[INFO] lost connection to {}".format(rpiName))
                lastActive.pop(rpiName)
                frameDict.pop(rpiName)

        lastActiveCheck = datetime.now()

    if key == ord("q"):
        break

cv2.destroyAllWindows()
