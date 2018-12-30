# update the adjacent town tags in the yaml source files from the town geojson files.
import os
import glob
import yaml
import json
import shapely
import geopandas as gpd

townFileNames = glob.glob('geo/towns/*.geojson')
townNames = []
townShapes = []

for filename in townFileNames:
    townName = os.path.split(filename)[1]

    townName = townName[0:-8]

    townNames.append(townName)

    shape = gpd.read_file(filename)
    
    townShapes.append(shape)

for townOuterIndex in range(len(townFileNames)):

    townName = townNames[townOuterIndex]
    cfg = {}
    with open("towns/{}.yaml".format(townName),"rt") as f :
        cfg = yaml.load(f)
 
    adjacentList = []
    for townInnerIndex in range(len(townFileNames)):

        if ( townInnerIndex != townOuterIndex) :
            for ii, crim in townShapes[townOuterIndex].iterrows():
                for ii2, popu in townShapes[townInnerIndex].iterrows():
            
                    if ( crim['geometry'].intersects(popu['geometry'])):
                        adjacentList.append(townNames[townInnerIndex])
                        #print( townNames[townInnerIndex] )
                        break
      
    print( townName)
    print( "  " + str(adjacentList))

    cfg['adjacent'] = adjacentList

    with open("towns/{}.yaml".format(townName),"wt") as f :        
        f.write( yaml.dump( cfg,default_flow_style=False ))



