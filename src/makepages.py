import sqlite3
import os
import glob
import io
import shapely.ops
import shapely.geometry
import shapely.wkt
import pyproj
import functools
import fnmatch
import geojson
import re
import sys
import json
from mako.template import Template
from mako.runtime import Context
from mako.lookup import TemplateLookup

SQ_KM_TO_SQ_MILES = 0.386102159 
METERS_TO_MILES = 0.000621371

conn = sqlite3.connect('mass-trails.sqlite')
townC = conn.cursor()

projectionToMeters = functools.partial(pyproj.transform, pyproj.Proj(init='epsg:4326'),pyproj.Proj(init='epsg:3410'))
projectionToLatLon = functools.partial(pyproj.transform, pyproj.Proj(init='epsg:3410'),pyproj.Proj(init='epsg:4326'))

justLettersNumbersRe = re.compile(r'[\W]') # \W [^a-zA-Z0-9_]., but for unicode

templateLookup = TemplateLookup(directories=[''], output_encoding='utf-8',input_encoding='utf-8')

townIndexTemplate = Template(filename='templates/townindex.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
townRankTemplate = Template(filename='templates/townranks.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )

townTemplate = Template(filename='templates/town.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
townPropTemplate = Template(filename='templates/townProperties.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
townOwnersTemplate = Template(filename='templates/townOwners.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
townPropMapTemplate = Template(filename='templates/townPropertyMap.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
townTrailMapTemplate = Template(filename='templates/townTrailMap.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
improveTownTemplate = Template(filename='templates/improvetown.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )

# multiple osm ways can have inconsistent values. We need to pick something 
# to avoid random pages being generated.
def mergeOsmValues( val1, val2) :
    if (len(val1) > len(val2)):
        return val1
    if (len(val1) < len(val2)):
        return val2
    return min( val1, val2)

# to preserve the timestamp info, don't overwrite existing files with the same content.
def writeFileIfDifferent( newLandownerFile, filename):
    existingFile = ""
    newFile = newLandownerFile.getvalue()

    if ( os.path.exists(filename) ):
        with open(filename,encoding='utf-8',newline='\n') as fileHandle: 
            existingFile = fileHandle.read()

    if ( existingFile != newFile):
        print("file modified " + filename)

        #with open ("old.txt",encoding='utf-8',mode="w",newline='\n') as fileHandle :
        #    fileHandle.write(existingFile)
        #with open ("new.txt",encoding='utf-8',mode="w",newline='\n') as fileHandle :
        #    fileHandle.write(newFile)
        
        with open (filename,encoding='utf-8',mode="w",newline='\n') as fileHandle :
            fileHandle.write(newFile)

        #os.exit(0)
    else:
        pass
        #print("file not modified " + filename)


def propertyPageName(osmId, normalizedName) :
    if ( normalizedName and len(normalizedName) > 0):
        return normalizedName

    return osmId

def WriteTowns(townNameFilter,searchUrls):

    townList = townC.execute('SELECT name,publicTrailLength, geom FROM towns ORDER BY name')
    townListNew = []

    for row in townList:
        (townName,townPublicTrailLength,townGeom) = row

        if ( townNameFilter != "" and townNameFilter != townName):
            continue

        townShape = shapely.wkt.loads(townGeom)
        townShapeProj = shapely.ops.transform(projectionToMeters, townShape)
        townAreaSqKm = townShapeProj.area / (1000.0*1000.0)
        
        townAreaSqMiles = SQ_KM_TO_SQ_MILES * float(townAreaSqKm)

        conservationAreaSqMiles = 0

        zips = conn.cursor().execute("SELECT zipCode from townZips where townName == ?" , (townName,)).fetchall()
        zips = [x[0] for x in zips]

        # Adjacent towns
        adjacentTowns1 = conn.cursor().execute("SELECT name1 from townAdjacents where name2 == ?" , (townName,)).fetchall()
        adjacentTowns1 = [x[0] for x in adjacentTowns1]
        adjacentTowns2 = conn.cursor().execute("SELECT name2 from townAdjacents where name1 == ?" , (townName,)).fetchall()
        adjacentTowns2 = [x[0] for x in adjacentTowns2]
        adjacentTowns = list()
        if ( len(adjacentTowns1) > 0 ):
            adjacentTowns.extend(adjacentTowns1)
        if ( len(adjacentTowns2) > 0 ):
            adjacentTowns.extend(adjacentTowns2)
        adjacentTowns = sorted(adjacentTowns)


        # properties
        propertyList = conn.cursor().execute(
            "select properties.osmId,properties.name,properties.normalizedName, properties.ownerName, properties.normalizedOwnerName, type, access, accessRaw, website, properties.publicTrailLength, properties.geom " + 
            "from properties, propertyInsides " + 
            "where " + 
            "propertyInsides.osmId = properties.osmId and " + 
            "propertyInsides.townName == ? " +
            "order by properties.normalizedOwnerName, properties.name" , 
            (townName,)).fetchall()

        propertyListOrg = propertyList
        propertyList = []
        landOwnerProperties = {}
        shapeLandInTownProj = shapely.geometry.Polygon([])


        for row in propertyListOrg :
            osmId, propertyName, normalizedName, ownerName, normalizeOwnerName,propType, access, accessRaw, website, publicTrailLength, geom = row
            shape = shapely.wkt.loads(geom)
            shapeProj = shapely.ops.transform(projectionToMeters, shape)

            shapeInTownProj = townShapeProj.intersection(shapeProj)
            shapeLandInTownProj = shapeLandInTownProj.union( shapeInTownProj)

            areaInTown = shapeInTownProj.area * SQ_KM_TO_SQ_MILES / (1000.0*1000.0)
            conservationAreaSqMiles += areaInTown

            if ( normalizeOwnerName ) :
                if ( not normalizeOwnerName in landOwnerProperties ):
                    landOwnerProperties[normalizeOwnerName] = []

                landOwnerProperties[normalizeOwnerName].append( areaInTown)
            
            area = shapeProj.area * SQ_KM_TO_SQ_MILES / (1000.0*1000.0)

            pageName = propertyPageName(osmId,normalizedName)

            dup = False
            for prop in propertyList:
                if ( prop['propertyPageName'] == pageName):
                    prop['propertyArea'] += area*640.0
                    prop['propertyAreaInTown'] += areaInTown*640
                    prop['publicTrailLength'] += publicTrailLength * METERS_TO_MILES
                    prop['osmCount'] += 1
                    if  len(prop['propType']) == 0:
                        prop['propType'] = propType
                    dup = True
            
            if ( dup == False):
                propertyList.append( 
                    {
                        'propertyPageName':pageName,
                        'propertyName':propertyName,
                        'ownerName':ownerName,
                        'propType':propType,                        
                        'access':access,
                        'rawAccess':accessRaw,
                        'website':website,
                        'normalizeOwnerName':normalizeOwnerName,
                        'propertyArea':area*640.0,
                        'propertyAreaInTown':areaInTown*640,
                        'publicTrailLength':publicTrailLength * METERS_TO_MILES,
                        'osmCount':1
                    })
                
        propertyList = sorted(propertyList, key=lambda k: k['publicTrailLength'],reverse=True)

        # land owners
        landOwnerList = conn.cursor().execute(
            "select distinct properties.ownerName, landowners.normalizedName " +
            "from properties, propertyInsides, landowners " +
            "where " + 
            "propertyInsides.osmId = properties.osmId and " + 
            "properties.normalizedOwnerName <> '' and " + 
            "landowners.normalizedName == properties.normalizedOwnerName and " +
            "propertyInsides.townName == ? " +
            "order by properties.normalizedOwnerName",(townName,)).fetchall()

        landOwnerListNew = []
        for row in landOwnerList:
            ownerName, normalizeOwnerName = row

            count = len(landOwnerProperties[normalizeOwnerName])            
            row = row + (count,)

            ownerAreaInTown = 0
            for a in landOwnerProperties[row[1]]:
                ownerAreaInTown += a

            row = row + (ownerAreaInTown*640.0,)

            landOwnerListNew.append(row)

        landOwnerList = sorted(landOwnerListNew, key=lambda x: x[3],reverse=True)

        townDirName = os.path.join( "..","towns",townName)
        if ( os.path.exists(townDirName ) == False):
            os.makedirs(townDirName)

        shapeLandInTown = shapeLandInTownProj

        townBoundaryJson = geojson.Feature(geometry=townShape, properties={})

        shapeLandInTown = shapely.ops.transform(projectionToLatLon, shapeLandInTownProj)  

        landInTownJson = geojson.Feature(geometry={},properties={})

        if ( shapeLandInTown.is_empty == False):
            try:
                landInTownJson = geojson.Feature(geometry=shapeLandInTown,properties={})
            except Exception as ex:
                print("Town land {} shape can't export to geojson {}".format(name,ex))
              
        # in the town page, only show the top N properties and land owners 
        topPropertyList = propertyList
        if ( len(propertyList) > 5 ):
            topPropertyList = propertyList[0:6]

        topLandOwnerList = landOwnerList
        if ( len(landOwnerList) > 5):
            topLandOwnerList = landOwnerList[0:5]
                                
        newFile = io.StringIO()
        body = townTemplate.render(
            townName=townName,
            townAreaSqMiles=townAreaSqMiles,
            publicTrailLength=townPublicTrailLength*METERS_TO_MILES,
            conservationAreaSqMiles=conservationAreaSqMiles,
            zips=zips,
            townBoundary=geojson.dumps(townBoundaryJson),
            landInTown=geojson.dumps(landInTownJson),
            adjacent=adjacentTowns, 
            propertyList=topPropertyList,
            landOwnerList=topLandOwnerList,
            propertyListFull=propertyList,
            landOwnerListFull=landOwnerList)
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join("..","towns", townName + ".html"))
        newFile.close()

        searchUrls.append( 
            {
                'url':"/towns/{}.html".format(townName),
                'search':townName,
                'type':'T',
                'show':"{} Summary".format(townName)
            }
        )

        newFile = io.StringIO()
        body = townPropTemplate.render(
            townName=townName,
            townAreaSqMiles=townAreaSqMiles,
            publicTrailLength=townPublicTrailLength*METERS_TO_MILES,
            conservationAreaSqMiles=conservationAreaSqMiles,
            zips=zips,
            townBoundary=geojson.dumps(townBoundaryJson),
            landInTown=geojson.dumps(landInTownJson),
            adjacent=adjacentTowns, 
            propertyList=propertyList,
            landOwnerList=landOwnerList)
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join( "..","towns",townName,"Properties_.html"))
        newFile.close()

        searchUrls.append( 
            {
                'url':"/towns/{}/Properties_.html".format(townName),
                'search':"{} properties".format(townName),
                'type':'T',
                'show':"{} Properties".format(townName)
            }
        )

        newFile = io.StringIO()
        body = townOwnersTemplate.render(
            townName=townName,
            townAreaSqMiles=townAreaSqMiles,
            publicTrailLength=townPublicTrailLength*METERS_TO_MILES,
            conservationAreaSqMiles=conservationAreaSqMiles,
            zips=zips,
            townBoundary=geojson.dumps(townBoundaryJson),
            landInTown=geojson.dumps(landInTownJson),
            adjacent=adjacentTowns, 
            propertyList=propertyList,
            landOwnerList=landOwnerList)
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join( "..","towns",townName,"Owners_.html"))
        newFile.close()

        searchUrls.append( 
            {
                'url':"/towns/{}/Owners_.html".format(townName),
                'search':"{} Landowners".format(townName),
                'type':'T',
                'show':"{} Landowners".format(townName)
            }
        )
            
        propertyList = sorted(propertyList, key=lambda k: k['propertyAreaInTown'],reverse=True)
            
        newFile = io.StringIO()
        body = improveTownTemplate.render(
            townName=townName,
            townAreaSqMiles=townAreaSqMiles,
            publicTrailLength=townPublicTrailLength*METERS_TO_MILES,
            conservationAreaSqMiles=conservationAreaSqMiles,
            zips=zips,
            townBoundary=geojson.dumps(townBoundaryJson),
            landInTown=geojson.dumps(landInTownJson),
            adjacent=adjacentTowns, 
            propertyList=propertyList,
            landOwnerList=landOwnerList)
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join( "..","towns", townName, "improve_.html"))
        newFile.close()

        WriteTownPropertyMapPage(townName,townBoundaryJson,searchUrls )

        townListNew.append( 
            { 
                "name":townName,
                "area":townAreaSqMiles,
                "conservationArea":conservationAreaSqMiles,
                "areaPercent":conservationAreaSqMiles/townAreaSqMiles*100.0,
                "publicTrailLength":townPublicTrailLength*METERS_TO_MILES
            } 
            )

    # get the ranks in
    townListNew = sorted(townListNew, key=lambda x: x["publicTrailLength"],reverse=True)
    for idx, val in enumerate(townListNew):
        val["rankPublicTrailLength"] = idx+1
    
    townListNew = sorted(townListNew, key=lambda x: x["conservationArea"],reverse=True)
    for idx, val in enumerate(townListNew):
        val["rankConservationArea"] = idx+1

    townListNew = sorted(townListNew, key=lambda x: x["areaPercent"],reverse=True)
    for idx, val in enumerate(townListNew):
        val["rankAreaPercent"] = idx+1

    townListNew = sorted(townListNew, key=lambda x: x["name"])

    newFile = io.StringIO()
    body = townIndexTemplate.render(
        townList=townListNew
        )
    newFile.write( body)
    writeFileIfDifferent( newFile, os.path.join("..","towns","index.html"))
    newFile.close()

    newFile = io.StringIO()
    body = townRankTemplate.render(
        rankBy="Open Space Area",
        townList=sorted(townListNew, key=lambda x: x["conservationArea"],reverse=True)
        )
    newFile.write( body)
    writeFileIfDifferent( newFile, os.path.join("..","towns","rank-area.html"))
    newFile.close()

    newFile = io.StringIO()
    body = townRankTemplate.render(
        rankBy="Open Space Area Percentile",
        townList=sorted(townListNew, key=lambda x: x["areaPercent"],reverse=True)
        )
    newFile.write( body)
    writeFileIfDifferent( newFile, os.path.join("..","towns","rank-area-percent.html"))
    newFile.close()

    newFile = io.StringIO()
    body = townRankTemplate.render(
        rankBy="Trails",
        townList=sorted(townListNew, key=lambda x: x["publicTrailLength"],reverse=True)
        )
    newFile.write( body)
    writeFileIfDifferent( newFile, os.path.join("..","towns","rank-trails.html"))
    newFile.close()


def WriteLandOwners(searchUrls):

    landOwnerIndexTemplate = Template(filename='templates/landownerindex.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
    landOwnerTemplate = Template(filename='templates/landowner.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )

    townShapes = {}
    for row in townC.execute('SELECT name,geom FROM towns ORDER BY name'):
        (townName,townGeom) = row
        townShape = shapely.wkt.loads(townGeom)
        townShapeProj = shapely.ops.transform(projectionToMeters, townShape)
        townShapes[townName] = townShapeProj

    landOwnerList = townC.execute('SELECT normalizedName,website,name FROM landowners ORDER BY name')
    landOwnerListNew = []

    for row in landOwnerList:
        normalizedName,website,name = row

        if ( website is None or website == "None"):
            website = ""

        propertyList = conn.cursor().execute(
            "select properties.osmId,properties.name,properties.normalizedName, propertyInsides.townName,properties.publicTrailLength, properties.geom " + 
            "from properties,propertyInsides " + 
            "where " + 
            "propertyInsides.osmId = properties.osmId and " + 
            "properties.normalizedOwnerName = ? " + 
            "order by propertyInsides.townName,properties.name" , 
            (normalizedName,)).fetchall()

        propertyListOrg = propertyList
        propertyList = []

        allShape = shapely.geometry.Polygon([])

        for row in propertyListOrg :
            propertyOsmId, propertyName, propertyNormalizedName,townName, publicTrailLength, geom = row
            shape = shapely.wkt.loads(geom)
            
            allShape = allShape.union(shape)
            
            shapeProj = shapely.ops.transform(projectionToMeters, shape)

            areaInTown = townShapes[townName].intersection(shapeProj).area

            area = areaInTown * SQ_KM_TO_SQ_MILES / (1000.0*1000.0)

            if ( publicTrailLength is None):
                publicTrailLength = 0

            pageName = propertyPageName( propertyOsmId,propertyNormalizedName)

            dup = False
            for prop in propertyList:
                if ( prop['propertyPageName'] == pageName and prop['propertyTownName'] == townName):
                    prop['propertyArea'] += area*640.0
                    prop['publicTrailLength'] += publicTrailLength*METERS_TO_MILES
                    dup = True

            if ( dup == False) :
                propertyList.append( 
                    {
                        'propertyPageName':pageName,
                        'propertyName':propertyName,
                        'propertyTownName':townName,
                        'publicTrailLength':publicTrailLength*METERS_TO_MILES,
                        'propertyArea':area*640.0
                    })

        propertyList = sorted(propertyList, key=lambda x: x['publicTrailLength'],reverse=True)

        ownerPublicTrailLength = 0
        conservationAreaSqMiles = 0

        propertyListTrailSize = conn.cursor().execute(
            "select publicTrailLength, geom " + 
            "from properties " + 
            "where " + 
            "normalizedOwnerName = ?",
            (normalizedName,)).fetchall()

        for row in propertyListTrailSize :
            publicTrailLength, geom = row   

            shape = shapely.wkt.loads(geom)                 
            shapeProj = shapely.ops.transform(projectionToMeters, shape)
            conservationAreaSqMiles += shapeProj.area * SQ_KM_TO_SQ_MILES / (1000.0*1000.0)

            ownerPublicTrailLength += publicTrailLength*METERS_TO_MILES
        
        allShapeJson = geojson.Feature(geometry={}, properties={})        
        if ( allShape.is_empty == False):
            try:
                allShapeJson = geojson.Feature(geometry=allShape, properties={})
            except Exception as ex:
                print("Landowner {} shape can't merge to geojson {}".format(name,ex))

        newFile = io.StringIO()
        body = landOwnerTemplate.render(
            name=name,
            normalizedName=normalizedName,
            conservationAreaSqMiles=conservationAreaSqMiles,
            propertyList=propertyList,
            publicTrailLength=ownerPublicTrailLength,
            website=website,
            allShape=geojson.dumps(allShapeJson),
            )
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join("..","landowners", normalizedName+".html"))
        newFile.close()
            
        landOwnerListNew.append( 
            { 
                'normalizedName':normalizedName,
                'name':name,
                'conservationAreaSqMiles':conservationAreaSqMiles,
                'publicTrailLength':ownerPublicTrailLength
            })

        searchUrls.append( 
            {
                'url':"/landowners/{}.html".format(normalizedName),
                'search':name,
                'type':'L',
                'publicTrailLength':ownerPublicTrailLength,
                'conservationAreaSqMiles':conservationAreaSqMiles,
                'propertyCount':len(propertyList)
            }
        )

    landOwnerListNew = sorted(landOwnerListNew, key=lambda x: x['conservationAreaSqMiles'],reverse=True)

    newFile = io.StringIO()
    body = landOwnerIndexTemplate.render(landOwnerList=landOwnerListNew)
    newFile.write( body)
    writeFileIfDifferent( newFile, "../landowners/index.html")
    newFile.close()

def WriteTownPropertyMapPage(townName,townBoundaryJson,searchUrls ):

    selectStr = "select properties.osmId,properties.name,properties.normalizedName, properties.ownerName, properties.normalizedOwnerName, properties.website, properties.geom " 

    propertyList = conn.cursor().execute(
        selectStr + 
        "from properties,propertyInsides " + 
        "where " + 
        "propertyInsides.osmId = properties.osmId and propertyInsides.townName = ?",(townName,)).fetchall()

    propertyListNew = []
    for propertyRow in propertyList:
        osmid, name, normalizedName, ownerName, normalizedOwnerName, website, geom = propertyRow

        propertyPageNameStr = propertyPageName(osmid,normalizedName)

        shape = shapely.wkt.loads(geom)
        shapeProj = shapely.ops.transform(projectionToMeters, shape)

        if ( normalizedName and len(normalizedName) > 0 ) :

            propertyListSameName = conn.cursor().execute(
                selectStr +          
                "from properties,propertyInsides " + 
                "where " + 
                "properties.normalizedName = ? and " +
                "propertyInsides.townName = ? and " +
                "propertyInsides.osmId = properties.osmId", (normalizedName,townName) ).fetchall()
                
            # spread the owner and website tabs around if there are multiple entities.
            for propSameName in propertyListSameName:
                osmidI, nameI, normalizedNameI, ownerNameI, normalizedOwnerNameI, websiteI, geomI = propSameName

                if ( ownerName is None):
                    ownerName = ownerNameI
                    normalizedOwnerName = normalizedOwnerNameI
                if ( website is None):
                    website = websiteI
                                    
        # back to lat long
        shape = shapely.ops.transform(projectionToLatLon, shapeProj)

        shapeJson = geojson.Feature(
            geometry=shape, 
            properties={"propertyPageName":propertyPageNameStr,"name":name,"ownerName":ownerName,"normalizedOwnerName":normalizedOwnerName,"website":website}
        )

        propertyListNew.append ( geojson.dumps(shapeJson))

    newFile = io.StringIO()
    body = townPropMapTemplate.render(
        propertyList=propertyListNew,
        townName=townName,
        townBoundary=geojson.dumps(townBoundaryJson)
    )
    newFile.write( body)
    writeFileIfDifferent( newFile, os.path.join( "..","towns",townName,"OpenSpacePropertyMap_.html"))
    newFile.close()

    searchUrls.append( 
        {
            'url':"/towns/{}/OpenSpacePropertyMap_.html".format(townName),
            'search':"{} property map".format(townName),
            'type':'T',
            'show':"{} Property Map".format(townName)
        }
    )

    newFile = io.StringIO()
    body = townTrailMapTemplate.render(
        propertyList=propertyListNew,
        townName=townName,
        townBoundary=geojson.dumps(townBoundaryJson)
    )
    newFile.write( body)
    writeFileIfDifferent( newFile, os.path.join("..","towns",townName,"TrailMap_.html"))
    newFile.close()

    searchUrls.append( 
        {
            'url':"/towns/{}/TrailMap_.html".format(townName),
            'search':"{} trail map".format(townName),
            'type':'T',
            'show':"{} Trail Map".format(townName)
        }
    )


def WriteProperties(townNameFilter,searchUrls):

    propertiesTemplate = Template(filename='templates/property.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )
    improvePropertiesTemplate = Template(filename='templates/improveproperty.html',strict_undefined=True,input_encoding='utf-8',lookup=templateLookup )

    selectStr = "select properties.osmId,properties.name,properties.normalizedName, propertyInsides.townName, publicTrailLength, properties.website, properties.ownerName, properties.normalizedOwnerName, properties.startDate, properties.type, properties.access, properties.accessRaw, properties.opening_hours, properties.wikipedia, properties.geom " 

    propertyList = conn.cursor().execute(
        selectStr + 
        "from properties,propertyInsides " + 
        "where " + 
        "propertyInsides.osmId = properties.osmId").fetchall()

    propertyListNew = []
    for propertyRow in propertyList:
        osmid, name, normalizedName, townName, publicTrailLength, websiteUrl, ownerName, normalizedOwnerName, startDate, propType, access, accessRaw, openingHours, wikipedia, geom = propertyRow
        propertyPageNameStr = propertyPageName(osmid,normalizedName)

        if ( townNameFilter != "" and townName != townNameFilter):
            continue
        
        shape = shapely.wkt.loads(geom)
        shapeProj = shapely.ops.transform(projectionToMeters, shape)

        osmIds = []

        if ( normalizedName and len(normalizedName) > 0 ) :
            publicTrailLength = 0 # outer property coming back again.
            propertyListSameName = conn.cursor().execute(
                selectStr +          
                "from properties,propertyInsides " + 
                "where " + 
                "properties.normalizedName = ? and " +
                "propertyInsides.townName = ? and " +
                "propertyInsides.osmId = properties.osmId " +
                "order by properties.osmId", (normalizedName,townName) ).fetchall()

            shape = shapely.geometry.Polygon([])
            shapeProj = shapely.geometry.Polygon([])
                
            for propSameName in propertyListSameName:
                osmidI, nameI, normalizedNameI, townNameI, publicTrailLengthI, websiteUrlI, ownerNameI, normalizedOwnerNameI, startDateI, propTypeI, accessI, accessRawI, openingHoursI, wikipediaI, geomI = propSameName

                shapeI = shapely.wkt.loads(geomI)
                shapeProjI = shapely.ops.transform(projectionToMeters, shapeI)

                shapeProj = shapeProj.union(shapeProjI)

                # different OSM objects can have different attributes. We need to be 
                # consistent with what is picked so the output files don't randomly change.
                startDateList = startDate.split(';')
                startDateList.extend( startDateI.split(';'))
                # empty dates must go.
                startDateList = [x for x in startDateList if x]

                # we only care about years.
                for n, i in enumerate(startDateList):
                    dt = i.split('-')
                    if ( len(dt) > 1 and len(dt[0]) == 4):
                        startDateList[n] = dt[0]

                startDateList = sorted(set(startDateList))
                startDate = ';'.join(startDateList)
                                                    
                newOwnerName = mergeOsmValues( ownerName, ownerNameI)
                if ( newOwnerName != ownerName):
                    ownerName = ownerNameI
                    normalizedOwnerName = normalizedOwnerNameI

                newRawAccess = mergeOsmValues( accessRaw, accessRawI)
                if ( newRawAccess != accessRaw ):
                    access = accessI
                    accessRaw = accessRawI; 
                
                openingHours = mergeOsmValues(openingHours, openingHoursI)
                wikipedia = mergeOsmValues(wikipediaI,wikipedia)
                propType = mergeOsmValues( propType, propTypeI)
                websiteUrl = mergeOsmValues( websiteUrlI, websiteUrl)
                name = mergeOsmValues( nameI , name)

                publicTrailLength += publicTrailLengthI
                                    
                osmIds.append( osmidI)
        else:
            osmIds = [osmid]


        # parking
        parking = []
        for id in osmIds:
            parkingRows = conn.cursor().execute(
                "select osmId,name,geom "
                "from parking " + 
                "where " + 
                "propertyOsmId = ?", (id,) ).fetchall()
            for parkingRow in parkingRows:
                (parkingOsmId, parkingName, parkingGeom) = parkingRow

                parkingFound = False

                for p in parking:
                    if ( p['osmId'] == parkingOsmId):
                        parkingFound = True

                if ( parkingFound == False):
                    parkingCenter = shapely.wkt.loads(parkingGeom).centroid
                    if parkingName is None:
                        parkingName = "Parking {}".format(len(parking)+1)

                    parking.append( { 'center':parkingCenter,'osmId':parkingOsmId, 'name':parkingName})

        parking = sorted(parking, key=lambda k: k['name'])

        area = shapeProj.area * SQ_KM_TO_SQ_MILES / (1000.0*1000.0) * 640

        # back to lat long
        shape = shapely.ops.transform(projectionToLatLon, shapeProj)

        shapeJson = geojson.Feature(geometry=shape, properties={})
        
        newFile = io.StringIO()
        body = propertiesTemplate.render(
            normalizedName=propertyPageNameStr,
            townName=townName,
            publicTrailLength=publicTrailLength*METERS_TO_MILES,
            website=websiteUrl,
            ownerName=ownerName,
            normalizedOwnerName=normalizedOwnerName,
            osmIds=osmIds,
            propertyArea=area,
            propertyAreaInTown=0.0,
            startDate=startDate,
            propType=propType,
            access=access,
            parking=parking,
            rawAccess=accessRaw,
            openingHours=openingHours,
            wikipedia=wikipedia,
            shape=geojson.dumps(shapeJson),
            name=name
            )
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join( "..","towns",townName, propertyPageNameStr + ".html"))
        newFile.close()

        if ( len(name) > 0 ) :
            # don't add dups to search list, because of multiple osm ids.
            newEntry = {
                    'url':"/towns/{}/{}.html".format(townName,propertyPageNameStr),
                    'search':name + " " + townName,
                    'type':'P',
                    'publicTrailLength':publicTrailLength*METERS_TO_MILES,
                    'propertyArea':area,
                    'ownerName':ownerName,
                    'town':townName
                }

            found = False
            for u in searchUrls:
                if ( u['url'] == newEntry['url']) :
                    found = True
                    break

            if ( found == False):
                searchUrls.append( newEntry)

        newFile = io.StringIO()
        body = improvePropertiesTemplate.render(
            normalizedName=propertyPageNameStr,
            townName=townName,
            publicTrailLength=publicTrailLength*METERS_TO_MILES,
            website=websiteUrl,
            ownerName=ownerName,
            normalizedOwnerName=normalizedOwnerName,
            osmIds=osmIds,
            propertyArea=area,
            propertyAreaInTown=0.0,
            startDate=startDate,
            propType=propType,
            access=access,
            parking=parking,                
            rawAccess=accessRaw,
            openingHours=openingHours,
            wikipedia=wikipedia,
            shape=geojson.dumps(shapeJson),
            name=name
            )
        newFile.write( body)
        writeFileIfDifferent( newFile, os.path.join("..","towns",townName,propertyPageNameStr + "_improve.html"))
        newFile.close()

        if ( len(name) > 0 ) :
            propertyListNew.append( (propertyPageNameStr,name) )            


def recursive_glob(rootdir, pattern):
    """Search recursively for files matching a specified pattern.
    Adapted from http://stackoverflow.com/questions/2186525/use-a-glob-to-find-files-recursively-in-python
    """
    
    matches = []
    for root, dirnames, filenames in os.walk(rootdir):
        for filename in fnmatch.filter(filenames, pattern):
            matches.append(os.path.join(root, filename))
        
    return matches

searchUrls = []

if ( len(sys.argv) == 1 ) :

    # clear out the existing files, landowners change.
    #generatedDirs = ['../landowners/','../towns/']
    #for generatedDir in generatedDirs:

    #for fileToDelete in recursive_glob(generatedDir,"*.html") :
    #        os.remove(fileToDelete )

    #    if ( os.path.exists(generatedDir)):
    #        os.remove(generatedDir)

    #    os.mkdir(generatedDir)
    
    WriteTowns("", searchUrls)
    WriteLandOwners(searchUrls)
    WriteProperties("",searchUrls)

else :
    for town in sys.argv[1:]:
        print(town)
        WriteTowns(town,searchUrls)
        WriteProperties(town,searchUrls)

with open('search.json', 'w') as outfile:
    json.dump(searchUrls, outfile)
