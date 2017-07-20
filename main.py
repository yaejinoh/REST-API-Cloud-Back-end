# REST API - Cloud Only Implementation
# Name:			Yae Jin Oh
# Due Date:		2/19/17
# Description:	1) a REST interface backed by Google's App Engine platform with data stored on Google Cloud 
#				Datastore that tracks two entities (zoos and animals) with 5 and 7 properties
#				2) User accounts are supported (ie. data is tied to specific users that only they can 
#				see or modify)
#               3) The account system uses Oauth 2.0 without need of a 3rd party library
#				4) There exists a relationship between the two entities
#               5) Able to POST, GET, PATCH, PUT, DELETE
#				Commands of interest:
#					/animals?checkedIn=:boolean 	-- GET request for animals that are checked in
# 					/animals 						-- GET request will return all animals
#					/zoo/:zooid/animals 			-- GET request will return an array of full JSON animals entries
# 					/zoos/:zooid/animals/:animalid	-- GET request with return information of an individual animal at individual zoo
# 					/zoos/:zooid 					-- GET request will return information of an individual zoo
# 					/zoos 							-- GET request will return all zoos
# 					/zoos/:zooid/animals/:animalid 	-- DELETE request will check a animal back in
# 					/zoos/:zooid/animals/:animalid 	-- PUT request will check a animal out to zoo

# Imported Libraries
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
from oauth2client.client import flow_from_clientsecrets
from rauth.service import OAuth2Service
import webapp2
import json
import urllib
import urllib2
import string
import random


# Class to hold the secret state variable randomly generated for the user
class OauthVar(ndb.Model):
	state_var = ndb.StringProperty()
	
# Class to hold the authentication token
class AuthToken(ndb.Model):
	auth_token = ndb.StringProperty()

	
# Animal class
class Animal(ndb.Model):
	user_id = ndb.StringProperty(required=True)
	species = ndb.StringProperty(required=True)
	population = ndb.IntegerProperty()
	consumption_class =  ndb.StringProperty() # Herbivore, Carnivore, Omnivore, Insectivore
	checked_in = ndb.BooleanProperty()
	
	
# Zoo class
class Zoo(ndb.Model):
	user_id = ndb.StringProperty(required=True)
	name = ndb.StringProperty(required=True)
	city = ndb.StringProperty()
	state = ndb.StringProperty()
	size = ndb.StringProperty()
	admission = ndb.FloatProperty()
	species_list = ndb.StringProperty(repeated=True) 
	
	
class LogInHandler(webapp2.RequestHandler):
	def get(self):
		# Delete any stray state variables that may be stored
		all_states = OauthVar.query().fetch(keys_only=True)
		ndb.delete_multi(all_states)

		# Randomly generate a string of 15 characters for the state variable
		state_var = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(15))
		auth_info = OauthVar(state_var=state_var)
		auth_info.put()
		
		# Send a GET request to the url with credential info
		url = 'https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=518379713624-146hkku1jvqvti9o3vb3m733lav400bu.apps.googleusercontent.com&redirect_uri=https://final-project-161802.appspot.com/oauth&scope=email&state=' + state_var
		try:
			result = urlfetch.fetch(url)
			if result.status_code == 200:
				self.response.write(result.content)
			else:
				self.response.status_code = result.status_code
		except urlfetch.Error:
			logging.exception('Caught exception fetching url')
	
	
class OauthHandler(webapp2.RequestHandler):
	def get(self):
		# Get the state variable from url returned by Google
		returned_state = self.request.get('state')
		# Get the stored state variable
		state_var = OauthVar.query().get()		
		# If the variables match, continue 
		if returned_state == state_var.state_var:
			# Create parameters to send in POST request
			form_fields = {
				'code': self.request.get('code'),
				'client_id': '518379713624-146hkku1jvqvti9o3vb3m733lav400bu.apps.googleusercontent.com',
				'client_secret': 'Ln2qFdruqZ5hbujJh6ykn2KC',
				'redirect_uri': 'https://final-project-161802.appspot.com/oauth',
				'grant_type': 'authorization_code',
			}
			
			# Delete any stray authentication tokens that may be stored
			all_tokens = AuthToken.query().fetch(keys_only=True)
			ndb.delete_multi(all_tokens)
			
			# POST request that exchanges the access code for a token
			try:
				form_data = urllib.urlencode(form_fields)
				headers = {'Content-Type': 'application/x-www-form-urlencoded'}
				result = urlfetch.fetch(
					url='https://www.googleapis.com/oauth2/v4/token',
					payload=form_data,
					method=urlfetch.POST,
					headers=headers)
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')	
			# Store and obtain token
			token_results = json.loads(result.content)
			auth_token = "Bearer " + token_results.get('access_token')
			self.response.write("Obtained token: ")	
			self.response.write(auth_token)
			
			# Store token in dict
			auth_tok = AuthToken(auth_token=auth_token)
			auth_tok.put()
		
		
