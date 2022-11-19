""""
atmospheric pressure and temperature BME280
lux  with TSL 2561
"""

from machine import Pin, I2C, reset
from time import sleep, time
from ubinascii import hexlify
from network import WLAN

CLIENT_ID = 'shed'

MQTT_SERVER = "192.168.1.210"
MQTT_USER = 'pusr103'
MQTT_PSWD = '21052017'

ERROR_REBOOT_TIME = 3600 # 1 h = 3600 sec

class LED:
	def __init__( self ):
		import os
		if os.uname().nodename == 'esp32':
			self._led = Pin( 13, Pin.OUT )
			self._reverse = True # LED in direct logic
		else:
			self._led = Pin( 0, Pin.OUT )
			self._reverse = False # LED in reverse logic

	def value( self, value=None ):
		if value == None:
			if self._reverse:
				return not( self._led.value() )
			else:
				return self._led.value()
		else:
			if self._reverse:
				value = not( value )
			self._led.value( value )

def get_i2c():
	import os
	if os.uname().nodename == 'esp32':
		return I2C( sda=Pin(23), scl=Pin(22) )
	else:
		return I2C( sda=Pin(4), scl=Pin(5) )

runapp = Pin( 12,  Pin.IN, Pin.PULL_UP )
led = LED()
led.value( 1 ) # eteindre

def led_error( step ):
	global led
	t = time()
	while ( time()-t ) < ERROR_REBOOT_TIME:
		for i in range( 20 ):
			led.value(not(led.value()))
			sleep(0.100)
		led.value( 1 ) # eteindre
		sleep( 1 )
		# clignote nbr fois
		for i in range( step ):
			led.value( 0 )
			sleep( 0.5 )
			led.value( 1 )
			sleep( 0.5 )
		sleep( 1 )
	# Re-start the ESP
	reset()

if runapp.value() != 1:
	from sys import exit
	exit(0)

led.value( 0 ) # allumer

# --- MAIN PROGRAM ---
from umqtt.simple import MQTTClient
try:
	q = MQTTClient( client_id = CLIENT_ID, server = MQTT_SERVER, user = MQTT_USER, password = MQTT_PSWD )
	sMac = hexlify( WLAN().config( 'mac' ) ).decode()
	q.set_last_will( topic="disconnect/%s" % CLIENT_ID , msg=sMac )
	if q.connect() != 0:
		led_error( step=1 )
except Exception as e:
	print( e )
	# check MQTT_SERVER, MQTT_USER, MQTT_PSWD
	led_error( step=2 )

try:
	from tsl2561 import TSL2561
	from bme280 import BME280, BMP280_I2CADDR
except Exception as e:
	print( e )
	led_error( step=3 )

i2c = get_i2c()

# CREATE sensors
try:
	tsl = TSL2561( i2c=i2c )
	bmp = BME280( i2c=i2c, address=BMP280_I2CADDR )
except Exception as e:
	print( e )
	led_error( step=4 )


try:
	sMac = hexlify( WLAN().config( 'mac' ) ).decode()
	q.publish( "connect/%s" % CLIENT_ID , sMac )
except Exception as e:
	print( e )
	led_error( step=5 )


import uasyncio as asyncio

def capture_1h():
	global q
	global tsl

	# tsl2561 - LUX sensor
	lux = "{0:.2f}".format( tsl.read() )
	q.publish( "home/outside/shed/lux", lux )

def capture_20min():
	global q
	global bmp
	# bmp280 - for pressure and temperature
	# capturer les valeurs sous format texte
	(t,p,h) = bmp.raw_values
	# transformer en chaine de caractère
	t = "{0:.2f}".format(t)
	p = "{0:.2f}".format(p)
    h = "{0:.2f}".format(h)
	q.publish( "home/outside/shed/pathm", p )
	q.publish( "home/outside/shed/temp", t ) 
    q.publish("home/outside/shed/hrel",h )
    

def heartbeat():
	sleep( 0.2 )

async def run_every( fn, min= 1, sec=None):
	""" Execute a function fn every min minutes or sec secondes"""
	global led
	wait_sec = sec if sec else min*60
	while True:
		led.value( 1 )
		fn()
		led.value( 0 ) 
		await asyncio.sleep( wait_sec )

async def run_app_exit():
	global runapp
	while runapp.value()==1:
		await asyncio.sleep( 10 )
	return

loop = asyncio.get_event_loop()
loop.create_task( run_every(capture_1h, min=60) )
loop.create_task( run_every(capture_20min, min=20) )
loop.create_task( run_every(heartbeat, sec=10) )
try:
	loop.run_until_complete( run_app_exit() )
except Exception as e :
	print( e )
	led_error( step=6 )

loop.close()
led.value( 1 ) 
