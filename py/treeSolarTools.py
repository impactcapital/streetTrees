#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec  6 11:56:34 2022

@author: joe
"""

import numpy as np
import pandas as pd
import boto3
from botocore import UNSIGNED
from botocore.client import Config
import json
from pyproj import Transformer
import laspy #ensure laz handler installed: pip install "laspy[lazrs,laszip]"
import matplotlib.pyplot as plt
import os
from time import sleep
import math

#

def readGeoJSON(filepath):
    with open(filepath) as f:
        features = json.load(f)["features"]                
    return features

def footprintPointsFromGeoJSON(feature):   
    points = []
    name = feature["properties"]["name"] 
    
    for polygonPart in feature["geometry"]["coordinates"]:
        for polygonSubPart in polygonPart:
            for coordinates in polygonSubPart:
                point = [coordinates[0],coordinates[1]]
                points.append(point)
                point = [coordinates[0],coordinates[1]]
                points.append(point)                  
    return points, name

def convertLatLon(lat,lon,epsgNumber=2263):
    transformer = Transformer.from_crs( "epsg:4326", "epsg:{}".format(epsgNumber) ) 
    x, y = transformer.transform(lat, lon)
    return x, y

def getLazFile(lazfilename):
    with laspy.open(lazfilename) as lz:
        las = lz.read()
        lidarPoints = np.array((las.X,las.Y,las.Z,las.intensity,las.classification, las.return_number, las.number_of_returns)).transpose()
        lidarDF = pd.DataFrame(lidarPoints)
        lidarDF.columns = ['X', 'Y', 'Z', 'intens', 'class', 'return_number', 'number_of_returns']
        lidarDF['X'] = lidarDF['X'] * lz.header.scales[0] + lz.header.offsets[0]
        lidarDF['Y'] = lidarDF['Y'] * lz.header.scales[1] + lz.header.offsets[1]
        lidarDF['Z'] = lidarDF['Z'] * lz.header.scales[2] + lz.header.offsets[2]
    return lidarDF

#

def stackTiles(lat,lon, boxSize=100, prefix ='NY_NewYorkCity/'):  # 'NY_FingerLakes_1_2020/' #
    '''
    
    Parameters:
        lat : latitude centerpoint in WGS 1984 (EPSG 4326)
        lon : longitude centerpoint in WGS 1984 (EPSG 4326)
        boxSize : crop dimensions in X & Y units of source data, typically meters
        prefix : S3 server directory name for public usgs lidar, for available servers: https://usgs.entwine.io/
        
    Returns:
        lidar_df : Pandas dataframe containing selection of point cloud retrieved from S3 bucket
        
    
    '''
    
    s3 = boto3.resource('s3', config=Config(signature_version=UNSIGNED))
    bucket = s3.Bucket('usgs-lidar-public')
    for obj in bucket.objects.filter(Prefix= prefix + 'ept.json'):
        key = obj.key
        body = obj.get()['Body']
        eptJson = json.load(body)
        epsgNumber = eptJson['srs']['horizontal']
        span = eptJson['span']
        [xmin,ymin,zmin,xmax,ymax,zmax] = eptJson['bounds']
      
    x,y = convertLatLon(lat,lon,epsgNumber)   
    locatorx = ( x - xmin ) / ( xmax - xmin ) 
    locatory = ( y - ymin ) / ( ymax - ymin )
    
    try:
        os.mkdir('laz_{}/'.format(prefix))
    except:
        pass
    
    # download highest level laz for entire extent
    if os.path.exists('laz_{}/0-0-0-0.laz'.format(prefix)) == False:
        lazfile = bucket.download_file(prefix + 'ept-data/0-0-0-0.laz','laz_{}/0-0-0-0.laz'.format(prefix))
    else: 
        pass
    
    lidar_df = getLazFile('laz_{}/0-0-0-0.laz'.format(prefix))
            
    for depth in range(1,10):
        binx = int( (locatorx * 2 ** ( depth ) ) // 1 ) 
        biny = int( (locatory * 2 ** ( depth ) ) // 1 ) 
        lazfile = prefix + 'ept-data/{}-{}-{}-'.format(depth,binx,biny)
        for obj in bucket.objects.filter(Prefix = lazfile ):
            key = obj.key
            lazfilename = key.split('/')[2]
            # download subsequent laz files and concat 
            if os.path.exists('laz_{}/{}'.format(prefix,lazfilename)) == False:
                lazfile = bucket.download_file(prefix + 'ept-data/'+lazfilename,'laz_{}/{}'.format(prefix,lazfilename))
            else: 
                pass
            lidar_df2 = getLazFile('laz_{}/{}'.format(prefix,lazfilename))
            if depth > 7:
                low = lidar_df2['Z'].mean() - lidar_df2['Z'].std()*4
                high = lidar_df2['Z'].mean() + lidar_df2['Z'].std()*8
            else:
                low = 0
                high = 1000
            lidar_df = pd.concat([lidar_df,lidar_df2])
                    
    lidar_df = lidar_df[lidar_df['Z'] > low ]
    lidar_df = lidar_df[lidar_df['Z'] < high ]
    lidar_df = lidar_df[lidar_df['X'] <= x + boxSize/2 ]
    lidar_df = lidar_df[lidar_df['X'] >= x - boxSize/2 ]
    lidar_df = lidar_df[lidar_df['Y'] <= y + boxSize/2 ]
    lidar_df = lidar_df[lidar_df['Y'] >= y - boxSize/2 ]
    return lidar_df

#



################################################################################################################################################







################################################################################################################################################





