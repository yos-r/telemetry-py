# ⚡Telemetry-py
Web application for tracking telemetric data (light, temperature, relative humidity, activity)in a household and displaying them in a dashboard with time-series databases.

Tools and technologies: Raspberry Pi,MQTT broker, RShell for pushing python scripts onto RaspberryPi, SQlite, Flask, Jinja.

## ⚙️ Hardware:
- Adafruit Feather HUZZAH with ESP8266 (wi-fi microncontroller for running Micropython)
- BME280 for measuring pressure, humidity and temperature
- TSL2561 for measuring light
- ADS1115 and TMP36 for analog temperature reading 
- Photoresistance for light detection (on or off)
- PIR for movement detection
- Magnetic contact for detecting if a door/window is opened


## 🦟 MQTT broker:
MQTT is a communication protocol for low-bandwidth networks. It uses a publication/subscription mechanism.
The sensors publish messages to specific topics. 
The applications subscribe to the topics.

A MQTT broker is a software enabling the exchange of information between different actors with MQTT protocol.
It handles connections, user accounts and topics.
Upon receiving messages from publishers, it propagates the messages to subscribers.

### Installing MQTT

```bash
$ sudo apt-get install mosquitto mosquitto-clients
```
````python
$ sudo pip install paho_mqtt
````
### Subscription and Publishing demo
The topics we'll use are the following
````
connect/<MAC address of client> 
home/outside/shed/pathm (atmospheric pressure)
home/outside/shed/lux 
home/outisde/shed/temp
home/outside/shed/hrel

home/inside/livingroom/temp
home/inside/livingroom/pir

home/inside/balcony/temp
home/inside/balcony/ldr
home/inside/balcony/window




````
A client subscribes to the topic ````home/inside/livingroom/temp ```` 
````bash
# 192.168.1.210 is the broker's address
$ mosquitto_sub -h 192.168.1.210 -t "home/inside/livingroom/temp" -v -u pusr103 -P 21052017
````

The temperature sensors connected to the MQTT broker will emit the messages containing values by publishing them as follows

```bash
$ mosquitto_pub -h 192.168.1.210 -t "home/inside/livingroom/temp" -m "28" -u pusr103 -P 21052017
````

Password and username (pusr103) are configured with the file  ```` passwd  ````

````bash
$ sudo mosquitto_passwd -c /etc/mosquitto/passwd pusr103 
```` 
Then configure ```` /etc/mosquitto/mosquitto.conf```` by adding these lines
````
allow_anonymous false
password_file /etc/mosquitto/passwd
````


