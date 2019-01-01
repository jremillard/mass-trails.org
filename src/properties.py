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
import functools
import pyproj
import osmium
import rtree 

justLettersNumbersRe = re.compile(r'[\W]') # \W [^a-zA-Z0-9_]., but for unicode

def normalizeName(name) :
    return justLettersNumbersRe.sub('',name).lower()

projectionToMeters = functools.partial(pyproj.transform, pyproj.Proj(init='epsg:4326'),pyproj.Proj(init='epsg:3410'))

wktfab = osmium.geom.WKTFactory()

class RoadIndexHandler(osmium.SimpleHandler):
    def __init__(self):
        osmium.SimpleHandler.__init__(self)
        self.highwayList= []
        self.highwayIndex = rtree.index.Index() 

    def way(self, o):
        if ( 'highway' in o.tags):
            val = o.tags['highway']
            osmId = o.id
            
            if ( val == 'residential' or val == 'service' or val == 'tertiary' or val == 'secondary'):
                try:
                    wkt = wktfab.create_linestring(o)
                    shape = shapely.wkt.loads(wkt)        

                    if ( shape.is_valid == False):
                        print("Highway {} Has bad toplogy".format(osmId))
                        shape = shapely.geometry.Point([])
                        
                except Exception as ex:
                    print("Highway {} Has bad toplogy {}".format(osmId,ex))
                    shape = shapely.geometry.Point([])
                
                shape = shapely.ops.transform(projectionToMeters, shape)        
                if not shape.is_empty :
                    self.highwayIndex.insert(len(self.highwayList), shape.bounds)
                    name = o.tags.get("name", "")                    
                    self.highwayList.append( {'osmId':osmId,'shape':shape,'highway':val, 'name' : name} )


class ParkingHandler(osmium.SimpleHandler):
    def __init__(self, c, highwayIndex):
        osmium.SimpleHandler.__init__(self)
        self.c = c
        self.parkingCount = 0

        propList = self.c.execute('SELECT osmid,geom FROM properties')
        self.propList= []

        self.parking = []
        self.parkingTags = []
        self.highwayIndex = highwayIndex

        self.propIndex = rtree.index.Index() 

        for row in propList:
            (osmId,propGeom) = row
            shape = shapely.wkt.loads(propGeom)                
            shape = shapely.ops.transform(projectionToMeters, shape)        
            if not shape.is_empty :
                self.propIndex.insert(len(self.propList), shape.bounds)
                self.propList.append( {'osmId':osmId,'shape':shape} )
        
    def isParking(self,o):
        takeObj = False
        if 'amenity' in o.tags and o.tags['amenity'] == 'parking':
            takeObj = True
        return takeObj

    def node(self,o):
        if self.isParking(o):
            osmId = "N" + str( int(o.id))

            try:
                wkt = wktfab.create_point(o)
                shape = shapely.wkt.loads(wkt)        

                if ( shape.is_valid == False):
                    print("Parking Point {} Has bad toplogy".format(osmId))
                    shape = shapely.geometry.Polygon([])
                    
            except Exception as ex:
                print("Parking Point {} Has bad toplogy {}".format(osmId,ex))
                shape = shapely.geometry.Polygon([])
            
            self.areaParking(o,shape, osmId)
                    
    def area(self,o):
        if self.isParking(o):

            osmId = o.id
            if ( osmId % 2 ):
                osmId = 'R' + str( int((osmId-1)/2))
            else:
                osmId = 'W' + str( int(osmId/2))
            
            try:
                wkt = wktfab.create_multipolygon(o)
                shape = shapely.wkt.loads(wkt)        

                if ( shape.is_valid == False):
                    print("Parking Area {} Has bad toplogy".format(osmId))
                    shape = shapely.geometry.Polygon([])
                    
            except Exception as ex:
                print("Parking Area {} Has bad toplogy {}".format(osmId,ex))
                shape = shapely.geometry.Polygon([])
                        
            self.areaParking(o,shape, osmId)

    def areaParking(self,o,shape, osmId):

        access = o.tags.get("access","yes")
        name = o.tags.get("name","")

        shapeProj = shapely.ops.transform(projectionToMeters, shape)        
        used = False        
        if ( not shapeProj.is_empty) :
            for j in self.propIndex.intersection( shapeProj.bounds):
                prop = self.propList[j]
                dist = shapeProj.distance(prop['shape'])

                if ( dist < 1 or ( dist < 50 and (access == "yes" or  access == "public" or access == "permissive"))):                                                    

                    if ( not shape.is_empty):
                        scalerank = 5
                        self.parking.append( shape)
                        self.parkingTags.append( {'type':'parking', 'name': name, 'scalerank' : int( scalerank ) })

                    if ( len(name ) == 0):
                        name = self.generateName(shapeProj)
                    
                    used = True
                    wkt = shapely.wkt.dumps(shape)
                    self.c.execute('insert into parking (osmId,propertyOsmID,name,geom) VALUES (?,?,?,?);',(osmId,prop['osmId'],name,wkt ))

        if ( used ):
            self.parkingCount += 1

    def generateName( self, shapeProj):

        nearby = list(self.highwayIndex.highwayIndex.nearest(shapeProj.bounds, 100))

        def sortHighways(j):
            highway = self.highwayIndex.highwayList[j]
            dist = shapeProj.distance( highway['shape'])
            return dist

        nearby= sorted( nearby, key=sortHighways)

        for j in nearby:
            highway = self.highwayIndex.highwayList[j]
            if ( len(highway['name']) > 0 ):
                return "Off " + highway['name']

        return ''


