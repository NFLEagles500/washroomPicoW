
import network
import _thread
from microdot import Microdot, Response
from microdot_utemplate import render_template
import utime
from tx import TX
from tx.get_pin import pin
from time import sleep
import time
#from picozero import pico_temp_sensor, pico_led
import machine
import urequests
import ujson
import ntptime
import secrets

# Pin definitions
    #PIR Pins
DATA_PIN = machine.Pin(2, machine.Pin.IN)
PIR_POWER = machine.Pin(3, machine.Pin.OUT) #Power for motion sensor
PIR_POWER.value(1)  # Set PIR_POWER pin to HIGH to provide 3.3V power
    #Light sensor
ADC_PIN = machine.Pin(26)
    #Radio Transmitter Pins
TX_POWER = machine.Pin(15, machine.Pin.OUT) #Power for radio transmit to ceiling fan
TX_POWER.value(1)  # Set TX_POWER pin to HIGH to provide 3.3V power
transmit = TX(pin(), 'washRoomCeilFan') #currently pin 14 (set in tx/get_pin.py)
    #Washer door mag sensor
washerDoor = machine.Pin(16, machine.Pin.IN)

#variables
url = 'http://192.168.86.33:5000/api'
rtc = machine.RTC()

# Configure ADC
adc = machine.ADC(26)  # Create ADC object on GP26 (ADC0)


#Join to existing wifi
ssid = secrets.SSID
passwd = secrets.passwd
run_threads = True
months = {
        1 : "Jan",
        2 : "Feb",
        3 : "Mar",
        4 : "Apr",
        5 : "May",
        6 : "Jun",
        7 : "Jul",
        8 : "Aug",
        9 : "Sep",
        10 : "Oct",
        11 : "Nov",
        12 : "Dec"
        }
#Create this as an Access Point
#ap = network.WLAN(network.AP_IF)
#ap.config(ssid='washFan', password='f82make')
#wait_counter = 0
#while ap.active() == False:
#    print(f"waiting {wait_counter}")
#    sleep(0.5)
#    pass
def connect():
    #Connect to WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.config(hostname='picowashroom')
    wlan.active(True)
    wlan.connect(ssid, passwd)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        sleep(1)
    ip = wlan.ifconfig()[0]
    print(f'{network.hostname()} is connected on {ip}')
    return ip

def fanOn():
    test = f'{time.localtime()[0]}/{months[time.localtime()[1]]}/{time.localtime()[2]:02d} {time.localtime()[3]:02d}:{time.localtime()[4]:02d}:{time.localtime()[5]:02d} Fan On'
    with open('washroom.log', 'a') as fw:
        fw.write(test)
        fw.write('\n')
    transmit('fanSpd3')
    utime.sleep(0.5)
    transmit('fan8hr')
    utime.sleep(0.5)

def fanOff():
    test = f'{time.localtime()[0]}/{months[time.localtime()[1]]}/{time.localtime()[2]:02d} {time.localtime()[3]:02d}:{time.localtime()[4]:02d}:{time.localtime()[5]:02d} Fan Off'
    with open('washroom.log', 'a') as fw:
        fw.write(test)
        fw.write('\n')
    transmit('fanSpd3')
    utime.sleep(0.5)
    transmit('fanOnOff')
    utime.sleep(0.5)

def lightToggle():
    transmit('lightTogg')
    utime.sleep(0.2)

