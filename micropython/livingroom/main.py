from machine import Pin, I2C, reset
import time
from ubinascii import hexlify
from network import WLAN
import os
"""
PIR, TMP36 (analog reading) and ADS1115
"""

CLIENT_ID = 'livingroom'
MQTT_SERVER = "192.168.1.210"
MQTT_USER = 'pusr103'
MQTT_PSWD = '21052017'

ERROR_REBOOT_TIME = 3600 # 1 h = 3600 sec

# PIR - ESP32 pin 27, ESP8266 pin 13.
PIR_PIN = 27 if os.uname().nodename == 'esp32' else 13  
PIR_RETRIGGER_TIME = 15 * 60 # 15 min
last_pir_time = 0
last_pir_msg  = "NONE"
last_pir_msg_time = 0
fire_pir_alert = False

class LED:
	""" Abstraction LED Utilisateur pour ESP32 et ESP8266 """
	# User LED set ESP32 is on #13 with direct logic,
	# ESP8266 on pin #0 with reverse Logic
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
led.value( 1 ) 

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

# --- Main program ---
from umqtt.simple import MQTTClient
try:
	q = MQTTClient( client_id = CLIENT_ID, server = MQTT_SERVER, user = MQTT_USER, password = MQTT_PSWD )
	sMac = hexlify( WLAN().config( 'mac' ) ).decode()
	q.set_last_will( topic="disconnect/%s" % CLIENT_ID , msg=sMac )
	if q.connect() != 0:
		led_error( step=1 )
except Exception as e:
	print( e )
	led_error( step=2 )

# loading libraries
try:
	from ads1x15 import *
	from machine import Pin
except Exception as e:
	print( e )
	led_error( step=3 )

i2c = get_i2c()

#PIR sensor
def pir_activated( p ):
	# print( 'pir activated @ %s' % time.time() )
	global last_pir_time, last_pir_msg, fire_pir_alert
	last_pir_time = time.time()
	fire_pir_alert = (last_pir_msg == "NONE")

# create sensors
try:
	adc = ADS1115( i2c=i2c, address=0x48, gain=0 )
	pir_sensor = Pin( PIR_PIN, Pin.IN )
	pir_sensor.irq( trigger=Pin.IRQ_RISING, handler=pir_activated )
except Exception as e:
	print( e )
	led_error( step=4 )

# announce connection of object to broker
try:
	sMac = hexlify( WLAN().config( 'mac' ) ).decode()
	q.publish( "connect/%s" % CLIENT_ID , sMac )
except Exception as e:
	print( e )
	led_error( step=5 )

import uasyncio as asyncio

def capture_1h():
	""" Capture data and publish messages every hour """
	global q
	global adc
	valeur = adc.read( rate=0, channel1=0 )
	mvolts = valeur * 0.1875
	t = (mvolts - 500)/10
	t = "{0:.2f}".format(t)  
	q.publish( "home/inside/livingroom/temp", t )

def heartbeat():
	time.sleep( 0.2 )

def pir_alert():
	global fire_pir_alert, last_pir_msg, last_pir_msg_time
	if fire_pir_alert:
		fire_pir_alert=False 
		last_pir_msg = "MOUV"
		last_pir_msg_time = time.time()
		q.publish( "home/inside/livingroom/pir", last_pir_msg )

def pir_update():
	""" Regular update of topic """
	global last_pir_msg, last_pir_msg_time
	if (time.time() - last_pir_msg_time) < PIR_RETRIGGER_TIME:
		return

	
	if (time.time() - last_pir_time) < PIR_RETRIGGER_TIME:
		msg = "MOUV"
	else:
		msg = "NONE"

	
	if msg == "NONE" == last_pir_msg:
		return

	#publishing messages
	last_pir_msg = msg
	last_pir_msg_time = time.time()
	q.publish( "maison/rez/salon/pir", last_pir_msg )


async def run_every( fn, min= 1, sec=None):
	global led
	wait_sec = sec if sec else min*60
	while True:
		led.value( 1 ) 
		try:
			fn()
		except Exception:
			print( "run_every catch exception for %s" % fn)
			raise 
		led.value( 0 ) #light LED
		await asyncio.sleep( wait_sec )

async def run_app_exit():
	global runapp
	while runapp.value()==1:
		await asyncio.sleep( 10 )
	return

loop = asyncio.get_event_loop()
loop.create_task( run_every(capture_1h, min=60) )
loop.create_task( run_every(pir_alert, sec=10) )
loop.create_task( run_every(pir_update, min=5))
loop.create_task( run_every(heartbeat, sec=10) )
try:
	loop.run_until_complete( run_app_exit() )
except Exception as e :
	print( e )
	led_error( step=6 )

pir_sensor = Pin( PIR_PIN, Pin.IN )

loop.close()
led.value( 1 ) # turn off LED
