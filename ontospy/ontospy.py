import sys, os, urllib2, time

import rdflib	 # so we have it available as a namespace
from rdflib import Namespace, exceptions, URIRef, RDFS, RDF, BNode
from rdflib.namespace import OWL, DC

from libs.util import *
from libs.entities import *

from libs.queryHelper import QueryHelper

from _version import *



class Graph(object):
	"""
	Object that scan an rdf graph for schema definitions (aka 'ontologies') 
	
	In [1]: import ontospy2
	INFO:rdflib:RDFLib Version: 4.2.0

	In [2]: g = ontospy2.Graph("npgcore_latest.ttl")
	Loaded 3478 triples
	Ontologies found: 1
	
	"""

	def __init__(self, source, text=False, endpoint=False, rdf_format=None):
		"""
		Load the graph in memory, then setup all necessary attributes.
		"""
		super(Graph, self).__init__() 

		self.rdfgraph = rdflib.Graph()
		self.graphuri	= None
		self.queryHelper = None # instantiated after we have a graph
		
		self.ontologies = []
		self.classes = []	
		self.namespaces = []
		
		self.properties = [] 
		self.annotationProperties = [] 
		self.objectProperties = []
		self.datatypeProperties = []
		
		self.toplayer = []
		self.toplayerProperties = []
		
		# keep track of the rdf source
		self.IS_ENDPOINT = False
		self.IS_FILE = False
		self.IS_URL = False
		self.IS_TEXT = False
		
		# finally		
		self.__loadRDF(source, text, endpoint, rdf_format)
		# extract entities into
		self._scan()

	
	def __repr__(self):
		return "<OntoSPy Graph (%d triples)>" % (len(self.rdfgraph))
				


	
	def __loadRDF(self, source, text, endpoint, rdf_format):
		"""
		After a graph has been loaded successfully, set up all params
		"""
		
		# LOAD THE GRAPH
				
		if text:
			self.IS_TEXT = True
			rdf_format = rdf_format or "turtle"
		
		
		elif endpoint:
			self.IS_ENDPOINT = True
			# @TODO 
			raise Exception("Sorry - the SPARQL component is not available yet.")

		else:

			if type(source) == type("string"):
				self.IS_URL = True
				
				if source.startswith("www."): #support for lazy people
					source = "http://%s" % str(source)
				self.graphuri = source	# default uri is www location
				rdf_format = rdf_format or guess_fileformat(source)

			elif type(source) == file:
				self.IS_FILE = True
				
				self.graphuri = source.name # default uri is filename
				rdf_format = rdf_format or guess_fileformat(source.name)
			
			else:
				raise Exception("You passed an unknown object. Only URIs and files are accepted.") 
			
		#FINALLY, DO THE LOADING BIT:		

		try:
			if self.IS_TEXT == True:			
				self.rdfgraph.parse(data=source, format=rdf_format)
			else:
				self.rdfgraph.parse(source, format=rdf_format)
			# set up the query helper too
			self.queryHelper = QueryHelper(self.rdfgraph)	
			printDebug("Loaded %d triples" % len(self.rdfgraph))
		
		except:
			printDebug("\nError Parsing Graph (assuming RDF serialization was *%s*)\n" % (rdf_format))	 
			raise




	def serialize(self, rdf_format="turtle"):
		""" Shortcut that outputs the graph """
		return self.rdfgraph.serialize(format=rdf_format)
			
	
	def sparql(self, stringa):
		""" wrapper around a sparql query """
		qres = self.rdfgraph.query(stringa)
		return list(qres)
			

	def __extractNamespaces(self, only_base = False):
		""" 
		Extract graph namespaces. Returns either the base namespace only, or all of them.
		Namespaces are given in this format:

			In [01]: for x in graph.namespaces():
					....:			print x
					....:
					....:
			('xml', rdflib.URIRef('http://www.w3.org/XML/1998/namespace'))
			('', rdflib.URIRef('http://cohereweb.net/ontology/cohere.owl#'))
			(u'owl', rdflib.URIRef('http://www.w3.org/2002/07/owl#'))
			('rdfs', rdflib.URIRef('http://www.w3.org/2000/01/rdf-schema#'))
			('rdf', rdflib.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#'))
			(u'xsd', rdflib.URIRef('http://www.w3.org/2001/XMLSchema#'))

		We assume that a base namespace is implied by an empty prefix		
		"""

		exit = []
		if self.IS_ENDPOINT==True:
			return False
		else:
			if only_base:
				ll = [x for x in self.rdfgraph.namespaces() if x[0] == '']
				exit = ll[0][1] if ll else None
			else:
				out = []
				for x in self.rdfgraph.namespaces():
					if x[0]:
						out.append(x)
					else: 
						# if the namespace is blank (== we have a base namespace)
						prefix = inferNamespacePrefix(x[1])
						if prefix:
							out.append((prefix, x[1]))
						else:
							out.append(('base', x[1]))
				if self.graphuri not in [y for x,y in self.rdfgraph.namespaces()]:
					# if not base namespace is set, try to simulate one
					out.append(('', self.graphuri))	 # use to be '_temp' ... WHY?
		
				exit = sorted(out)
		# finally..
		self.namespaces = exit
		


	
	# ------------	
	# === main method === #	 
	# ------------
	
	def _scan(self, source=None, text=False, endpoint=False, rdf_format=None):
		""" 
		scan a source of RDF triples 
		build all the objects to deal with the ontology/ies pythonically
				
		In [1]: g.scan("npgcore_latest.ttl")
		Ontologies found: 1
		Out[3]: [<OntoSPy: Ontology object for uri *http://ns.nature.com/terms/*>]
		
		"""
		
		if source: # add triples dynamically
			self.__loadRDF(source, text, endpoint, rdf_format)
		
		printDebug("started scanning...")
						
		self.__extractNamespaces()
		
		self.__extractOntologies()
		printDebug("Ontologies found: %d" % len(self.ontologies))
						
		self.__extractClasses()
		printDebug("Classes	   found: %d" % len(self.classes))
		
		self.__extractProperties()
		printDebug("Properties found: %d" % len(self.properties))
		printDebug("...Annotation	: %d" % len(self.annotationProperties))
		printDebug("...Datatype		: %d" % len(self.datatypeProperties))
		printDebug("...Object		: %d" % len(self.objectProperties))
		
		self.__computeTopLayer()

			
		




	
	
	def __extractOntologies(self, exclude_BNodes = False, tryDC_metadata = True, return_string=False):
		"""
		returns Ontology class instances
				
		"""
		out = []
	
		qres = self.queryHelper.getOntology()

		if qres:
			# NOTE: SPARQL returns a list of rdflib.query.ResultRow (~ tuples..)
			
			for candidate in qres:
				if isBlankNode(candidate[0]):
					if exclude_BNodes:
						continue
					if tryDC_metadata:
						# @todo: transform into SPARQL EG
						# qres2 = self.rdfgraph.query(
						#	  """SELECT DISTINCT ?z
						#		 WHERE {
						#			<%s> dc:identifier ?z
						#		 }""" % str(candidate[0]))
							   
						checkDC_ID = [x for x in self.rdfgraph.objects(candidate[0], DC.identifier)]
						if checkDC_ID:
							out += [Ontology(checkDC_ID[0])]
							
				else:
					out += [Ontology(candidate[0])]
			
			
		else:
			printDebug("No owl:Ontologies found")
			
		#finally		
		self.ontologies = out
		# add all annotations/triples
		for onto in self.ontologies:
			onto.triples = self.queryHelper.entityTriples(onto.uri)
		


	##################
	#  
	#  METHODS for MANIPULATING RDFS/OWL CLASSES 
	# 
	#  RDFS:class vs OWL:class cf. http://www.w3.org/TR/owl-ref/ section 3.1
	#
	##################


	def __extractClasses(self):
		""" 
		2015-06-04: removed sparql 1.1 queries
		2015-05-25: optimized via sparql queries in order to remove BNodes
		2015-05-09: new attempt 
		"""
		self.classes = [] # @todo: keep adding? 
		
		qres = self.queryHelper.getAllClasses()
		# instantiate classes 
		
		for candidate in qres:
			# tip: OntoClass(uri, rdftype=None, namespaces = None)
			self.classes += [OntoClass(candidate[0], candidate[1], self.namespaces)]
				
		
		#add more data
		for aClass in self.classes:
			
			aClass.triples = self.queryHelper.entityTriples(aClass.uri)
					
			# add direct Supers				
			directSupers = self.queryHelper.getClassDirectSupers(aClass.uri)
			
			for x in directSupers:
				superclass = self.getClass(uri=x[0])
				if superclass: 
					aClass.parents.append(superclass)
					
					# add inverse relationships (= direct subs for superclass)
					if aClass not in superclass.children:
						 superclass.children.append(aClass)
			



	def __extractProperties(self, removeBlankNodes = True):
		""" 
		2015-06-04: removed sparql 1.1 queries
		2015-06-03: analogous to get classes		
		"""
		self.properties = [] # @todo: keep adding? 
		self.annotationProperties = [] 
		self.objectProperties = []
		self.datatypeProperties = [] 
		
		qres = self.queryHelper.getAllProperties()
		
		# instantiate properties 
		
		for candidate in qres:
			if removeBlankNodes and isBlankNode(candidate[0]):
				pass
			else: # tip: candidate[1] is the RDF type of the property
				self.properties += [OntoProperty(candidate[0], candidate[1], self.namespaces)]


		#add more data
		for aProp in self.properties:
			
			if aProp.rdftype == rdflib.OWL.DatatypeProperty:
				self.datatypeProperties += [aProp]
			elif aProp.rdftype == rdflib.OWL.AnnotationProperty:
				self.annotationProperties += [aProp]
			elif aProp.rdftype == rdflib.OWL.ObjectProperty:
				self.objectProperties += [aProp]
			else:
				pass
			
			aProp.triples = self.queryHelper.entityTriples(aProp.uri)
			aProp._buildGraph() # force construction of mini graph

			self.__buildDomainRanges(aProp)
			
			# add direct Supers				
			directSupers = self.queryHelper.getPropDirectSupers(aProp.uri)
			
			for x in directSupers:
				superprop = self.getProperty(uri=x[0])
				if superprop: 
					aProp.parents.append(superprop)
				
					# add inverse relationships (= direct subs for superprop)
					if aProp not in superprop.children:
						 superprop.children.append(aProp)
		
					
					

	def getClass(self, id=None, uri=None, match=None):
		""" 
		get the saved-class with given ID or via other methods...
		
		Note: it tries to guess what is being passed..
	
		In [1]: g.getClass(uri='http://www.w3.org/2000/01/rdf-schema#Resource')
		Out[1]: <Class *http://www.w3.org/2000/01/rdf-schema#Resource*>
		
		In [2]: g.getClass(10)
		Out[2]: <Class *http://purl.org/ontology/bibo/AcademicArticle*> 

		In [3]: g.getClass(match="person")
		Out[3]: 
		[<Class *http://purl.org/ontology/bibo/PersonalCommunicationDocument*>,
		 <Class *http://purl.org/ontology/bibo/PersonalCommunication*>,
		 <Class *http://xmlns.com/foaf/0.1/Person*>]
		
		"""
		
		if not id and not uri and not match:
			return None
			
		if type(id) == type("string"):
			uri = id
			id = None
			if not uri.startswith("http://"):
				match = uri
				uri = None
		if match:
			if type(match) != type("string"):
				return []
			res = []
			for x in self.classes:
				if match.lower() in x.uri.lower():
					res += [x]
			return res
		else:
			for x in self.classes:
				if id and x.id == id:
					return x
				if uri and x.uri.lower() == uri.lower():
					return x
			return None


	def getProperty(self, id=None, uri=None, match=None):
		""" 
		get the saved-class with given ID or via other methods...
		
		Note: analogous to getClass method		
		"""
		
		if not id and not uri and not match:
			return None
			
		if type(id) == type("string"):
			uri = id
			id = None
			if not uri.startswith("http://"):
				match = uri
				uri = None
		if match:
			if type(match) != type("string"):
				return []
			res = []
			for x in self.properties:
				if match.lower() in x.uri.lower():
					res += [x]
			return res
		else:
			for x in self.properties:
				if id and x.id == id:
					return x
				if uri and x.uri.lower() == uri.lower():
					return x
			return None
			
					

	def __computeTopLayer(self):

		exit = []
		for c in self.classes:
			if not c.parents:
				exit += [c]
		self.toplayer = exit # sorted(exit, key=lambda x: x.id) # doesnt work

		# properties 
		exit = []
		for c in self.properties:
			if not c.parents:
				exit += [c]
		self.toplayerProperties = exit # sorted(exit, key=lambda x: x.id) # doesnt work
		

	def printClassTree(self, element = 0, level=0, showids=True):
		""" 
		Print nicely into stdout the class tree of an ontology 
		
		Note: indentation is made so that ids up to 3 digits fit in, plus a space.
		[123]1--
		[1]123--
		[12]12--
		"""
		
		if not element:	 # first time
			for x in self.toplayer:
				# NOTE: this is the util.printClassTree
				printGenericTree(x, level, showids)
		
		else:
			printGenericTree(element)		


	def printPropertyTree(self, element = 0, level=0, showids=True):
		""" 
		Print nicely into stdout the property tree of an ontology 
		
		Note: indentation is made so that ids up to 3 digits fit in, plus a space.
		[123]1--
		[1]123--
		[12]12--
		"""
		
		if not element:	 # first time
			for x in self.toplayerProperties:
				# NOTE: this is the util.printPropertyTree
				printGenericTree(x, level, showids)
		
		else:
			printGenericTree(element)
			
			

	###########

	# METHODS for MANIPULATING RDFS/OWL PROPERTIES

	###########



	def __buildDomainRanges(self, aProp):			
		"""
		extract domain/range details and add to Python objects
		"""
		domains = aProp.rdfgraph.objects(None, rdflib.RDFS.domain)
		ranges =  aProp.rdfgraph.objects(None, rdflib.RDFS.range)
		
		for x in domains:
			if not isBlankNode(x):
				aClass = self.getClass(uri=str(x))
				if aClass:
					aProp.domains += [aClass]
					aClass.domain_of += [aProp]
				else:
					aProp.domains += [x]  # edge case: it's not an OntoClass instance?
				
		for x in ranges:
			if not isBlankNode(x):
				aClass = self.getClass(uri=str(x))
				if aClass:
					aProp.ranges += [aClass]
					aClass.range_of += [aProp]
				else:
					aProp.ranges += [x] 







