## ESP8266
We can attach sensors to an ESP8266 microcontroller to collect data.
It has superior flash memory, faster clock and offers wi-fi support.

In this project we will use the Feather Huzzah ESP8266 platform for running MicroPython firmware on ESP8266 objects.

   -  install ````esptool```` 
- identify the peripheral on raspberry pi  ex: ````/dev/ttyUSB0````
- install micropython on raspberry pi by downloading binary in ````/tmp/upy````
`````
$ wget https://micropython.org/resources/firmware/esp8266-1m-20220618-v1.19.1.bin
`````
then clear flash memory and install micropython firmware (binary) on the ESP8266 microcontroller 
 ```` bash
 #clear flash memory
 $ esptool.py --port /dev/ttyUSB0 erase_flash 
 $ esptool.py --port /dev/ttyUSB0 --baud 115200 write_flash
 $ --flash_size=detect -fm dio 0 esp8266-1m-20220618-v1.19.1.bin
````
   
## REPL Micropython session via serial connection
````bash
$ sudo apt-get install picocom
$ sudo picocom /dev/ttyUSB0 -b115200
````
## RShell via serial connection
For running linux shell commands and handling files we use RShell.
````bash
$ sudo pip3 install rshell
$ rshell --port /dev/ttyUSB0 --baud 115200 --buffer-size 128 --editor nano
````
We get this interface where we can execute linux commands, create files etc..
```` bash
home/pi > !touch test.py # write some test code
home/pi > !cat test.py
home/pi > repl # we can launch repl from inside an rshell session
````
## Booting up Micropython
The file ````boot.py```` is the first file read. 
It enables STA mode, permitting an ESP8266 module to connect to a Wi-fi network and other ESP8266 components to publish messages to a MQTT server.

## General stucture of an ESP8266 object
Each object needs specific libraries that will be provided by a ````bootstrap.sh```` file. \
The ````main.py```` file defines:
- MQTT connection parameters to define the MQTT client
- A  ```Led ``` class and ```led_error``` function for the main problems occuring when working with an ESP8266 object.
(ex: invalid connection to MQTT broker, error with importing libraries, error while publishing to topic etc..)
- A Runapp object for conditional boot
- An I2C object
- Objects for the different sensors (ex: TSL2561 )

````main.py```` also publishes the client's MAC adress to the topic ````connect/<client_id>````, publishes retrieved data from the ESP8266 objects to the right topics.

We use ````asyncio ````library to run Python coroutines concurrently and have full control over their execution.





