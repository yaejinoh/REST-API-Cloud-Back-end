# REST-API-Cloud-Back-end
# Name:			Yae Jin Oh
# Date:			2/19/17
# Description:	1) a REST interface backed by Google's App Engine platform with data stored on Google Cloud 
#				        Datastore that tracks two entities (zoos and animals) with 5 and 7 properties
#				        2) User accounts are supported (ie. data is tied to specific users that only they can 
#				        see or modify)
#               3) The account system uses Oauth 2.0 without need of a 3rd party library
#				        4) There exists a relationship between the two entities
#               5) Able to POST, GET, PATCH, PUT, DELETE
#				        Commands of interest:
#					          /animals?checkedIn=:boolean 	  -- GET request for animals that are checked in
# 					        /animals 						            -- GET request will return all animals
#					          /zoo/:zooid/animals 			      -- GET request will return an array of full JSON animals entries
# 					        /zoos/:zooid/animals/:animalid	-- GET request with return information of an individual animal at individual zoo
# 					        /zoos/:zooid 					          -- GET request will return information of an individual zoo
# 					        /zoos 							            -- GET request will return all zoos
# 					        /zoos/:zooid/animals/:animalid 	-- DELETE request will check a animal back in
# 					        /zoos/:zooid/animals/:animalid 	-- PUT request will check a animal out to zoo
