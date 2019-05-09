#! /usr/bin/env python3

import requests

class AirTraffic():
    def __init__(self, geo, serviceInfo, session=False): 
        self.geo = geo
        self.serviceInfo = serviceInfo
        if session:
            self.session = requests.Session()
            self.session.auth = (serviceInfo['username'], serviceInfo['apikey'])
        else:
            self.session = None
    def set_geo(self, geo):
        self.geo = geo
    def set_serviceInfo(self, serviceInfo):
        self.serivceInfo = serviceInfo
    def get_geo(self):
        return self.geo
    def get_serviceInfo(self):
        return self.serviceInfo
    def get_airTraffic(self):
        if self.session:
            r = self.session.get(
                    self.serviceInfo['endpoint'], params=self.geo)
        else:
            r = requests.get(
                    self.serviceInfo['endpoint'], params=self.geo)
        if 'states' in r.json():
            return r.json()['states']
        else:
            return False
