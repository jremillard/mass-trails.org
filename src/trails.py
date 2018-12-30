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
import pprint
import copy
import rtree

justLettersNumbersRe = re.compile(r'[\W]') # \W [^a-zA-Z0-9_]., but for unicode

def normalizeName(name) :
    return justLettersNumbersRe.sub('',name).lower()

projectionToMeters = functools.partial(pyproj.transform, pyproj.Proj(init='epsg:4326'),pyproj.Proj(init='epsg:3410'))
projectionToLatLon = functools.partial(pyproj.transform, pyproj.Proj(init='epsg:3410'),pyproj.Proj(init='epsg:4326'))

wktfab = osmium.geom.WKTFactory()

class TrailsHandler(osmium.SimpleHandler):
    def __init__(self, c):
        osmium.SimpleHandler.__init__(self)
        self.c = c
        self.trailCount = 0
        self.trails = []
        self.tags = {}
        self.badTags = {}

        self.allowedTags = [
            "access","operator","highway","footway",
            "surface","colour","width","wheelchair","symbol",
            "bridge",
            "horse", "foot","bicycle",
            "name","alt_name",""
            ]
        
    def takeIt(self,o):
        takeObj = False
        if 'highway' in o.tags :
            if o.tags['highway'] == 'path' or o.tags['highway'] == 'footway' or o.tags['highway'] == 'track' or o.tags['highway'] == 'cycleway':
                takeObj = True
            
        return takeObj

    def filterAccess(self,v):
        if ( v == "no"):
            v = "private"

        if ( v == "public"):                   
            v = "yes"

        if ( v == "restricted"):
            v = "private"
        if ( v== "customers"):
            v = "permissive"
        
        if ( not v in ['yes','private','permissive']):
            v = ''

        return v

         
    def way(self, o):
        if self.takeIt( o):
            self.trailCount += 1
            osmId = o.id

            tagList = {}

            for t in o.tags:
                if ( t.k in self.allowedTags) :
                    k = t.k
                    v = str(t.v)
                    takeTag = True

                    # clean up the tags!
                    if (k == "access"):
                        v = self.filterAccess(v)
                        if ( len(v) == 0):
                            takeTag = False

                    if ( k == "foot"):
                        if ( v == "designated"):
                            v = "yes"
                        v = self.filterAccess(v)
                        if ( len(v) == 0):
                            takeTag = False
                        

                    if ( k == 'surface'):
                        if ( v in [ 'asphalt','concrete','paving_stones','bricks','wood','brick','paved','cement']):
                            v = 'paved'
                        elif (v in ['compacted','fine_gravel','gravel','pebblestone']): 
                            v = 'compacted'
                        elif (v in ['ground','sand','dirt','grass','shells','unpaved','earth']):
                            v = 'ground'
                        else:
                            takeTag = False

                    if ( k == "width"):
                        units = 1.0
                        if ( v.find("'") > 0 or v.find("ft")  > 0 or v.find("feet") > 0):
                            units = 0.3048
                        m = re.search('^([0-9\\.]+)', v)
                        if ( m):
                            v = m.group(0)
                            vI = int(round(float(v)*units+0.001)) # take 0.5 as 1
                            if (vI < 1 or vI > 4):
                                takeTag = False                            
                            v= str(vI)
                        else:
                            takeTag = False

                        #takeTag = not takeTag
                        #v = t.v + ":" + v

                    # footway, and path are the same.
                    if ( k == "highway"):
                        if ( v == "footway"):
                            v = "path"
                    
                    if ( takeTag):
                        tagList[k] = v

                        kv = k + "=" + v
                        if (kv in self.tags ):
                            self.tags[kv] += 1
                        else:
                            self.tags[kv] = 1
                    else:
                        kv = k + "=" + str(t.v)
                        if (kv in self.badTags ):
                            self.badTags[kv] += 1
                        else:
                            self.badTags[kv] = 1

                        
            if ( len(tagList) > 0) :

                # we are doing hiking trails, foot access rules.
                if ( "foot" in tagList):
                     tagList["access"] = tagList["foot"]

                try:
                    wkt = wktfab.create_linestring(o)
                    shape = shapely.wkt.loads(wkt)        

                    if ( shape.is_valid == False):
                        print("Way {} Has bad toplogy".format(osmId))
                        shape = shapely.geometry.Polygon([])
                    else:
                        self.trails.append({"geometry":shape, "tags":tagList, "osmId": osmId} )

                except Exception as ex:
                    print("Way {} Has bad toplogy {}".format(osmId,ex))
            
