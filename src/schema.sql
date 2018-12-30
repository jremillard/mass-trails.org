CREATE TABLE `townAdjacents` ( `name1` TEXT NOT NULL, `name2` TEXT NOT NULL , PRIMARY KEY (name1, name2));
CREATE TABLE IF NOT EXISTS "townZips" (
	`townName`	TEXT NOT NULL,
	`zipCode`	TEXT NOT NULL,
	`updateId`	INTEGER NOT NULL,
	PRIMARY KEY(`townName`,`zipCode`)
);
CREATE TABLE IF NOT EXISTS "landowners" (
	`name`	TEXT NOT NULL,
	`website`	TEXT,
	`updateId`	INTEGER NOT NULL,
	`normalizedName`	TEXT,
	PRIMARY KEY(`name`)
);
CREATE TABLE IF NOT EXISTS "propertyInsides" (
	`osmId`	TEXT NOT NULL,
	`townName`	TEXT NOT NULL,
	PRIMARY KEY(`osmId`,`townName`)
);
CREATE TABLE IF NOT EXISTS "properties" (
	`osmId`	TEXT NOT NULL,
	`name`	TEXT,
	`ownerName`	TEXT,
	`updateId`	INTEGER NOT NULL,
	`website`	TEXT,
	`normalizedOwnerName`	TEXT,
	`geom`	TEXT,
	`normalizedName`	TEXT,
	`startDate`	TEXT,
	`access`	TEXT,
	`opening_hours`	TEXT,
	`wikipedia`	TEXT,
	`boundary`	TEXT,
	`landuse`	TEXT,
	`leisure`	TEXT,
	`accessRaw`	TEXT,
	`type`	TEXT,
	`publicTrailLength`	REAL,
	PRIMARY KEY(`osmId`)
);
CREATE TABLE IF NOT EXISTS "towns" (
	`name`	TEXT NOT NULL,
	`geom`	TEXT,
	`publicTrailLength`	REAL,
	PRIMARY KEY(`name`)
);
CREATE INDEX `landowners-normalizedName` ON `landowners` (`normalizedName` );
CREATE TABLE IF NOT EXISTS "parking" (
	`osmId`	TEXT,
	`propertyOsmID`	TEXT,
	`geom`	TEXT,
	`name`	TEXT,
	PRIMARY KEY(`osmId`,`propertyOsmID`)
);
CREATE INDEX `parking-property` ON `parking` (`propertyOsmID` )





;