class AnimalHandler(webapp2.RequestHandler):
	# POST data in order to make a new Animal
	def post(self):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
			
			# Set up ancestor Animal that will be parent of all Animal
			parent_key = ndb.Key(Animal, "parent_animal")
			# Send data into json obj
			animal_data = json.loads(self.request.body) 
			# Create new Animal
			new_animal = Animal(user_id=user_id, species=animal_data['species'], population=animal_data['population'], consumption_class=animal_data['consumption_class'], checked_in=animal_data['checked_in'], parent=parent_key)
			new_animal.put()
			animal_dict = new_animal.to_dict()
			animal_dict['self'] = '/animals/' + new_animal.key.urlsafe()
			# Dump data back out
			self.response.write(json.dumps(animal_dict)) 
			self.response.set_status(201)
		
	# GET data for animals
	def get(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
		
			checkedIn_val = self.request.get('checkedIn')
			if id:
				# GET request for information of an individual animal
				b = ndb.Key(urlsafe=id).get()
				if b.user_id == user_id:
					b_d = b.to_dict()
					# Create a self link using the key as id
					b_d['self'] = "/animals/"+id
					self.response.write(json.dumps(b_d))
				else:
					self.response.write("ERROR: Not authorized")

			# GET request for all animals
			if (id == None and not checkedIn_val):
			
				all_animals = Animal.query(Animal.user_id==user_id).fetch()
				final_list = []
				for animals in all_animals:
					json_animals = animals.to_dict()
					json_animals['self'] = '/animals/' + animals.key.urlsafe()
					final_list.append(json_animals)
				self.response.write(json.dumps(final_list))
		
			else:
				# Use GET multidict to find query variable
				# /animals?checkedIn=:boolean -- GET request for checkedIn=TRUE animals
				#if checkedIn_boolean is True:
				if checkedIn_val=="true":
					user_animals = Animal.query(Animal.user_id==user_id).fetch()
					final_list = []
					for animals in user_animals:
						if animals.checked_in == True:
							json_animal = animals.to_dict()
							json_animal['self'] = '/animals/' + animals.key.urlsafe()
							final_list.append(json_animal)
					self.response.write(json.dumps(final_list))

				# /animals?checkedIn=:boolean -- GET request for checkedIn=FALSE animals
				#if checkedIn_boolean is False:
				if checkedIn_val=="false":
					user_animals = Animal.query(Animal.user_id==user_id).fetch()
					final_list = []
					for animals in user_animals:
						if animals.checked_in == False:
							json_animal = animals.to_dict()
							json_animal['self'] = '/animals/' + animals.key.urlsafe()
							final_list.append(json_animal)
					self.response.write(json.dumps(final_list))
				
	# DELETE animal entries
	def delete(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
	
			if id:
				# Retrieve entity
				a = ndb.Key(urlsafe=id).get()	
				if a.user_id == user_id:
					# Delete the animal from Animal
					a.key.delete()		
			
					# Delete animal from any zoo species_list lists
					a_id = "/animals/"+id 							# = "/books/aghkZXZ-Tm9uZXImCxIEQm9vayILcGFyZW50X2Jvb2sMCxIEQm9vaxiAgICAgPSeCAw"
					zoo = Zoo.query(Zoo.species_list==a_id).get()	# = Customer(key=Key('Customer', 'parent_customer', 'Customer', 5074933356953600), balance=3.5, checked_out=[u'/book/aghkZXZ-Tm9uZXImCxIEQm9vayILcGFyZW50X2Jvb2sMCxIEQm9vaxiAgICAgPSeCAw', u'/book/aghkZXZ-Tm9uZXImCxIEQm9vayILcGFyZW50X2Jvb2sMCxIEQm9vaxiAgICAgPSuCww'], name=u'Dennis Howard')
		#			self.response.write(zoo.species_list)			# = [u'/animals/aghkZXZ-Tm9uZXImCxIEQm9vayILcGFyZW50X2Jvb2sMCxIEQm9vaxiAgICAgMymCQw', u'/book/aghkZXZ-Tm9uZXImCxIEQm9vayILcGFyZW50X2Jvb2sMCxIEQm9vaxiAgICAgMzmCww']
					if zoo:
						zoo.species_list.remove(a_id)
						zoo.put()
					# Set code 204
					self.response.set_status(204)
				else:
					self.response.write("ERROR: Unauthorized command")
				
	# PUT animal entries
	def put(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
			
			if id:
				# Retrieve entity
				a = ndb.Key(urlsafe=id).get()
				if a.user_id == user_id:
					# Send data into json obj
					animal_data = json.loads(self.request.body)
					
					# If there is a species, update
					if animal_data.get('species'):
						a.species=animal_data['species']
					# Else fill as NULL
					else:
						a.species=None
						
					# If there is a population, update
					if animal_data.get('population'):
						a.population=animal_data['population']
					# Else fill as NULL
					else:
						a.population=None
						
					# If there is a consumption_class, update
					if animal_data.get('consumption_class'):
						a.consumption_class=animal_data['consumption_class']
					# Else fill as NULL
					else:
						a.consumption_class=None
					
					# If there is a checked_in, update
					if animal_data.get('checked_in'):
						a.checked_in=animal_data['checked_in']
					# Else fill as NULL
					else:
						a.checked_in=False
					
					# Put edits into animal
					a.put()
					a_dict = a.to_dict()
					a_dict['self'] = '/animals/' + a.key.urlsafe()
					# Dump data back out
					self.response.write(json.dumps(a_dict))
					
				else:
					self.response.write("ERROR: Unauthorized command")
				
	# PATCH animal entries
	def patch(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
			
			if id:
				# Retrieve entity
				a = ndb.Key(urlsafe=id).get()
				if a.user_id == user_id:
					# Send data into json obj
					animal_data = json.loads(self.request.body)
					
					# If there is a species, update
					if animal_data.get('species'):
						a.species=animal_data['species']
						
					# If there is a population, update
					if animal_data.get('population'):
						a.population=animal_data['population']
						
					# If there is a consumption_class, update
					if animal_data.get('consumption_class'):
						a.consumption_class=animal_data['consumption_class']
					
					# If there is a checked_in, update
					if animal_data.get('checked_in'):
						a.checked_in=animal_data['checked_in']
		#			if animal_data.get('checked_in')==False:		###########
		#				a.checked_in=False							###########
					else:											###########
						a.checked_in=False
					
					# Put edits into animal
					a.put()
					a_dict = a.to_dict()
					a_dict['self'] = '/animals/' + a.key.urlsafe()
					# Dump data back out
					self.response.write(json.dumps(a_dict))
					
				else:
					self.response.write("ERROR: Unauthorized command")
					
				
class ZooHandler(webapp2.RequestHandler):
	# POST data in order to make a new zoo
	def post(self):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
		
			# Set up ancestor zoo that will be parent of all zoos
			parent_key = ndb.Key(Zoo, "parent_zoo")
			# Send data into json obj
			zoo_data = json.loads(self.request.body)
			# Create list to hold animals links in species_list
			zoo_animals = []
			if zoo_data['species_list']=="[]":
				# Create a new zoo
				new_zoo = Zoo(user_id=user_id, name=zoo_data['name'], city=zoo_data['city'], state=zoo_data['state'], size=zoo_data['size'], admission=zoo_data['admission'], species_list=zoo_animals, parent=parent_key)
			else:
				# Loop through all species_list animals passed in POST request
				for animals in zoo_data['species_list']:
					# Match species_list animals with list of animals in database
					animal_list = Animal.query(Animal.species==animals).get()
					# Adjust Animals list of checked_in to be consistent with species_list
					animal_list.checked_in=False	
					animal_list.put()				
					# Add the animal link to zoo_animals
					zoo_animals.append('/animals/' + animal_list.key.urlsafe())
				# Create a new zoo
				new_zoo = Zoo(user_id=user_id, name=zoo_data['name'], city=zoo_data['city'], state=zoo_data['state'], size=zoo_data['size'], admission=zoo_data['admission'], species_list=zoo_animals, parent=parent_key)

			new_zoo.put()
			zoo_dict = new_zoo.to_dict()
			zoo_dict['self'] = '/zoos/' + new_zoo.key.urlsafe()	
			# Dump data back out
			self.response.write(json.dumps(zoo_dict))
			self.response.set_status(201)
					
	# GET data for zoos
	def get(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
		
			# If there is an id
			if id:
				# /zoo/:zooid/animals -- GET request will return an array of full JSON animals entries
				if id.endswith("/animals"):
					z_id = id.replace("/animals", "")
					z = ndb.Key(urlsafe=z_id).get()
					if z.user_id == user_id:
						final_list = []
						all_animals = Animal.query().fetch()
						for animals in all_animals:
							a_id = '/animals/' + animals.key.urlsafe()
							for z_animals in z.species_list:
								if a_id == z_animals:
									json_animals = animals.to_dict()
									json_animals['self'] = '/animals/' + animals.key.urlsafe()
									final_list.append(json_animals)
						self.response.write(json.dumps(final_list))
					else:
						self.response.write("ERROR: Not authorized")
					
				# /zoos/:zooid/animals/:animalid
				elif "/animals/" in id:
					# Split id to obtain the zoo id and animal id
					id_list = id.split("/animals/")
					z_id = id_list[0]
					a_id = id_list[1]
					# Retrieve the animal
					a_list = []
					a = ndb.Key(urlsafe=a_id).get()
					if a.user_id == user_id:
						a_dict = a.to_dict()
						a_dict['self'] = '/animals/' + a.key.urlsafe()
						a_list.append(a_dict)
						self.response.write(json.dumps(a_list))
					else:
						self.response.write("ERROR: Not authorized")
					
				# /zoos/:zooid -- GET request will return information of an individual zoo
				else:
					z = ndb.Key(urlsafe=id).get()
					if z.user_id == user_id:
						z_d = z.to_dict()
						# Create a self link using the key as id
						z_d['self'] = "/zoos/" + id
						self.response.write(json.dumps(z_d))
					else:
						self.response.write("ERROR: Not authorized")
					
			# /zoos -- GET request will return all zoos
			else:
				all_zoos = Zoo.query().fetch()
				final_list = []
				for zoos in all_zoos:
					if zoos.user_id == user_id:
						json_zoos = zoos.to_dict()
						json_zoos['self'] = '/zoos/' + zoos.key.urlsafe()
						final_list.append(json_zoos)
				self.response.write(json.dumps(final_list))		

	# DELETE zoo entries ****************************************************************************
	def delete(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
		
			# /zoos/:zooid/animals/:animalid ----- DELETE request will check a animal back in
			if "/animals" in id:
				# Split id to obtain the zoo id and animal id
				id_list = id.split("/animals/")
				z_id = id_list[0]
				a_id = id_list[1]
				# Retrieve keys of the zoo and animal
				z = ndb.Key(urlsafe=z_id).get()
				if z.user_id == user_id:
					a = ndb.Key(urlsafe=a_id).get()
					if a.user_id == user_id:
						# Remove the animal from the zoo's species_list list
						z.species_list.remove('/animals/' + a.key.urlsafe())
						# Adjust animal's checked_in to be consistent with species_list
						a.checked_in=True		
						a.put()		
						z.put()
						self.response.set_status(200)
					else: 
						self.response.write("ERROR: Unauthorized command is unable to access the animal entity")
				else: 
					self.response.write("ERROR: Unauthorized command is unable to access the zoo entity")
					
			else: 
				# Retrieve entity
				z = ndb.Key(urlsafe=id).get()	
				if z.user_id == user_id:
					animal_list = Animal.query().fetch()
					
					book_keys = []
					# Loop through all zoo's species_list animals to set checked_in to True
					for animals in z.species_list:
						animals = animals.replace("/animals/", "")
						for animal_list_animals in animal_list:
							if animal_list_animals.key.urlsafe() == animals:
								animal_list_animals.checked_in = True
								animal_list_animals.put()							
					# Delete the zoo
					z.key.delete()	
					# Set code 204
					self.response.set_status(204)		
				else:
					self.response.write("ERROR: Unauthorized command")

	# PUT zoo entries
	def put(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
		
			# /zoos/:zooid/animals/:animalid ----- PUT request will check a animal out to zoo
			if "/animals/" in id:
				# Split id to obtain the zoo id and animal id
				id_list = id.split("/animals/")
				z_id = id_list[0]
				a_id = id_list[1]
				# Retrieve keys of the zoo and animal
				z = ndb.Key(urlsafe=z_id).get()
				if z.user_id == user_id:
					a = ndb.Key(urlsafe=a_id).get()
					if a.user_id == user_id:
						# Add the animal from the zoo's species_list list
						z.species_list.append('/animals/' + a.key.urlsafe())
						# Adjust animal's checked_in to be consistent with species_list
						a.checked_in=False		
						a.put()		
						z.put()
						self.response.set_status(201)
					else:
						self.response.write("ERROR: Unauthorized command is unable to access the animal entity")
				else:
					self.response.write("ERROR: Unauthorized command is unable to access the zoo entity")
				
			else:
				# Retrieve entity
				z = ndb.Key(urlsafe=id).get()
				if z.user_id == user_id:
					# Send data into json obj
					zoo_data = json.loads(self.request.body)
					
					# If there is a name, update
					if zoo_data.get('name'):
						z.name=zoo_data['name']
					# Else fill as NULL
					else:
						z.name=None
					
					# If there is a city, update
					if zoo_data.get('city'):
						z.city=zoo_data['city']
					# Else fill as NULL
					else:
						z.city=None
						
					# If there is a state, update
					if zoo_data.get('state'):
						z.state=zoo_data['state']
					# Else fill as NULL
					else:
						z.state=None
						
					# If there is a size, update
					if zoo_data.get('size'):
						z.size=zoo_data['size']
					# Else fill as NULL
					else:
						z.size=None	
						
					# If there is a admission, update
					if zoo_data.get('admission'):
						z.admission=zoo_data['admission']
					# Else fill as NULL
					else:
						z.admission=None	
						
					# If there is a species_list list, update
					if zoo_data.get('species_list'):
						# Create list to hold animal links in species_list
						zoo_animals = []
						# Loop through all species_list animals passed in PUT request
						for animals in zoo_data['species_list']:
							# Match species_list animals with list of animals in database
							animal_list = Animal.query(Animal.species==animals).get()
							if animal_list.user_id == user_id:
								# Add the animal link to zoo_animals
								zoo_animals.append('/animals/' + animal_list.key.urlsafe())
								z.species_list=zoo_animals
								# Adjust animals list of checked_in to be consistent with species_list
								animal_list.checked_in=False		
								animal_list.put()					
							else:
								self.response.write("ERROR: Unauthorized command is unable to access: " + str(animals) + "<br>")
					# Else fill as NULL
					else:
						z.species_list=[]
						
					# Put edits into zoo
					z.put()
					
					z_dict = z.to_dict()
					z_dict['self'] = '/zoos/' + z.key.urlsafe()
					# Dump data back out
					self.response.write(json.dumps(z_dict))		
				else:
					self.response.write("ERROR: Unauthorized command is unable to access the zoo entity")

	# PATCH zoo entries
	def patch(self, id=None):
		# Obtain the authorization token
		auth_token = AuthToken.query().get()
		if auth_token is None:
			self.response.write("ERROR: Not authorized")
		else:
			# Flush out user ID field
			user_id = None
			# GET request that uses token to access the Google+ account linked with the email login
			try:
				result = urlfetch.fetch(
					url='https://www.googleapis.com/plus/v1/people/me',
					headers={'Authorization': auth_token.auth_token})
			except urlfetch.Error:
				logging.exception('Caught exception fetching url')
			# Get user ID
			user_results = json.loads(result.content)
			user_id = user_results['id']
		
			if id:
				# Retrieve entity
				z = ndb.Key(urlsafe=id).get()
				if z.user_id == user_id:
					# Send data into json obj
					zoo_data = json.loads(self.request.body)
					
					# If there is a name, update
					if zoo_data.get('name'):
						z.name=zoo_data['name']
						
					# If there is a city, update
					if zoo_data.get('city'):
						z.city=zoo_data['city']
						
					# If there is a state, update
					if zoo_data.get('state'):
						z.state=zoo_data['state']
						
					# If there is a size, update
					if zoo_data.get('size'):
						z.size=zoo_data['size']
						
					# If there is a admission, update
					if zoo_data.get('admission'):
						z.admission=zoo_data['admission']				
						
					# If there is a species_list list given, update
					if zoo_data.get('species_list'):
						# Create list to hold animal links in species_list
						zoo_animals = []
						# Loop through all species_list animals passed in PUT request
						for animals in zoo_data['species_list']:
							# Match species_list animals with list of animals in database
							animal_list = Animal.query(Animal.species==animals).get()
							if animal_list.user_id == user_id:
								# Add the animal link to zoo_animals
								zoo_animals.append('/animals/' + animal_list.key.urlsafe())
								z.species_list=zoo_animals
								# Adjust Animals list of checked_in to be consistent with species_list
								animal_list.checked_in=False		
								animal_list.put()	
							else:
								self.response.write("ERROR: Unauthorized command is unable to access: " + str(animals) + "<br>")
					# Put edits into zoo
					z.put()
					
					z_dict = z.to_dict()
					z_dict['self'] = '/zoos/' + z.key.urlsafe()
					# Dump data back out
					self.response.write(json.dumps(z_dict))			
				else:
					self.response.write("ERROR: Not Authorized")


class DeleteAllHandler(webapp2.RequestHandler):
	def delete(self, id=None):
		# Delete all books in the database	
		all_animals = Animal.query().fetch(keys_only=True)
		ndb.delete_multi(all_animals)

		# Delete all customers in the database
		all_zoos = Zoo.query().fetch(keys_only=True)
		ndb.delete_multi(all_zoos)
		
		self.response.set_status(204)

class LogOutHandler(webapp2.RequestHandler):
	def get(self):
		# Delete any stray authentication tokens that may be stored
		all_tokens = AuthToken.query().fetch(keys_only=True)
		ndb.delete_multi(all_tokens)
		self.response.write("You have been logged out.")

class MainPage(webapp2.RequestHandler):
	def get(self):
		# Delete any stray authentication tokens that may be stored
		all_tokens = AuthToken.query().fetch(keys_only=True)
		ndb.delete_multi(all_tokens)
		# Notify user they are being redirected to login
		self.response.write("Welcome to class CS 496: Final Project - Cloud Only Implementation!! <br/>")
		self.response.write("It seems you have not logged in. Please press the Log In button to be redirected to authorize login credentials via Google+")
		# Button to redirect user to login
		login_page = "/login/"
		self.response.write('<form action="%s"><input type="submit" value="Log in"></form>' % login_page)


# Allow PATCH method handling on Webapp2
allowed_methods = webapp2.WSGIApplication.allowed_methods
new_allowed_methods = allowed_methods.union(('PATCH',))
webapp2.WSGIApplication.allowed_methods = new_allowed_methods
		

app = webapp2.WSGIApplication([
	('/', MainPage),
	('/oauth', OauthHandler),
	('/login/', LogInHandler),
	('/logout', LogOutHandler),
	('/zoos', ZooHandler),
	('/zoos/(.*)', ZooHandler),
	('/animals', AnimalHandler),
	('/animals/(.*)', AnimalHandler),
	('/animals?checkedIn=(.*)', AnimalHandler),			# GET list of all checked in/out animals
	('/delete', DeleteAllHandler),						# PURELY FOR TESTING, NO AUTHORIZATION NEEDED
], debug=True)