def updateTrails():

    conn = sqlite3.connect('mass-trails.sqlite')

    th = TrailsHandler(conn)

    th.apply_file("massachusetts-latest.osm.pbf", locations=True, idx='sparse_mem_array')

    conn.cursor().execute("update properties set publicTrailLength = 0")
    conn.cursor().execute("update towns set publicTrailLength = 0")

    propertyListDb = conn.cursor().execute(
        "select properties.access,osmid,properties.geom " 
        "from properties").fetchall()

    propertyList= []
    propIndex = rtree.index.Index() 

    for propertyRow in propertyListDb:
        access, osmId, geom = propertyRow
        shape = shapely.wkt.loads(geom)
        shapeProj = shapely.ops.transform(projectionToMeters, shape)

        if not shapeProj.is_empty :
            propIndex.insert(len(propertyList), shapeProj.bounds)
            propertyList.append( {"geometry":shapeProj, "osmId":osmId, "access":access})

    townListDb = conn.cursor().execute(
        "select name,geom " 
        "from towns").fetchall()

    townList= []
    townIndex = rtree.index.Index() 

    for townRow in townListDb:
        name, geom = townRow
        shape = shapely.wkt.loads(geom)
        shapeProj = shapely.ops.transform(projectionToMeters, shape)
        townIndex.insert(len(townList), shapeProj.bounds)
        townList.append( {"geometry":shapeProj, "name":name})

    sumTemp = 0
    # fill in access tags on "highway" using open space properties 
    currentRound = th.trails.copy()
    count = 0
    bigRound = 0
    while ( len(currentRound) > 0 ) :

        bigRound += 1
        #for i in range(0,min( 10, len(currentRound))):
        #    pprint.pprint( currentRound[i])

        nextRound = []
        for path in currentRound:
            #if ( (count % 10000) == 0):
            #    print("{0} {1}/{2} {3:.1f}%".format( bigRound, count,len(th.trails),100.0*count/len(th.trails) ))
            count += 1

            # if way has no access tag, try to figure it out. 
            pathProj = shapely.ops.transform(projectionToMeters, path["geometry"])

            for j in propIndex.intersection( pathProj.bounds):
                prop = propertyList[j]
                if ( prop["geometry"].intersects(pathProj)) :
                    overlapProj = prop["geometry"].intersection(pathProj)
                    if ( overlapProj.length > 0.01 ):
                        #originalLength = pathProj.length
                        #unionLength = overlapProj.length                            

                        # replace shape with intersection
                        overlap = shapely.ops.transform(projectionToLatLon, overlapProj)   
                        path["geometry"] = overlap
                                                        
                        leftOverProj = pathProj.difference(prop["geometry"])
                        #leftOverLength = leftOverProj.length

                        #print("Split {} {}={}+{} Delta {} m".format(path["osmId"],originalLength,unionLength,leftOverLength,originalLength-unionLength-leftOverLength))
                        
                        if ( leftOverProj.length > 0.01 ):
                            # really overlapping, process it again on the next round.
                            leftOver = shapely.ops.transform(projectionToLatLon, leftOverProj)        
                            newWay = {"geometry":leftOver, "tags":path["tags"].copy() ,"osmId":path["osmId"]}
                            nextRound.append(newWay)
                            th.trails.append(newWay)

                        # update access tag.
                        if ( not "access" in path["tags"]) :
                            if ( len(prop["access"]) > 0 and len(th.filterAccess( prop["access"])) > 0 ):
                                path["tags"]["access"] = th.filterAccess( prop["access"])
                            else:
                                path["tags"]["access"] = "permissive"

                        # 'yes','private','permissive'
                        if ( path["tags"]["access"] == "yes" or path["tags"]["access"] == "permissive"):
                            sumTemp += overlapProj.length *0.000621371
                            conn.cursor().execute("update properties set publicTrailLength = publicTrailLength+? where osmId = ?",
                                (overlapProj.length,prop["osmId"]) )
                        
                        break
                                

        currentRound = nextRound

    # for "highway" not on open space
    for path in th.trails:
        if ( not "access" in path["tags"] and "highway" in path["tags"]) :
            if ( path["tags"]["highway"] == "track"  ) :
                # tracks are private by default if they are not tagged 
                path["tags"]["access"] = "private"
            elif (  path["tags"]["highway"] == "cycleway" ) :
                # cycleway is permissive
                path["tags"]["access"] = "permissive"
            elif ( "operator" in path["tags"]  ) :
                # highways with operator tag, but no access tags are permissive
                path["tags"]["access"] = "permissive"
            elif ( 'footway' in path['tags'] and path['tags']['footway'] == 'sidewalk') :
                # sidewalks are access yes
                path["tags"]["access"] = "yes"
            else:
                # finally if a path still doesn't have an access tag, lets nail it with access private
                path["tags"]["access"] = "private"


    # sidewalks are paved, cycleways are paved unless tagged otherwise.
    for path in th.trails:
        if not "surface" in path["tags"]:
            if 'footway' in path['tags'] and path['tags']['footway'] == 'sidewalk':
                path["tags"]["surface"] = "paved"
            elif path["tags"]["highway"] == "cycleway" :
                path["tags"]["surface"] = "paved"
            

    # find out length of trails in each town.
    for path in th.trails:
        if ( path["tags"]["access"] == "yes" or path["tags"]["access"] == "permissive"):
            if not "surface" in path["tags"] or path["tags"]["surface"] != "paved" :
                pathProj = shapely.ops.transform(projectionToMeters, path["geometry"])

                if ( not pathProj.is_empty) :
                    for j in townIndex.intersection( pathProj.bounds):                
                        town = townList[j]
                        overlapProj = town["geometry"].intersection(pathProj)
                        if ( overlapProj.length > 0.01 ):
                                conn.cursor().execute("update towns set publicTrailLength = publicTrailLength+? where name = ?",
                                    (overlapProj.length,town["name"]) )


    print("Number of ways: %d" % th.trailCount)
    for kv in th.tags:

        if ( False and kv.find("width=") == 0):
            print("{} ,{}".format(kv,th.tags[kv]))
        if ( False and kv.find("access=") == 0):
            print("{} ,{}".format(kv,th.tags[kv]))
        if ( False and kv.find("surface=") == 0):
            print("{} ,{}".format(kv,th.tags[kv]))

    if ( False) :
        print("Bad kv's")
        for kv in sorted(th.badTags):
                print("{} ,{}".format(kv,th.badTags[kv]))

    with open("trails-osm.geojson","wt") as outputFile:

        features =[]

        for path in th.trails:
            features.append( geojson.Feature(geometry=path["geometry"], properties=path["tags"]))

        featureC = geojson.FeatureCollection(features)
        maTrails = geojson.dumps(featureC)

        outputFile.write(maTrails)

    conn.commit()
    conn.close()


updateTrails()

