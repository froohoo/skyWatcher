#!/usr/bin/env python3
from sqlalchemy import Table, Column, Integer, Unicode, MetaData, create_engine
from sqlalchemy.orm import mapper, create_session
import csv
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


    def importData(self):
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

    def getRecord(self, str_icao24):
        record = self.query.filter(self.mapClass.icao24==str_icao24).one()
        return record.__dict__

def getArgs(config):
    c = config
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
    return vars(parser.parse_args())


def procImage(frame, box, record, imageFolder, imageNum):
    (h,w) = frame.shape[:2]
    bb = box * np.array([w,h,w,h])
    imagename=path.join(imageFolder, str(imageNum) +'.jpg')
    meatname=path.join(imageFolder, str(imageNum) + '.toml')
    metadata = {'imagename':imagename, 'bb':bb, 'record':record}
    cv2.imwrite(imagename, frame)
    with open(metaname, 'w') as f:
        toml.dump(metadata, f)
    
