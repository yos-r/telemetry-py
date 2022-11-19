import time
from network import WLAN
from umqtt.simple import MQTTClient
from ubinascii import hexlify
import sys
CLIENT_ID="demo-pub"
MQTT_SERVER="127.0.0.1"
MQTT_USER="pusr103"
MQTT_PSWD="2105217"

q=MQTTClient(client_id=CLIENT_ID,server=MQTT_SERVER,user=MQTT_USER,password=MQTT_PSWD)

sMac=hexlify(WLAN().config('mac')).decode()
q.publish(f"connect/{CLIENT_ID}",sMac)

for i in range(10):
    print(f"pub {i} ")
    q.publish("demo/counter",str(i))
    time.sleep(1)

q.disconnect()