import os
import time
import datetime


# MA extract is read at 19:00 every day.
#dt = datetime.datetime.now()  
#while dt.hour < 19:
#    dt = datetime.datetime.now()  
#    time.sleep(60)

os.system('python getosm.py')
os.system("python properties.py")
os.system("python makepages.py")
os.system("python trails.py")
os.system("python sitemap.py")
os.system("browserify search.js --outfile ../scripts/search.js")
os.system("pushmasstrails.py")


# MAPBOX_ACCESS_TOKEN= to upload token env

#os.system("mapbox upload mass-trails.7otdywgx --name ma-trails-osm-cqxncf trails-osm.geojson")
os.system("mapbox upload mass-trails.01ptq61x --name ma-properties-osm-0y6yww properties-osm.geojson")



