import time
from network import WLAN
from umqtt.simple import MQTTClient
from ubinascii import hexlify
import sys
CLIENT_ID="demo-sub"
MQTT_SERVER="127.0.0.1"
MQTT_USER="pusr103"
MQTT_PSWD="2105217"

led=Pin(12,Pin.OUT)
led.value(0)

q=MQTTClient(client_id=CLIENT_ID,server=MQTT_SERVER,user=MQTT_USER,password=MQTT_PSWD)
#we have to define a callback function for q
def callback(topic,msg):
    t=topic.decode('utf8')
    m=msg.decode('utf8')
    print(f"topic is {t} message is {m}" )
    if t=="cmd/led":
        led.value(1 if m=="off" else 0) #turn off lef

q.set_callback(callback) #

#register in the network topic
sMac=hexlify(WLAN().config('mac')).decode()
q.publish(f"connect/{CLIENT_ID}",sMac)

q.subscribe("demo/#")
q.subscribe("cmd/led")

while True:
    q.wait_msg() #anytime a message related to subs comes, the callback function is launched
    #q.check_msg() #non-blocking
q.disconnect()