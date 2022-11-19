"""""
best case scenario: no infinite loops, rshell working 
if infinite loop happens: need to reflash! 
"""
WIFI_SSID="HexaByteADD08" 
WIFI_PASSWORD="secret"
""""
    activate STA mode 
"""
def sta_connect():
    import network
    wlan=network.WLAN(network.STA_IF)
    wlan.active(True) #STA activation (instead of access point)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID,WIFI_PASSWORD)
        while not wlan.isconnected(): #try timeout?
            pass

def sta_connect_timeout():
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        # connecting to network...
        wlan.connect( WIFI_SSID, WIFI_PASSWORD )
        import time
        ctime = time.time()
        while not wlan.isconnected():
            if time.time()-ctime > 40:
                print( 'WLAN timeout!')
                break
            time.sleep( 0.5 )
#conditional boot with RunApp Interrupter
def sta_connect_runapp(timeout = None, disable_ap = False ):
    import network, time
    from machine import Pin
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    ##   
    # deactivate boot.py and main.py      
    #       ##
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID,WIFI_PASSWORD)
        runapp = Pin( 12,  Pin.IN, Pin.PULL_UP)
        ## read state at pin 12: 0 or 1
        if runapp.value() == 0:
            print( "WLAN: no wait!")
        else:
            ctime = time.time()
            while not wlan.isconnected():
                if timeout and ((time.time()-ctime)>timeout):
                    print( "WLAN: timeout!" )
                    break
                else:
                    # print(".")
                    time.sleep( 0.500 )
    if wlan.isconnected() and disable_ap:
        ap=network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)
            print("AP disabled")

""""
    connect 
"""
sta_connect()
if sta_connect_runapp(disable_ap=True,timeout=0):
    print("connected to WLAN")
""""
    garbage collector
"""
import gc
gc.collect()

