import socket
import ffmpeg
import selectors
import numpy as np
from multiprocessing import Process, Queue
import queue

class Jpeg():
    
    SOI = b'\xff\xd8'
    EOI = b'\xff\xd9'

class JpegSender(Jpeg):

    def __init__(self, host, port, device):
        self.addr = (host, port)
        self.device = device
        self.name = socket.gethostname()
        self.running = False
        self.inb = b''
        self.sndsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sndsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ffproc = None

    def run_ffmpeg(self):
        ffcmd = ffmpeg.input(self.device, format='v4l2', input_format='mjpeg')
        ffcmd = ffmpeg.output(ffcmd, 'pipe:', format='mjpeg', vcodec='copy')
        self.ffproc = ffmpeg.run_async(ffcmd, pipe_stdout=True, pipe_stdin=True )
        self.running = True

    def stop_ffmpeg(self):
        self.ffproc.communicate(input='q'.encode())
        self.running = False

    def send_jpeg(self):
        self.sndsock.connect_ex(self.addr)
        while self.running:
            self.inb += self.ffproc.stdout.read(1024)
            start = self.inb.find(self.SOI)
            end = self.inb.find(self.EOI)
            if end > -1:
                if start > -1:
                    bname = self.name.encode()
                    msg = self.SOI + bytes([len(bname)]) + bname  + self.inb[start:end+2]
                    self.sndsock.sendall(msg)
                self.inb = self.inb[end+2:]


class JpegReceiver(Jpeg):
    
    def __init__(self, host, port, maxq=5):
        self.addr = (host, port)
        self.myname = 'skywatcher01' #socket.gethostname()
        self.q = Queue(maxsize=maxq)
        self.running = False
        self.inb = b''
        self.lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.lsock, selectors.EVENT_READ, self.accept_wrapper)
    
    def accept_wrapper(self, key, mask):
        sock = key.fileobj
        conn, addr = sock.accept()
        print('Accepted connection from {0}:{1}'.format(*addr))
        conn.setblocking(False)
        self.sel.register(conn, selectors.EVENT_READ, self.service_connection)

    def service_connection(self, key, mask):
        sock = key.fileobj
        recv_data = sock.recv(1024)
        if recv_data:
            #print("Recieved {0} bytes of data".format(len(recv_data)))
            # This approach is not, in general, correct for finding the start/end
            # of the JPEG image in the TCP stream. However, for the simple
            # MJPEG stream from the web cam, it appears to work fine.
            # Stream is modified with additional header that includes:
            # SOI(2b):NameLength(1b):RpiName(NameLength):(\n)-SOI... 
            self.inb += recv_data
            start = self.inb.find(self.SOI)
            end = self.inb.find(self.EOI)
            if end > -1:
                if start > -1:
                    namelen = self.inb[start+2]
                    header = self.inb[start:start+3+namelen]
                    jpeg = self.inb[start+3+namelen:end+2]
                    if jpeg[0:2] == self.SOI: 
                        name = header[3:3+namelen].decode()
                        try:
                            self.q.put_nowait((name, jpeg))
                        except queue.Full:
                            self.q.get()
                self.inb = self.inb[end+2:]
        else:
            self.sel.unregister(sock)
            sock.close()
     
    def run(self):
        w = Process(target=self.worker)
        self.running = True
        w.start()

    def stop(self):
        self.running = False
        self.unregister(self.lsock)
        self.lsock.close()
        self.q.close()
            
    def worker(self):
        self.lsock.bind(self.addr)
        self.lsock.listen()
        self.lsock.setblocking(False)
        print("listeneing on {0}:{1}".format(*self.addr))

        while self.running:
            events = self.sel.select(timeout=None)
            for key, mask in events:
                callback = key.data
                callback(key, mask)
        
