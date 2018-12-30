# update the zip tags in the yaml source files from the MassGIS zip layer
import os
import glob
import yaml
import json
import shapely
import geopandas as gpd

zipFile = gpd.read_file('geo/zip/ZIPCODES_NT_POLY.shp')

zips = {}

for ii, row in zipFile.iterrows():
    zip = row['POSTCODE']
    townName = row['CITY_TOWN']
    townName = townName.title()
    townName = townName.replace(", Town Of","")

    # different names for the same town.
    if ( townName == 'Mt Washington'):
        townName = "Mount Washington"
    if  (townName == "Manchester By The Sea"):
        townName = "Manchester-by-the-Sea"
        
    #print("{} - {}".format(zip ,townName ))

    if ( townName in zips) :
        if ( (zip in zips[townName]) == False) :
            zips[townName].append(zip)
    else:
        zips[townName] = []
        zips[townName].append(zip)
        
# make sure the towns make yaml file names. 
badTowns = False
for town in zips:

    cfg = {}
    townYaml = "towns/{}.yaml".format(town)
    if ( os.path.isfile(townYaml) == False) :
        print("No town called " + town)
        badTowns = True

if ( badTowns) :
    exit(1)

for town in zips:

    cfg = {}
    townYaml = "towns/{}.yaml".format(town)
    with open(townYaml,"rt") as f :
        cfg = yaml.load(f)
    
    cfg['zips'] = zips[town]

    print(town)
    print("  " + str(zips[town] ))

    with open(townYaml,"wt") as f :        
        f.write( yaml.dump( cfg,default_flow_style=False ))







