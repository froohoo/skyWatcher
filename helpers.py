#!/usr/bin/env python3
from sqlalchemy import Table, Column, Integer, Unicode, MetaData, create_engine
from sqlalchemy.orm import mapper, create_session
from OpenSky import AirTraffic
from multiprocessing import Process, Queue
import csv,glob,toml
import argparse
import numpy as np
import cv2 as cv2
import os.path as path

class Records(object):
    pass

class RegistrationDB():

    def __init__(self,csvFile):
        self.csv = csvFile
        self.tablename = csvFile.split('.')[0]
        self.engine = create_engine('sqlite:///:memory:', echo=False)
        self.metadata = MetaData(bind=self.engine)
        self.headers = None
        self.table = None
        self.session = None
        self.query = None
        self.mapClass = Records
        self.record = None 


    def import_data(self):
        with open(self.csv, 'r') as f:
            r=csv.reader(f)
            self.headers = next(r)
            self.table = Table(self.tablename, self.metadata,
                    Column('id', Integer, primary_key=True),
                    *(Column(field, Unicode(50)) for field in self.headers))
            self.metadata.create_all()
            mapper(self.mapClass, self.table)
            self.session = create_session(bind=self.engine, autocommit=False,
                    autoflush=True)
            con = self.engine.raw_connection()
            cmd = 'INSERT INTO ' + self.tablename  + ' VALUES(null,' + \
                    (len(self.headers) * '?,')[:-1] + ')'
            con.executemany(cmd, r)
            con.commit()
            con.close()
            self.query = self.session.query(self.mapClass)

    def get_record(self, str_icao24):
        record = self.query.filter(self.mapClass.icao24==str_icao24).one()
        d = record.__dict__
        del d['_sa_instance_state']
        return d

def getNewestImgNum(imgPath):
    imageFolder = path.expanduser(imgPath)
    fileList = glob.glob(path.join(imageFolder,'*'))
    newest = max(fileList, key=path.getctime)
    return int(path.split(newest)[1].split('.')[0])

def getArgs(c):
    #construct the argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--prototxt", type=str,
            default=c['mobileNet']['prototxt'],
            help="path to Caffe 'deploy' prototxt file")
    parser.add_argument("-m", "--model", type=str,
            default=c['mobileNet']['model'],
            help="path to Caffe pre-trained model")
    parser.add_argument("-c", "--confidence", type=float, 
            default=c['mobileNet']['confidence'], 
            help="minimum probability to filter weak detections")
    parser.add_argument("-mW", "--montageW", type=int, 
            default=c['gui']['montageW'], 
            help="montage frame width")
    parser.add_argument("-mH", "--montageH", type=int,
            default=c['gui']['montageH'],
            help="montage frame height")
    parser.add_argument("-f", "--imageFolder", type=str,
            default=c['data']['imageFolder'],
            help="folder location to store images")
    parser.add_argument("-r", "--regDB", type=str,
            default=c['data']['regDB'],
            help="path to icao24 registration csv")
    parser.add_argument("-a", "--host", type=str,
            default=c['network']['host'],
            help="listening interface for client connections")
    parser.add_argument("-s", "--socket", type=int,
            default=c['network']['socket'],
            help="listening socket for client connections")
    return vars(parser.parse_args())

class Detection():

    def __init__(self,frame,box):
        self.frame = frame
        self.box   = box

    def get_frame(self):
        return self.frame

    def get_box(self):
        return self.box

    def set_frame(self, frame):
        self.frame = frame

    def set_box(self, box):
        self.box = box


class ImageAnnotater():

    def __init__(self, c, imgNum=None):
        self.q = Queue()
        self.regCSV = c['data']['regDB']
        self.imageFolder = path.expanduser(c['data']['imageFolder'])
        self.geofence = c['geofence']
        self.openSky = c['openSky']
        self.regDB = None
        self.traffic = None
        if imgNum is None:
            self.imageNum = getNewestImgNum(self.imageFolder) + 1
        else:
            self.imageNum = imageNum
    def init_regDB(self):
        if self.regDB is None:
            self.regDB = RegistrationDB(self.regCSV)
            self.regDB.import_data()
 
    def init_openSky(self):
        if self.traffic is None:
            self.traffic= AirTraffic(self.geofence, self.openSky)

    def run(self):
        if (self.regDB is None) or (self.traffic is None):
            self.init_regDB()
            self.init_openSky()
        w = Process(target=self.worker)
        w.start()
        #w.join()

    def worker(self):
        while True:
            d = self.q.get(block=True)
            img = d.get_frame()
            box = d.get_box()
            print('Got a message with bb: ', box)
            (h,w) = img.shape[:2]
            bb = box * np.array([w,h,w,h])
            bb = bb.astype("int")
            traffic = self.traffic.get_traffic()
            if traffic is None: continue
            icao24 = traffic[0][0]
            record = self.regDB.get_record(icao24)
            imagename = path.join(self.imageFolder, str(self.imageNum) +'.jpg')
            metaname = path.join(self.imageFolder, str(self.imageNum) + '.toml')
            metadata = {'imagename':imagename, 'bb':bb, 'record':record}
            cv2.imwrite(imagename, img)
            with open(metaname, 'w') as f:
                toml.dump(metadata, f)
            self.imageNum += 1


