../scripts/search.js: search.js ../sitemap.xml
	browserify search.js --outfile ../scripts/search.js

../sitemap.xml: trails-osm.geojson properties-osm.geojson sitemap.py ../towns/*.html 
	python3 sitemap.py

trails-osm.geojson: massachusetts-latest.osm.pbf properties-osm.geojson trails.py
	python3 trails.py

properties-osm.geojson: massachusetts-latest.osm.pbf properties.py
	python3 properties.py

schema.sql: mass-trails.sqlite
	sqlite3 mass-trails.sqlite .schema > schema.sql

../towns/index.html: trails-osm.geojson properties-osm.geojson makepages.py templates/*.html schema.sql
	python3 makepages.py