class PropertiesHandler(osmium.SimpleHandler):
    def __init__(self, c):
        osmium.SimpleHandler.__init__(self)
        self.c = c
        self.propertyCount = 0
        self.properties = []
        self.propertyTags = []
        

        townList = self.c.execute('SELECT name,geom FROM towns ORDER BY name')
        self.townList= []
        self.townIndex = rtree.index.Index() 

        for row in townList:
            (townName,townGeom) = row
            shape = shapely.wkt.loads(townGeom)                
            shape = shapely.ops.transform(projectionToMeters, shape)        
            self.townIndex.insert(len(self.townList), shape.bounds)
            self.townList.append( { 'townName':townName, 'shape':shape } )
                
    def isProperty(self,o):
        takeObj = False
        if 'landuse' in o.tags :
            v = o.tags['landuse']
            if v == 'conservation' or v == 'recreation_ground':
                takeObj = True
        if 'leisure' in o.tags :
            v = o.tags['leisure']
            if v == 'recreation_ground' or v == 'nature_reserve' or v == 'park':
                takeObj = True
        if 'boundary' in o.tags:
            v = o.tags['boundary']
            if v == 'national_park' or v == 'protected_area':
                takeObj = True
        return takeObj

    def area(self,o):
        if self.isProperty(o):
            self.areaProcessProperty(o)

    def areaProcessProperty(self,o):
        self.propertyCount += 1
        osmId = o.id
        if ( osmId % 2 ):
            osmId = 'R' + str( int((osmId-1)/2))
        else:
            osmId = 'W' + str( int(osmId/2))

        try:
            wkt = wktfab.create_multipolygon(o)
            shape = shapely.wkt.loads(wkt)        

            if ( shape.is_valid == False):
                print("Area {} Has bad toplogy".format(osmId))
                shape = shapely.geometry.Polygon([])
                
        except Exception as ex:
            print("Area {} Has bad toplogy {}".format(osmId,ex))
            shape = shapely.geometry.Polygon([])

        boundary = o.tags.get("boundary", "")
        landuse = o.tags.get("landuse", "")
        leisure = o.tags.get("leisure", "")

        name = o.tags.get("name", "")
        alt_name = o.tags.get("alt_name", "")
        website = o.tags.get("website", "")
        wikipedia = o.tags.get("wikipedia","")
        openingHours = o.tags.get("opening_hours","")
        startDate = o.tags.get("start_date","")

        propType = ""
                    
        if 'landuse' in o.tags :
            v = o.tags['landuse']
            if v == 'conservation':
                propType = "conservation"
            if v == 'recreation_ground':
                propType = "recreation_ground"

        if 'leisure' in o.tags :
            v = o.tags['leisure']
            if v == 'nature_reserve':
                propType = "conservation"
            if v == 'recreation_ground':
                propType = "recreation_ground"
            if v == 'park':
                propType = "park"
                                    
        if 'boundary' in o.tags:
            v = o.tags['boundary']
            if v == 'national_park' or v == 'protected_area':
                propType = "conservation"

        access = o.tags.get("access","")
        # allowed access tag values. Kill everything else.
        if ( access != "no" and access != "yes" and access != "public" and access != "private" and access != "permissive"):
            access = ""
        accessRaw = o.tags.get("access","")

        owner = o.tags.get("owner", "")
        # fixup some known/simple errors in OSM owner names, that are really 
        # not worth the trouble fixing in OSM.
        if ( owner == 'X'):
            owner = ""
        owner = owner.replace(" Of "," of ")
        owner = owner.replace(" And "," and ")
        owner = owner.replace("Dcr ","DCR ")
        owner = owner.replace(" Llc "," LLC")
        
        self.updateTownSql(osmId, name,website, owner, startDate, propType, access, accessRaw,wikipedia, openingHours, boundary, landuse, leisure, shape)

        shapeProj = shapely.ops.transform(projectionToMeters, shape)        

        largestTownName = ""
        largestTownArea = 0
        if ( not shapeProj.is_empty and shapeProj.area > 0) :
            for j in self.townIndex.intersection( shapeProj.bounds):
                townName =  self.townList[j]['townName']
                townShape = self.townList[j]['shape']

                areaInTown = shapeProj.intersection(townShape)
                if ( areaInTown.area > largestTownArea) :
                    largestTownArea = areaInTown.area
                    largestTownName = townName

                if ( areaInTown.area > 2000 or areaInTown.area/shapeProj.area > 0.20 ):
                    self.c.execute('insert into propertyInsides (osmId,townName) VALUES (?,?);',(osmId,townName))

        if ( not shape.is_empty ):
            self.properties.append( shape)

            scalerank = 5
            areaSqKm = shapeProj.area / (1000*1000)
            if ( areaSqKm > 3):
                scalerank = 1
            elif ( areaSqKm > 1.5):
                scalerank = 2
            elif ( areaSqKm > 0.75):
                scalerank = 3
            elif ( areaSqKm > 0.1):
                scalerank = 4
                                
            self.propertyTags.append( 
            {
                'type':propType, 
                'town':largestTownName,
                'url': '/towns/' + largestTownName + '/' + normalizeName(name) + ".html",
                'website':website,
                'owner':owner, 
                'ownerUrl':'/landowners/' + normalizeName(owner) + ".html",
                'name': name, 
                'areaSqKm':areaSqKm,
                'scalerank' : int( scalerank ) 
            })


    def updateTownSql( self, wayid, name,website, owner, startDate, propType, access, accessRaw,wikipedia, openingHours,  boundary, landuse, leisure, shape):
        normalizedOwnerName = normalizeName(owner)
        normalizedName = normalizeName(name)

        existingProperty = self.c.execute('SELECT * FROM properties where osmId == ?',(wayid,))
        if ( existingProperty.fetchone() ) :
            self.c.execute(
                "update properties set name=?,normalizedName=?,ownerName=?,normalizedOwnerName=?, " + 
                "website=?,startDate=?,type=?,access=?,accessRaw=?,wikipedia=?, opening_hours=?, boundary=?, landuse=?, leisure=?, geom=? " + 
                "where osmId = ?;",
                (name,normalizedName,owner,normalizedOwnerName,website,startDate, propType, access, accessRaw,wikipedia, openingHours,  boundary, landuse, leisure, shape.wkt,wayid))
        else:
            self.c.execute(
                "insert into properties (osmId,name,normalizedName,ownerName,normalizedOwnerName, " + 
                "website,startDate, type,access, accessRaw,wikipedia, opening_hours,  boundary, landuse, leisure, updateId,publicTrailLength, geom) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);",
                (wayid,name,normalizedName,owner,normalizedOwnerName,website,startDate, propType, access,accessRaw,wikipedia, openingHours,  boundary, landuse, leisure, 0,0,shape.wkt))

        if ( len(owner) > 0 ) :

            # remove everything that is not a letter or number, lower case
            normalizedName = normalizeName(owner)

            existingOwner = self.c.execute('SELECT * FROM landowners where normalizedName == ?',(normalizedName,))
            if ( existingOwner.fetchone() == None) :
                self.c.execute('insert into landowners (name,normalizedName,updateId) VALUES (?,?,?);',(owner,normalizedName,0))


