../sitemap.xml: sitemap.py ../towns/index.html ../scripts/search.js
	python3 sitemap.py

../towns/index.html search.json : makepages.py trails-osm.geojson properties-osm.geojson templates/*.html schema.sql  
	python3 makepages.py

../scripts/search.js: search.js search.json
	browserify search.js --outfile ../scripts/search.js

trails-osm.geojson: trails.py massachusetts-latest.osm.pbf properties-osm.geojson
	python3 trails.py

renderingdb.sqlite: makerenderingdb.py massachusetts-latest.osm.pbf
	python3 makeenderingdb.py

properties-osm.geojson: properties.py massachusetts-latest.osm.pbf 
	python3 properties.py

schema.sql: mass-trails.sqlite
	sqlite3 mass-trails.sqlite .schema > schema.sql



