#!/usr/bin/python
# -*- coding: utf8 -*-
"""
Runs on startup:
- subscribes to different topics and stores messages in the corresponding tables.
Uses connectors, MQTT capture classes, queued messages, queues, a thread for writing the messages into db and a main
class App for incorporating all these classes.
"""
import configparser
import re
import logging, logging.config
import paho.mqtt.client as mqtt_client
import time
import datetime
import threading
from queue import Queue
import sqlite3 as sqlite

INIFILE = "/etc/pythonic/push-to-db.ini"
logger = logging.config.fileConfig( INIFILE )

class Config:
	sections = {}
	inifilename = ""
	logger = None

	def __init__(self, inifile ):
		self.sections = {}
		self.logger = logging.getLogger('root')
		self._readini( inifile )

	def _ConfigSectionMap(self, config_parser, section):
		dict1 = {}
		option_names = config_parser.options(section)
		for option_name in option_names:
			try:
				dict1[option_name.lower()] = config_parser.get(section, option_name)
				if dict1[option_name.lower()] == -1:
					self.logger.warning("skip: %s" % option_name)
			except Exception as err:
				self.logger.warning("exception %s on key '%s'! Key value set to None" % (err,option_name) )
				dict1[option_name] = None
		return dict1

	def _readini( self, inifile ):
		parser = configparser.RawConfigParser()
		parser.read( inifile )
		self.inifilename = inifile
		for section in parser.sections():
			self.sections[section.lower()] = self._ConfigSectionMap(parser, section)

	def _dump( self ):
		print( "== Dump Config %s" % ("="*20) )
		print( self.inifilename )
		for section_name, section_values in self.sections.items():
			for key,value in section_values.items():
				print( "[%s].%s = %s" % (section_name, key, value) )

	def search_section( self, reg_exp ):
		_result = []
		_re = re.compile( reg_exp )
		for section in self.sections.keys():
			if _re.match( section ):
				_result.append( section )
		return _result

	def get( self, section, key, default = Exception ):
		if not( section in self.sections ):
			if default == Exception:
				raise AttributeError( "Invalid section request [%s].%s" %(section,key) )
			else:
				return default
		else:
			dic = self.sections[section] 
			if not( key in dic ):
				if default == Exception:
					raise AttributeError( "Invalid name request [%s].%s" % (section,key) )
				else:
					return default
			else:
				return dic[key]

	def getint( self, section, key, default = Exception ):
		return int( self.get(section, key, default) )

class QueuedMessage( object ):
	""" MQTT messages are wrapped in this object and added to the Queue. 
	"""

	__slots__ = ['receive_time', 'topic', 'payload', 'sub_handler', 'qos', 'timeserie_sub_handlers']

	def __init__(self, receive_time, topic, payload, qos, sub_handler, timeserie_sub_handlers = None ):
		self.receive_time = receive_time
		self.topic = topic
		self.payload = payload
		self.qos = qos
		self.sub_handler = sub_handler
		self.timeserie_sub_handlers = timeserie_sub_handlers

class MqttBaseCapture( object ):
	""" 
	Class that handles subscriptions.
	"""
	def __init__( self, subscribe_comalist, storage_target, connector ):

		self.sub_filters = subscribe_comalist.split(",")
		self.sub_regexps = []
		self.connector   = connector
		for sub_filter in self.sub_filters:
			self.sub_regexps.append( self.mqtt_filter_to_re(sub_filter) )
		self.storage_connector = (storage_target.split('.')[0]).strip()			 
		self.storage_table     = (storage_target.split('.')[1]).strip()

	def mqtt_filter_to_re( self, sub_filter ):
		""" convert subscription filter to regular expression """
		s = sub_filter.replace( '+', '[^/]+' ) 
		s = s.replace('#', '.+') 
		s = s.replace( '/', '\/' ) 
		return re.compile( s )

	def match_subscription( self, topic ):
		for _re in self.sub_regexps:
			if _re.match( topic ):
				return True
		return False

	def target_id( self ):
		return '%s.%s' % (self.storage_connector.lower(), self.storage_table.lower() )

	#this function will be later implemented
	def store_data( self, queued_message ):
		logging.getLogger('root').warning( '%s.store_data() must be overloaded' % self.__class__.__name__ )
		
