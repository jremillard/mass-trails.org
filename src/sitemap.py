import xml.etree.cElementTree as ET
import glob
import re

urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

for filename in glob.iglob(r'../**/*.html', recursive=True):
    
    filename = filename.replace('../','')

    if ( filename.find("src") != 0 ) :

        filename = filename.replace(" ","%20")

        if (  re.search("/[WR][0-9]+.html", filename) == None and 
              re.search("_improve.html", filename) == None and 
              re.search("improve_.html", filename) == None ):

            url = ET.SubElement(urlset, "url")
            ET.SubElement(url,"loc").text = "https://www.mass-trails.org/" + filename
            

tree = ET.ElementTree(urlset)
tree.write("../sitemap.xml",encoding="UTF-8",xml_declaration=True)

