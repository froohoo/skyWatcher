#!/usr/bin/env python

from imutils.video import VideoStream
from imagezmq.imagezmq import ImageSender
import argparse
import socket
import time

#construct the argument parser and parse the arguments

parser = argparse.ArgumentParser()
parser.add_argument('-s', "--server-ip", required=True,
        help="ip address of the server to which the client will connect")
parser.add_argument('-p', "--port", required=True, 
        help="TCP port on which servier is listening")
args = vars(parser.parse_args())

# initialize the ImageSender object with the socket address of the server
sender = ImageSender(connect_to="tcp://{}:{}".format(
    args["server_ip"], args["port"]))
print(args)
# get the host name, initialize the video stream, and allow the
# camera sensor to warmup
rpiName = socket.gethostname()
vidStream = VideoStream(src=0).start()
time.sleep(2.0)

while True:
    # read the frame from the camera and send it to the server
    frame = vidStream.read()
    sender.send_image(rpiName, frame)


