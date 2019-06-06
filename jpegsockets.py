import socket
import selectors
import struct
from multiprocessing import Process, Queue
import queue

try:
    import ffmpeg
except ImportError:
    print("[WARN] could not import ffmpeg.. if this is the listner, that is fine")
    
class Jpeg():
    
    SOI = b'\xff\xd8'
    EOI = b'\xff\xd9'
    COM = b'\xff\xfe'

class JpegSender(Jpeg):

    def __init__(self, host, port, device):
        self.addr = (host, port)
        self.device = device
        self.name = socket.gethostname()
        self.running = False
        self.outb = b''
        self.sndsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sndsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ffproc = None
        
        bname = self.name.encode()
        COMlen = struct.pack('>h', len(bname)+2)
        self.COMfld = self.COM + COMlen +  bname
        self.running = False

    def run_ffmpeg(self):
        ffcmd = ffmpeg.input(self.device, format='v4l2', input_format='mjpeg',
                s='svga', r=7.5)
        ffcmd = ffmpeg.output(ffcmd, 'pipe:', format='mjpeg', vcodec='copy')
        self.ffproc = ffmpeg.run_async(ffcmd, pipe_stdout=True, pipe_stdin=True )
        self.running = True

    def stop_ffmpeg(self):
        self.ffproc.communicate(input='q'.encode())
        self.running = False

    def send_jpeg(self):
        if not self.running:
            self.run_ffmpeg()
        self.sndsock.connect_ex(self.addr)
        while self.running:
            rcv_data = self.ffproc.stdout.read(1024)
            if rcv_data:
                if self.SOI in rcv_data:
                    soi = rcv_data.find(self.SOI)
                    self.outb += rcv_data[:soi+2] 
                    self.outb += self.COMfld + rcv_data[soi+2:]
                else:
                    self.outb += rcv_data
            sent = self.sndsock.send(self.outb)
            self.outb = self.outb[sent:]


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
            # This approach is not, in general, correct for finding the start/end
            # of the JPEG image in the TCP stream. However, for the simple
            # MJPEG stream from the web cam, it appears to work fine.
            # Stream is modified with additional header that includes:
            # SOI(2b):NameLength(1b):RpiName(NameLength):(\n)-SOI... 
            if self.EOI in recv_data:
                eoi = recv_data.find(self.EOI)
                soi = self.inb.find(self.SOI)
                jpeg = self.inb[soi:] + recv_data[:eoi+2]
                self.inb = recv_data[eoi+2:]
                COMlenpos = jpeg.find(self.COM) + 2
                try:
                    COMlen, = struct.unpack('>h', jpeg[COMlenpos:COMlenpos+2])
                    bname = jpeg[COMlenpos+2:COMlenpos+COMlen]
                    name = bname.decode()
                    self.q.put_nowait((name, jpeg))
                except UnicodeDecodeError:
                    print('[INFO] Corrupt Comment field: {0:b}'.format(bname))
                except queue.Full:
                    self.q.get()
            else:
                self.inb += recv_data
        else:
            self.sel.unregister(sock)
            sock.close()
     
    def run(self):
        w = Process(target=self.worker)
        self.running = True
        w.start()

    def stop(self):
        self.running = False
        self.sel.unregister(self.lsock)
        self.lsock.close()
        self.q.close()
        self.sel.close()
            
    def worker(self):
        self.lsock.bind(self.addr)
        self.lsock.listen()
        self.lsock.setblocking(False)
        print("listeneing on {0}:{1}".format(*self.addr))

        try:
            while self.running:
                events = self.sel.select(timeout=None)
                for key, mask in events:
                    callback = key.data
                    callback(key, mask)
        
        except KeyboardInterrupt: 
            print("[INFO] Keyboard Interrupt, stopping and closing socket...")
            self.stop()
