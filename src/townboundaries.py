import sys
import os
import sqlite3
import glob
import re
import string
import shapely.geometry
import shapely.wkt
import shapely.ops
import geojson

conn = sqlite3.connect('mass-trails.sqlite')

for geojsonFile in glob.glob('geo/towns/*.geojson'):
    townName = os.path.split(geojsonFile)[1]
    townName = townName[0:-8]

    with open(geojsonFile,'r') as f :
        boundaryJson = geojson.load(f)

        boundaryShape = shapely.geometry.shape(boundaryJson['features'][0]['geometry'])

        if ( boundaryShape.is_valid == False) :
            print("Town {} has bad toplogy".format(townName))
            boundaryShape = boundaryShape.buffer(0)
            if ( boundaryShape.is_valid == False): 
                print("Town {} still Has bad toplogy".format(townName))

        c = conn.cursor()
        c.execute('update towns set geom=? where name = ?',(boundaryShape.wkt,townName))

conn.commit()
conn.close()