def updateProperties():
    conn = sqlite3.connect('mass-trails.sqlite')
    conn.execute("Delete from propertyInsides")
    conn.execute("Delete from properties")

    ph = PropertiesHandler(conn)

    ph.apply_file("massachusetts-latest.osm.pbf", locations=True, idx='sparse_mem_array')

    print("Number of Properties: %d" % ph.propertyCount)

    ownerPropertyCountList = conn.execute(
        "select properties.normalizedOwnerName , count(osmId) "
        "from landowners, properties "
        "where landowners.normalizedName = properties.normalizedOwnerName "
        "group by properties.normalizedOwnerName order by count(osmId)").fetchall()

    for row in ownerPropertyCountList:
        normalizedName,count = row

        if ( count == 0) :
            print("deleting {}".format(normalizedName))
            conn.execute("delete landowners where landowner.normalizedName = ?",(normalizedName,))

    count = conn.execute("select count(*) from landowners").fetchone()

    print("Number of landowners: {}".format(count[0]))

    conn.commit()
    conn.close()

    return ph

def updateParking():
    highwayIndex = RoadIndexHandler()
    highwayIndex.apply_file("massachusetts-latest.osm.pbf", locations=True, idx='sparse_mem_array')

    conn = sqlite3.connect('mass-trails.sqlite')
    conn.execute("Delete from parking")

    ph = ParkingHandler(conn, highwayIndex)
    ph.apply_file("massachusetts-latest.osm.pbf", locations=True, idx='sparse_mem_array')

    print("Number of Parking Lots: %d" % ph.parkingCount)

    conn.commit()
    conn.close()

    return ph


propertyHandler = updateProperties()
parkingHandler = updateParking()

with open("properties-osm.geojson","wt") as outputFile:
    features =[]

    for index, p in enumerate( propertyHandler.properties):

        #print(p)
        features.append( geojson.Feature(geometry=p, properties=propertyHandler.propertyTags[index]))

    for index, p in enumerate( parkingHandler.parking):
        #print(p)
        features.append( geojson.Feature(geometry=p, properties=parkingHandler.parkingTags[index]))

    featureC = geojson.FeatureCollection(features)
    maTrails = geojson.dumps(featureC)

    outputFile.write(maTrails)


#updateTownBounds()

   

