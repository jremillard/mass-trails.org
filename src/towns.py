import sys
import overpy
import os
import sqlite3
import glob
import re
import string
import shapely.geometry
import shapely.wkt
import shapely.ops
import geojson
import functools
import pyproj
import osmium
import rtree 

projectionToMeters = functools.partial(pyproj.transform, pyproj.Proj(init='epsg:4326'),pyproj.Proj(init='epsg:3410'))
wktfab = osmium.geom.WKTFactory()

def updateTownBoundary():
    conn = sqlite3.connect('mass-trails.sqlite')

    for geojsonFile in glob.glob('geo/towns/*.geojson'):
        townName = os.path.split(geojsonFile)[1]
        townName = townName[0:-8]

        with open(geojsonFile,'r') as f :
            boundaryJson = geojson.load(f)

            boundaryShape = shapely.geometry.shape(boundaryJson['features'][0]['geometry'])

            c = conn.cursor()
            c.execute('update towns set geom=? where name = ?',(boundaryShape.wkt,townName))

    conn.commit()
    conn.close()


class TownAddressHandler(osmium.SimpleHandler):
    def __init__(self, c):
        osmium.SimpleHandler.__init__(self)
        self.c = c
        self.propertyCount = 0
        self.properties = []
        self.propertyTags = []
        self.zips = {}
        

        townList = self.c.execute('SELECT name,geom FROM towns ORDER BY name')
        self.townList= []
        self.townIndex = rtree.index.Index() 

        for row in townList:
            (townName,townGeom) = row
            shape = shapely.wkt.loads(townGeom)                
            shape = shapely.ops.transform(projectionToMeters, shape)        
            self.townIndex.insert(len(self.townList), shape.bounds)
            self.townList.append( { 'townName':townName, 'shape':shape } )
            self.zips[townName] = {}

    def way(self, o):
        osmId = o.id

        if 'addr:postcode' in o.tags :
            try:
                wkt = wktfab.create_linestring(o)
                shape = shapely.wkt.loads(wkt)        

                if ( shape.is_valid == False):
                    print("Way {} Has bad toplogy".format(osmId))
                    shape = shapely.geometry.Point([])
                    
            except Exception as ex:
                print("Way {} Has bad toplogy {}".format(osmId,ex))
                shape = shapely.geometry.Point([])

            self.addZip(shape, o)

    def node(self,o):

        osmId = o.id

        if 'addr:postcode' in o.tags :
            try:
                wkt = wktfab.create_point(o)
                shape = shapely.wkt.loads(wkt)        

                if ( shape.is_valid == False):
                    print("Point {} Has bad toplogy".format(osmId))
                    shape = shapely.geometry.Point([])
                    
            except Exception as ex:
                print("Point {} Has bad toplogy {}".format(osmId,ex))
                shape = shapely.geometry.Point([])

            self.addZip(shape, o)

    def addZip( self, shape, o):
            
        shapeProj = shapely.ops.transform(projectionToMeters, shape)        
        
        if ( not shapeProj.is_empty) :
            for j in self.townIndex.intersection( shapeProj.bounds):
                townName =  self.townList[j]['townName']
                townShape = self.townList[j]['shape']

                if ( shapeProj.intersects(townShape)):
                    zipCode = o.tags['addr:postcode']
                    if ( re.match(r'^[0-9]{5}(-[0-9]{4})?$', zipCode)):
                        self.zips[townName][zipCode] = 1
        

def updateTownZips():
    # attempting to get the zip codes from OSM, in 2018, the OSM data is not complete enough compared to 
    # to massgis data, its close ... 
    conn = sqlite3.connect('mass-trails.sqlite')
 
    ph = TownAddressHandler(conn)

    ph.apply_file("massachusetts-latest.osm.pbf", locations=True, idx='sparse_mem_array')

    # just print them out for now.
    for townName in sorted(ph.zips):
        print(townName,end=' ')
        for zipCode in ph.zips[townName]:
            print(zipCode,end=', ')
        print()

    #conn.commit()
    #conn.close()

    return ph

updateTownZips()