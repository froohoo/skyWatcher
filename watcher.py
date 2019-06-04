#!/usr/bin/env python3

from jpegsockets import JpegSender
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('-s', "--server-ip", type=str, required=True,
        help="ip address of the server to which the client will connect")
parser.add_argument('-p', "--port", type=int, required=True, 
        help="TCP port on which servier is listening")
parser.add_argument('-d', "--device", type=str, required=False,
        default='/dev/video0', help="Video device to stream images from" )
args = vars(parser.parse_args())

try:
    js = JpegSender(args['server_ip'], args['port'], args['device'])
    js.run_ffmpeg()
    js.send_jpeg()

except KeyboardInterrupt:
    print("\n\n[INFO] Keyboard Interrupt, stopping ffmpeg & closing socket...")
    js.stop_ffmpeg
    js.sndsock.close()