def core1():
    #variables
    global months
    global rtc
    global run_threads
    led_on = False
    last_data_pin_change = 0
    countdown_duration = 30
    last_closed_door_change = 0
    door_closed_threshold = 300 #5 minutes
    last_opened_door_change = 0
    door_opened_threshold = 1200 # 20 minutes
    fan_stage = 1 #1 will mean nothing, 2 will mean 5 minutes door closed counting, 3 will mean waiting for door to open, 4 for 20 minutes open door countdown
    #Toggle light to initiate whether it is on or off
    before_adc_value = adc.read_u16()
    lightToggle()
    #utime.sleep(0.2)
    after_adc_value = adc.read_u16()
    print(f"Before: {before_adc_value}, After: {after_adc_value}")
    if before_adc_value > after_adc_value:
        lightToggle()
        #utime.sleep(0.2)
    print('Light initiated...')
    doorCheckCount = 25
    # Main loop
    while True:
        if not run_threads:
            print('run thread interrupt')
            break
        if doorCheckCount == 25:
            if washerDoor.value() == 1:
                last_opened_door_change = 0
                if fan_stage == 1:
                    print('Door closed, starting closed timer')
                    last_closed_door_change = utime.time()
                    fan_stage = 2
                elif fan_stage == 2:
                    if (utime.time() - last_closed_door_change) >= door_closed_threshold:
                        print('Door closed for over 5 minutes, waiting for door open')
                        fanOff()
                        last_closed_door_change = 0
                        fan_stage = 3
                    else:
                        timer = door_closed_threshold - (utime.time() - last_closed_door_change)
                        print(f'Door closed countdown: {timer}')
                elif fan_stage == 4:
                    last_opened_door_change = 0
                    fan_stage = 3
                    print('Door was closed before 20 minutes of being open, resetting')
            if washerDoor.value() == 0:
                last_closed_door_change = 0
                if fan_stage == 2:
                    #this means the door was NOT closed for 5+ minutes, reset it
                    fan_stage = 1
                    print('Door opened before closed threshold, resetting')
                elif fan_stage == 3:
                    last_opened_door_change = utime.time()
                    fan_stage = 4
                elif fan_stage == 4:
                    if (utime.time() - last_opened_door_change) >= door_opened_threshold:
                        fanOn()
                        last_opened_door_change = 0
                        fan_stage = 1 #Reset fan stage once you start cieling fan
                    else:
                        timer = door_opened_threshold - (utime.time() - last_opened_door_change)
                        print(f'Door opened countdown: {timer}')
            doorCheckCount = 1
        # Read data from DATA_PIN
        data = DATA_PIN.value()
        #print(adc.read_u16())
        if data == 1:
            if not led_on:
                test = f'{time.localtime()[0]}/{months[time.localtime()[1]]}/{time.localtime()[2]:02d} {time.localtime()[3]:02d}:{time.localtime()[4]:02d}:{time.localtime()[5]:02d} Light On'
                led_on = True
                lightToggle()
                #utime.sleep(0.2)
                with open('washroom.log', 'a') as fw:
                    fw.write(test)
                    fw.write('\n')
                print("LED turned on.")
            #led_on = True
            #LED_PIN.value(1)
            last_data_pin_change = utime.time()
            
        else:
            if led_on and (utime.time() - last_data_pin_change) >= countdown_duration:
                led_on = False
                lightToggle()
                #utime.sleep(0.2)
                print("LED turned off.")
            elif led_on:
                print(countdown_duration - (utime.time() - last_data_pin_change))

        # Read the ADC value
        #adc_value = adc.read_u16()

        doorCheckCount += 1
        utime.sleep(0.2)  # Delay for 0.1 seconds


def webpage(temperature, state):
    #Template HTML
    html = f"""
            <!DOCTYPE html>
            <html>
            <form action="./lighton">
            <input type="submit" value="Light on" />
            </form>
            <form action="./lightoff">
            <input type="submit" value="Light off" />
            </form>
            <p>LED is {state}</p>
            <p>Temperature is {temperature}</p>
            </body>
            </html>
            """
    return str(html)

app = Microdot()
Response.default_content_type = 'text/html'

@app.route('/')
def index(request):
    washLogs = []
    with open('washroom.log','r') as f:
        examp = []
        for line in f.readlines():
            examp.append(line)
        firstEntry = len(examp)
        if len(examp) > 50:
            lastEntry = len(examp) - 50
        else:
            lastEntry = 0
        #final = []
        while lastEntry <= firstEntry:
            washLogs.append(examp[firstEntry-1])
            firstEntry = firstEntry - 1
    return render_template('home.html', logs=washLogs)

@app.route('/orders', methods=['GET'])
def index(req):
    name = "donsky"
    orders = ["soap", "shampoo", "powder"]

    return render_template('orders.html', name=name, orders=orders)

@app.route("/api", methods=["POST", "GET"])
def washRoomLog(request):
    print(request)
    if request.method == "POST":
        if request.json['logEntry']:
            print(request.json['logEntry'])
            return 'done'
        else:
            return '404'

try:
    connect()
    ntptime.settime()
    print(time.localtime())
except KeyboardInterrupt:
    run_threads = False

try:    
    second_thread = _thread.start_new_thread(core1, ())
except KeyboardInterrupt:
    run_threads = False
if __name__ == '__main__':
    try:
        app.run(port=80)
    except KeyboardInterrupt:
        run_threads = False
#except KeyboardInterrupt:
#    machine.reset()