class MqttTopicCapture( MqttBaseCapture ):
	""" Capture message and store in table topicmsg """
	def __init__( self, subscribe_comalist, storage_target, connector ):
		super( MqttTopicCapture, self).__init__( subscribe_comalist, storage_target, connector )

	def store_data( self, queued_message ):
		tsname = None
		if queued_message.timeserie_sub_handlers:
			for ts_sub_handler in [ sub_handler for sub_handler in queued_message.timeserie_sub_handlers if sub_handler.storage_connector == self.storage_connector ]:
				tsname = ts_sub_handler.storage_table
				break;
		self.connector.update_value( self.storage_table, queued_message.receive_time, 
			queued_message.topic, queued_message.payload, queued_message.qos, tsname = tsname )

class MqttTimeserieCapture( MqttBaseCapture ):
	""" Capture message and store in ts_xxxx """
	def __init__( self, subscribe_comalist, storage_target, connector ):
		super( MqttTimeserieCapture, self).__init__( subscribe_comalist, storage_target, connector )

	def store_data( self, queued_message ):
		self.connector.timeserie_append( self.storage_table, queued_message.receive_time, 
			queued_message.topic, queued_message.payload, queued_message.qos )

# Connectors:
class BaseConnector( object ):
	def __init__( self, params ):
		self.params = params

class SqliteConnector( BaseConnector ):
	""" Connector to Sqlite database """
	def __init__( self, params ):
		super( SqliteConnector, self ).__init__( params )
		# typiquement /var/local/sqlite/pythonic.db
		self.db_file = params['db']
		self._conn = None 

	def is_connected( self ):
		return (self._conn != None)

	def connect( self ):
		if not self.is_connected():
			logging.getLogger('connector').debug( 'Connect to sqlite db %s' % self.db_file )
			self._conn = sqlite.connect( self.db_file )

	def disconnect( self ):
		if self.is_connected():
			logging.getLogger('connector').debug( 'disconnect() sqlite' )
			self._conn.close()
			self._conn = None

	def commit( self ):
		if self.is_connected():
			logging.getLogger('connector').debug( 'commit() on sqlite' )
			self._conn.commit()

	def update_value( self, table_name, receive_time, topic, payload, qos, tsname=None ):
		logging.getLogger('connector').debug( 'update_value() on sqlite' )

		if tsname:
			sSql = "UPDATE %s SET message = ?, qos = ?, rectime = ?, tsname = ?  where topic = ?" % table_name
			_data = (payload, qos, receive_time, tsname, topic)
		else:
			sSql = "UPDATE %s SET message = ?, qos = ?, rectime = ? where topic = ?" % table_name
			_data = (payload, qos, receive_time, topic)

		self.connect()
		cur = self._conn.cursor()
		r = cur.execute( sSql, _data )
		if r.rowcount == 0:
			if tsname:
				sSql = "INSERT INTO %s (topic,message,qos,rectime, tsname) VALUES (?,?,?,?,?)" % table_name
				r = cur.execute( sSql, (topic,payload,qos,receive_time, tsname) )			
			else:
				sSql = "INSERT INTO %s (topic,message,qos,rectime) VALUES (?,?,?,?)" % table_name
				r = cur.execute( sSql, (topic,payload,qos,receive_time) )

	def timeserie_append( self, table_name, receive_time, topic, payload, qos ):
		logging.getLogger('connector').debug( 'timeserie_append() on sqlite' )

		sSql = "INSERT INTO %s (topic,message,qos,rectime) VALUES (?,?,?,?)" % table_name

		self.connect()	
		cur = self._conn.cursor()
		r = cur.execute( sSql, (topic,payload,qos,receive_time) )			

