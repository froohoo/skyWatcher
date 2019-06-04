import cv2
import numpy as np

# MotionExtracton class. Convienience class to simplify the extraction
# of a ROI where objects are moving from a stream of images. 
# returns the cropped region of interest of size resolution.

class MotionExtractor:
    def __init__(self, history=5, resolution=(300,300), dist2Threshold=2800.0,
            detectShadows=False):
        self.outW = resolution[0]
        self.outH = resolution[1]
        self.fgmask = None
        self.img = None
        self.erosion_kernel = np.ones((5,5), np.uint8)
        self.backgroundSubtractor = cv2.createBackgroundSubtractorKNN(history, 
                dist2Threshold, detectShadows)
    def update(self, img):
        self.img = img
        self.fgmask = self.backgroundSubtractor.apply(img)
        self.fgmask = cv2.erode(self.fgmask, self.erosion_kernel,iterations=1)
    def getBackground(self):
        return self.backgroundSubtractor.getBackgroundImage()
    def getFgmask(self):
        return self.fgmask
    def getForeground(self):
        return cv2.bitwise_and(self.img, self.img, mask=self.fgmask)
    def getMotionCrop(self,img):
        self.update(img)
        l,t,w,h = cv2.boundingRect(self.fgmask)
        center = [l + w//2, t + h//2]
        center[0] = np.clip(center[0], self.outW//2, img.shape[1]-self.outW//2)
        center[1] = np.clip(center[1], self.outH//2, img.shape[0]-self.outH//2)
        l = center[0] - self.outW//2
        t = center[1] - self.outH//2
        w = self.outW
        h = self.outH
        #print(l,t,w,h)
        if (w>50 and h>50): 
            return img[t:t+h, l:l+w]
        else:
            return img

        
        



