import xml.etree.cElementTree as ET
import xml.dom.minidom
import glob
import re
import time
import os

urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

def indent(elem, level=0):
  i = "\n" + level*"  "
  if len(elem):
    if not elem.text or not elem.text.strip():
      elem.text = i + "  "
    if not elem.tail or not elem.tail.strip():
      elem.tail = i
    for elem in elem:
      indent(elem, level+1)
    if not elem.tail or not elem.tail.strip():
      elem.tail = i
  else:
    if level and (not elem.tail or not elem.tail.strip()):
      elem.tail = i


for filename in glob.iglob(r'../**/*.html', recursive=True):
    

    if ( filename.find("src") != 0 ) :

        if (  re.search("/[WR][0-9]+.html", filename) == None and 
              re.search("_improve.html", filename) == None and 
              re.search("improve_.html", filename) == None and 
              re.search("/src/",filename) == None):

            filenameUrl = filename.replace('../','')
            filenameUrl = filenameUrl.replace(" ","%20")

            url = ET.SubElement(urlset, "url")
            ET.SubElement(url,"loc").text = "https://www.mass-trails.org/" + filenameUrl

            mtime = os.path.getmtime( filename)
            timeStr = time.strftime("%Y-%m-%d",time.gmtime(mtime))
            ET.SubElement(url,"lastmod").text = timeStr            

indent(urlset)
tree = ET.ElementTree(urlset)

tree.write("../sitemap.xml",encoding="UTF-8",xml_declaration=True)