#Thread for treaing 
class MessageLazyWriter(threading.Thread):
	""" Thread for treating queued messages containting mqtt messages and storing them in the database
	    """ 
	def __init__( self, params, message_queue, connectors, stopper_event ):
		
		super( MessageLazyWriter, self ).__init__()
		# configuring the thread
		self.max_queue_latency   = int(params['maxqueuelatency'])
		self.max_queue_size      = int(params['maxqueuesize'])
		self.pause_after_process = int(params['pauseafterprocess'])
		# Synced FIFO queue
		self.message_queue = message_queue
		# Connectors
		self.connectors = connectors
		# What event stops the thread
		self.stopper_event = stopper_event
		self.logger = logging.getLogger('root')

	def run( self ):
		self.logger.debug( 'LazyWriter thread started')
		latency_start = None 
		while not self.stopper_event.is_set():
			if self.message_queue.empty():
				# time.sleep( self.pause_after_process )
				latency_start = None
				continue 
			else:
				if latency_start == None:
					self.logger.debug( 'LazyWriter latency_start set to now')
					latency_start = datetime.datetime.now()

			if self.message_queue.qsize() > self.max_queue_size:
				self.logger.info( 'LazyWriter queue size %s reached -> Process_message_queue.' % self.max_queue_size )
				self.process_message_queue()
				latency_start = None
				time.sleep( self.pause_after_process )

			elif latency_start and ((datetime.datetime.now()-latency_start).seconds > self.max_queue_latency):
				self.logger.info( 'LazyWriter latency %s sec reached -> Process_message_queue.' % self.max_queue_latency )
				self.process_message_queue()
				latency_start = None
				time.sleep( self.pause_after_process )

		self.logger.debug( 'LazyWriter thread exit')

	def process_message_queue( self ):
		""" Write the queued message into the database """
		con_list = []
		pmq_logger = logging.getLogger('pmq')
		while not self.message_queue.empty():
			queued_message = self.message_queue.get()
			try:
				pmq_logger.debug( 'process_message_queue %s for handler %s on %s with payload %s' % \
					(queued_message.topic, queued_message.sub_handler.__class__.__name__, \
						queued_message.sub_handler.target_id(), queued_message.payload) )
				# gather connectors
				connector = queued_message.sub_handler.connector
				if not connector in con_list:
					con_list.append( connector )
				# Let the subhandler (MQTT capture class) do the writing into the db
				queued_message.sub_handler.store_data( queued_message )
			except Exception as err:
				pmq_logger.error( 'process_message_queue encounter an error while processing the message' )
				pmq_logger.error( '  %s with %s' % (err.__class__.__name__, err) )				
				pmq_logger.error( '  handler: %s' % queued_message.sub_handler.__class__.__name__ )
				pmq_logger.error( '  topic  : %s' % queued_message.topic )
				pmq_logger.error( '  payload: %s' % queued_message.payload )
			finally:
				self.message_queue.task_done()
		# Commit on all connectors
		for connector in con_list:
			connector.commit()
			connector.disconnect()
				

