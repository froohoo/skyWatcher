#!/usr/bin/env python3

from datetime import datetime
from OpenSky import AirTraffic
from multiprocessing import Process, Queue
import numpy as np
from threading import Thread
import imagezmq.imagezmq as imagezmq
import imutils
import toml
from motionextractor import MotionExtractor
import cv2
import helpers

# read from config
try: 
    c = toml.load('skyWatcher.toml')
except FileNotFoundError:
    print("[ERROR] skyWatcher.toml not found")
    raise 

# over-ride config with command line args if present
args = helpers.getArgs(c)

imageNum = 0
imageHub = imagezmq.ImageHub()

print("[INFO] creating opensky-network.org session...")
traffic = AirTraffic(c['geofence'], c['openSky'], session=False)
traffic.get_airTraffic()

print("[INFO] loading aircraft registration data ...")
acDB = helpers.RegistrationDB(args['regDB'])
acDB.importData()

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
    (rpiName, raw_frame) = imageHub.recv_image()
    imageHub.send_reply(b'OK')
    frame = np.copy(raw_frame)
    if rpiName not in lastActive.keys():
        print("[INFO] receiving data from {}...".format(rpiName))

    lastActive[rpiName] = datetime.now()
    print(frame.shape)
    frame = motionDetector.getMotionCrop(frame)
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
                print("[INFO] Detection...")
                at = traffic.get_airTraffic()
                record = acDB.getRecord(at[0][0])
                objCount[CLASSES[idx]] += 1
                dethandler = Thread(target=helpers.procImage,
                        args=(frame, detections[0,0,i,3:7], record, 
                            args['imageFolder'], imageNum))
                dethandler.start()
                '''
                box = detections[0,0,i,3:7] * np.array([w,h,w,h])
                (startX, startY, endX, endY) = box.astype("int")
                filename=path.join(args['imageFolder'], str(imageNum)+'.jpg')
                print(traffic.get_airTraffic())
                cv2.imwrite(filename, raw_frame)
                cv2.rectangle(frame, (startX, startY), (endX, endY), 
                        (255,0,0), 2)
                '''
                imageNum += 1
                

    cv2.putText(frame,rpiName, (10,25), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0, 255), 2)
    label=", ".join("{}: {}".format(obj, count) for (obj, count) in
            objCount.items())
    cv2.putText(frame, label, (10, h-20), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
    label="Raw Image: " + str(raw_frame.shape)
    cv2.putText(raw_frame, label, (10,30), 
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,255), 6)
    frameDict[rpiName+" raw"] = raw_frame
    frameDict[rpiName+" detections"] = frame
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
