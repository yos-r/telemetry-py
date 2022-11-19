"""
need: photoresistance, magnetic contact, tmp36 and ADS1115 for temp reading
"""
import os
from machine import Pin, I2C, reset
import time
from ubinascii import hexlify
from network import WLAN

CLIENT_ID = 'balcony'

MQTT_SERVER = "192.168.1.210"

MQTT_USER = 'pusr103'
MQTT_PSWD = '21052017'

ERROR_REBOOT_TIME = 3600 # 1 h = 3600 sec

CONTACT_PIN =  27 if os.uname().nodename == 'esp32' else 13  # on what pin is the PIR located
last_contact_state = 0 # 0=closed, 1=open

LDR_HYST  = 200
last_ldr_state = "NOIR" # Noir ou ECLAIRAGE

def ldr_to_state( adc_ldr, adc_pivot ):
	""" Transform light value to LIGHT or DARK """
	global last_ldr_state
	# print( "adc_ldr, adc_pivot = %s, %s" %
	#        (adc_ldr, adc_pivot) )
	if adc_ldr > (adc_pivot+LDR_HYST):
		return "LIGHT"
	elif adc_ldr < (adc_pivot-LDR_HYST):
		return "DARK"
	else:
		return last_ldr_state

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
		""" contrôle the LED state """
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
led.value( 1 ) # TURN OFF

def led_error( step ):
	global led
	t = time.time()
	while ( time.time()-t ) < ERROR_REBOOT_TIME:
		for i in range( 20 ):
			led.value(not(led.value()))
			time.sleep(0.100)
		led.value( 1 ) 
		time.sleep( 1 )
		for i in range( step ):
			led.value( 0 )
			time.sleep( 0.5 )
			led.value( 1 )
			time.sleep( 0.5 )
		time.sleep( 1 )
	reset()

if runapp.value() != 1:
	from sys import exit
	exit(0)

led.value( 0 ) 

# --- MAIN PROGRAM ---
from umqtt.simple import MQTTClient
try:
	q = MQTTClient( client_id = CLIENT_ID,
		server = MQTT_SERVER,
		user = MQTT_USER,
		password = MQTT_PSWD )
	sMac = hexlify( WLAN().config( 'mac' ) ).decode()
	q.set_last_will( topic="disconnect/%s" % CLIENT_ID , msg=sMac )
	if q.connect() != 0:
		led_error( step=1 )
except Exception as e:
	print( e )
	led_error( step=2 ) # check MQTT_SERVER, MQTT_USE- MQTT_PSWD

# Loading libraries
try:
	from ads1x15 import *
	from machine import Pin
except Exception as e:
	print( e )
	led_error( step=3 )

i2c = get_i2c()


try:
	adc = ADS1115( i2c=i2c, address=0x48, gain=0 )

	contact = Pin( CONTACT_PIN, Pin.IN, Pin.PULL_UP )
	last_contact_state = contact.value()
	last_ldr_state = ldr_to_state(
		adc_ldr   = adc.read( rate=0, channel1=1),
		adc_pivot = adc.read( rate=0, channel1=2) )
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
	#publish temperature every hour
	global q
	global adc
	valeur = adc.read( rate=0, channel1=0 )
	mvolts = valeur * 0.1875
	t = (mvolts - 500)/10
	t = "{0:.2f}".format(t)
	q.publish( "home/inside/balcony/temp", t )

def check_contact():
	""" publish magnetic contact state at every change """
	global q
	global last_contact_state
	if contact.value()==last_contact_state:
		return
	time.sleep( 0.100 )
	valeur = contact.value()
	if valeur != last_contact_state:
		q.publish( "home/inside/balcony/window",
			"OPEN" if valeur==1 else "CLOSED" )
		last_contact_state = valeur

def check_ldr():
	global q
	global adc
	global last_ldr_state
	ldr_state = ldr_to_state(
		adc_ldr = adc.read( rate=0, channel1=1),
		adc_pivot = adc.read( rate=0, channel1=2) )
	if ldr_state != last_ldr_state:
		q.publish( "home/inside/balcony/ldr", ldr_state )
		last_ldr_state = ldr_state

def heartbeat():
	time.sleep( 0.2 )


async def run_every( fn, min= 1, sec=None):
	""" Execute a function fn every min minutes or sec secondes"""
	global led
	wait_sec = sec if sec else min*60
	while True:
		led.value( 1 )
		try:
			fn()
		except Exception:
			print( "run_every catch exception for %s" % fn)
			raise 
		led.value( 0 ) 
		await asyncio.sleep( wait_sec )

async def run_app_exit():
	global runapp
	while runapp.value()==1:
		await asyncio.sleep( 10 )
	return

loop = asyncio.get_event_loop()
loop.create_task( run_every(capture_1h, min=60) )
loop.create_task( run_every(check_contact, sec=2 ) )
loop.create_task( run_every(check_ldr, sec=5) )
loop.create_task( run_every(heartbeat, sec=10) )
try:
	loop.run_until_complete( run_app_exit() )
except Exception as e :
	print( e )
	led_error( step=6 )

loop.close()
led.value( 1 )