class App:
	""" Class for application logic
	needs the config file, subhandlers, connectors and a message queue.
	
	"""

	def __init__(self):
		self.logger = logging.getLogger('root')
		self.logger.info( 'Initializing app')

		self.mqtt = None
		self.message_queue = None 
		self.connectors = None
		self.sub_handlers = None
		self.stopper = None  

		self.config = Config( INIFILE )
		# self.config._dump()

		self.build_connectors()
		self.build_sub_handlers()

	def build_connectors( self ):
		"""Construct connectors from config file"""
		self.connectors = {} 
		# Collect the connectors: "connector.xxxx"
		lst = self.config.search_section( "^connector\.\w+$" )
		for section in lst:
			connector_classname = self.config.get( section, 'class')
			connector_class = globals()[connector_classname]
			self.connectors[ section.replace('connector.','') ] = \
				connector_class( self.config.sections[section] )

	def build_sub_handlers( self ):
		"""Construct sub_handlers from config file"""
		self.sub_handlers = [] 
		# collect the subhandlers "mqtt.capture.x"
		lst = self.config.search_section( "^mqtt\.capture\.\d+$" )
		for section in lst:
			handler_classname = self.config.get( section, 'class' )
			handler_class = globals()[handler_classname]
			connector_name = self.config.get( section, 'storage').split('.')[0]
			if not(connector_name in self.connectors):
				raise Exception( 'No [connector.%s] defined for storage=%s (see [%s])' % (connector_name,self.config.get( section, 'storage'),section) )
			connector = self.connectors[connector_name]
			self.sub_handlers.append(
				handler_class( 
					self.config.get( section, 'subscribe' ),
					self.config.get( section, 'storage'),
					connector 
				)
			)

	def _mqtt_on_connect( self, client, userdata, flags, rc ):
		""" connecting  to the broker """
		self.logger.info( "mqtt connect return code: %s" % rc )
		self.mqtt_connected = (rc == 0)

	def _mqtt_on_message( self, client, userdata, message ):
		""" receiving message from the broker """
		self.logger.info( "getting MQTT message..." )
		self.logger.info( "  topic  : %s" % message.topic )
		self.logger.info( "  message: %s" % message.payload )
		self.logger.info( "  QoS    : %s" % message.qos )
		try:
			to_call = {} # sub handler to call
			for sub_handler in self.sub_handlers:
				if sub_handler.match_subscription( message.topic ):
					target_id = sub_handler.target_id()
					if not( target_id in to_call ):
						to_call[target_id] = sub_handler

			# Handle TimeSerie capture first
			queued_timeserie = []
			for target_id, sub_handler in to_call.items() : 
				if not isinstance( sub_handler, MqttTimeserieCapture ):
					continue
				to_queue = QueuedMessage( receive_time=datetime.datetime.now(), \
					topic=message.topic, payload=message.payload, \
					qos=message.qos, sub_handler=sub_handler  )
				self.message_queue.put( to_queue )
				# Remember the queued timeserie for this message
				queued_timeserie.append( sub_handler )
			
			# Handle Message Capture after
			for target_id, sub_handler in to_call.items() : 
				if isinstance( sub_handler, MqttTimeserieCapture ):
					continue
				to_queue = QueuedMessage( receive_time=datetime.datetime.now(), \
					topic=message.topic, payload=message.payload, \
					qos=message.qos, sub_handler=sub_handler, \
					timeserie_sub_handlers=queued_timeserie if len(queued_timeserie)>0 else None  )
				self.message_queue.put( to_queue )

				#sub_handler.process_message( message.topic, message.payload )

		except Exception as err:
			self.logger.error( 'Exception while processing MQTT message')
			self.logger.error( "  topic: %s" % message.topic )
			self.logger.error( "  message: %s" % message.payload )
			self.logger.error( "  exception: %s" % err )

	def connect_broker( self ):
		""" Connect the broker and perform all the needed subscriptions """
		
		if self.mqtt:
			del( self.mqtt )
			self.mqtt = None
		self.mqtt_connected = False

		self.mqtt = mqtt_client.Client( client_id = 'push-to-db' )
		self.mqtt.on_connect = self._mqtt_on_connect
		self.mqtt.on_message = self._mqtt_on_message
		if not( self.config.get( 'mqtt.broker', 'username', default = None ) in (None, 'None') ):
			self.mqtt.username_pw_set( 
				username = self.config.get( 'mqtt.broker', 'username'),
				password = self.config.get( 'mqtt.broker', 'password')
				)
		self.mqtt.connect(
				host = self.config.get( 'mqtt.broker', 'mqtt_broker' ),
				port = self.config.getint( 'mqtt.broker', 'mqtt_port' ),
				keepalive = self.config.getint( 'mqtt.broker', 'mqtt_keepalive')
			)

		# subscribe
		sub_done = [] 
		for sub_handler in self.sub_handlers:
			for sub in sub_handler.sub_filters:
				if not sub in sub_done:
					self.logger.info( 'subscribing %s' % sub )
					self.mqtt.subscribe( sub )
					sub_done.append( sub )

	def run( self ):
		self.logger.info( 'Running app')
		self.message_queue = Queue() 
		self.stopper = threading.Event()

		lazyWriter = MessageLazyWriter( self.config.sections['lazywriter'], \
			self.message_queue, self.connectors, \
			self.stopper )
		lazyWriter.start()

		try:
			self.connect_broker()
		except Exception as err:
			self.logger.error( 'connect_broker() error with %s' % err)
			raise
		
		try:
			self.mqtt.loop_forever()
		except Exception as err:
			self.logger.error( 'Error while processing broker messages! %s' % err )
		except KeyboardInterrupt:
			self.logger.info( 'User abord with KeyboardInterrupt exception' )
		except SystemExit:
			self.logger.info( 'System exit with SystemExit exception!' )

		# signal threads to stop
		self.stopper.set()

		# Wait the thread to finish
		self.logger.info( 'Waiting for LazyWriter thread...')
		lazyWriter.join()

if __name__ == "__main__":
	#main()
	app = App()
	app.run()