##################
# 
#  COMMAND LINE 
#
##################


def main(argv):
	"""

	"""
	DEFAULT_ONTO = "data/schemas/pizza.ttl"
	
	sTime = time.time()
	
	if argv:
		g = Graph(argv[0])
	else:
		print "Argument not provided... loading test graph: %s" % DEFAULT_ONTO
		g = Graph(DEFAULT_ONTO)

	ontologies = g.ontologies
	
	for o in ontologies:
		# print "Ontology URI:", o.uri
		# print "Annotations:"
		print "\nMetadata\n-----------"
		o.printTriples()
	
	
	if False:
		print "Top Layer:", str([cc.qname for cc in g.toplayer])
	
	# if False:
	#	for c in g.classes:
	#		print c.qname
	#		print "...direct Supers: ", len(c.directSupers), str([cc.qname for cc in c.directSupers])
	#		print "...direct Subs: ", len(c.directSubs), str([cc.qname for cc in c.directSubs])


		# c.triplesPrint()
	
	if True:
		print "\nMain Taxonomy\n-----------"
		g.printClassTree(showids=False)


	# finally:
	
	# print some stats.... 
	eTime = time.time()
	tTime = eTime - sTime
	print "*" * 30
	print "Time:	   %0.2fs" %  tTime
		

if __name__ == '__main__':
	main(sys.argv[1:])
	
	

