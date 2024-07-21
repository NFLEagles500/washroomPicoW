#from lcd1602 import LCD
import network
import _thread
from microdot import Microdot, Response
from microdot_utemplate import render_template
import utime
from tx import TX
from tx.get_pin import pin
from time import sleep
import time
import machine
import urequests
import ujson
import ntptime
import envSecrets
import uos

#Interruptable main.py
sleep(5)

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
    #Threads kill pin.  Pull this circuit if you can't connect since it starts main.py
#threads_pin = machine.Pin(19, machine.Pin.IN)

#variables
url = 'http://192.168.86.33:5000/api'
rtc = machine.RTC()

# Configure ADC
adc = machine.ADC(26)  # Create ADC object on GP26 (ADC0)


#Join to existing wifi
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

#Setting defaults depending on which pico
devCheck = uos.uname()
if 'Pico W' in devCheck.machine:
    dev = 'picow'
    onboardled = machine.Pin('LED', machine.Pin.OUT)
else:
    dev = 'pico'
    onboardled = machine.Pin(25, machine.Pin.OUT)
onboardled.value(0)

def update_main_script():
    response = urequests.get(envSecrets.github_url)
    new_code = response.text
    response.close()

    # Check if the new code is different from the existing code
    if new_code != open('main.py').read():
        print('Github code is different, updating...')
        # Save the new main.py file
        with open('main.py', 'w') as f:
            f.write(new_code)

        # Reset the Pico to apply the updated main.py
        machine.reset()

def appLog(stringOfData):
    with open('log.txt','a') as file:
        if type(stringOfData) == str:
            file.write(f"{utcToLocal('datetime')} {stringOfData}\n")
            print(f"{utcToLocal('datetime')} {stringOfData}")
        else:
            file.write(f"{utcToLocal('datetime')} --- Traceback begin ---\n")
            usys.print_exception(stringOfData,file)
            file.write(f"{utcToLocal('datetime')} --- Traceback end ---\n")

def logCleanup():
    with open('washroom.log','r') as readingFile:
        entries = []
        for line in readingFile:
            if line != '\n':
                entries.append(line)
    if len(entries) > 29:
        lastEntry = len(entries)
        startEntry = lastEntry - 29
        entries = entries[startEntry:lastEntry]
    print(f"Entries: {entries}")
    
    with open('washroom.log','w') as writeFile:
        for line in entries:
            writeFile.write(line)
    appLog('Cleaned up washroom.log')


def connect():
    #Connect to WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.disconnect()
    wlan.config(hostname='picotest')
    sleep(1)
    wlan.active(True)
    wlan.connect(envSecrets.ssid, envSecrets.wifipsw)
    iter = 1
    while wlan.ifconfig()[0] == '0.0.0.0':
        print(f'Not Connected...{iter}')
        iter += 1
        sleep(1)
        if iter == 10:
            wlan.connect(envSecrets.ssid, envSecrets.wifipsw)
            iter = 1
    ip = wlan.ifconfig()[0]
    print(f'{network.hostname()} is connected on {ip}')

def fanOn():
    test = f'{utcToLocal('datetime')} Fan On'
    with open('washroom.log', 'a') as fw:
        fw.write(test)
        fw.write('\n')
    transmit('fanSpd3')
    utime.sleep(0.5)
    transmit('fan8hr')
    utime.sleep(0.5)

def fanOff():
    test = f'{utcToLocal('datetime')} Fan Off'
    with open('washroom.log', 'a') as fw:
        fw.write(test)
        fw.write('\n')
    transmit('fanSpd3')
    utime.sleep(0.5)
    transmit('fanOnOff')
    utime.sleep(0.5)

def lightToggle(state):
    before_adc_value = adc.read_u16()
    transmit('lightTogg')
    utime.sleep(0.7)
    after_adc_value = adc.read_u16()
    print(f"Before: {before_adc_value}, After: {after_adc_value}")
    if before_adc_value > after_adc_value and state == 'Off':
        print('transmitting again to correct...')
        transmit('lightTogg')
        utime.sleep(0.2)
    elif after_adc_value > before_adc_value and state == 'On':
        print('transmitting again to correct...')
        transmit('lightTogg')
        utime.sleep(0.2)
    

def utcToLocal(type):
    global localUtcOffset
    global months
    localTime = time.localtime(time.time() + localUtcOffset)
    print(localTime[0])
    if type == 'time':
        return f'{localTime[3]:02d}:{localTime[4]:02d}:{localTime[5]:02d}'
    elif type == 'date':
        return f'{localTime[0]}/{months[localTime[1]]}/{localTime[2]:02d}'
    else:
        return f'{localTime[0]}/{months[localTime[1]]}/{localTime[2]:02d} {localTime[3]:02d}:{localTime[4]:02d}:{localTime[5]:02d}'

def core1():
    #variables
    global months
    global rtc
    global run_threads
    #global threads_pin
    led_on = False
    last_data_pin_change = 0
    countdown_duration = 30
    last_closed_door_change = 0
    door_closed_threshold = 300 #5 minutes
    last_opened_door_change = 0
    door_opened_threshold = 1200 # 20 minutes
    fan_stage = 1 #1 will mean nothing, 2 will mean 5 minutes door closed counting, 3 will mean waiting for door to open, 4 for 20 minutes open door countdown
    #Toggle light to initiate whether it is on or off
    #before_adc_value = adc.read_u16()
    lightToggle('Off')
    #utime.sleep(0.2)
    #after_adc_value = adc.read_u16()
    #print(f"Before: {before_adc_value}, After: {after_adc_value}")
    #if before_adc_value > after_adc_value:
    #    lightToggle()
        #utime.sleep(0.2)
    print('Light initiated...')
    doorCheckCount = 25
    # Main loop
    while True:#threads_pin.value() == 1:
    #if not run_threads:
    #    print('run thread interrupt')
    #    break
        if doorCheckCount == 25:
            #print(f'Washer door is {washerDoor.value()}')
            if washerDoor.value() == 1:
                last_opened_door_change = 0
                if fan_stage == 1:
                    print('Door closed, starting closed timer')
                    last_closed_door_change = utime.time()
                    fan_stage = 2
                elif fan_stage == 2:
                    if (utime.time() - last_closed_door_change) >= door_closed_threshold:
                        #print('Door closed for over 5 minutes, waiting for door open')
                        fanOff()
                        last_closed_door_change = 0
                        fan_stage = 3
                    else:
                        timer = door_closed_threshold - (utime.time() - last_closed_door_change)
                        #print(f'Door closed countdown: {timer}')
                elif fan_stage == 4:
                    last_opened_door_change = 0
                    fan_stage = 3
                    #print('Door was closed before 20 minutes of being open, resetting')
            if washerDoor.value() == 0:
                last_closed_door_change = 0
                if fan_stage == 2:
                    #this means the door was NOT closed for 5+ minutes, reset it
                    fan_stage = 1
                    #print('Door opened before closed threshold, resetting')
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
                        #print(f'Door opened countdown: {timer}')
            doorCheckCount = 1
        # Read data from DATA_PIN
        data = DATA_PIN.value()
        #print(data)
        #print(adc.read_u16())
        if data == 1:
            if not led_on:
                #test = f'{utcToLocal('datetime')} Light On'
                led_on = True
                lightToggle('On')
                #utime.sleep(0.2)
                #with open('washroom.log', 'a') as fw:
                #    fw.write(test)
                #    fw.write('\n')
                print("Light turned on.")
            #led_on = True
            #LED_PIN.value(1)
            last_data_pin_change = utime.time()
            
        else:
            if led_on and (utime.time() - last_data_pin_change) >= countdown_duration:
                led_on = False
                lightToggle('Off')
                #utime.sleep(0.2)
                print("Light turned off.")
            #elif led_on:
            #    print(countdown_duration - (utime.time() - last_data_pin_change))

        # Read the ADC value
        #adc_value = adc.read_u16()

        doorCheckCount += 1
        if utime.localtime()[3] == 2 and utime.localtime()[4] == 0 and utime.localtime()[5] == 0:
            logCleanup()
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


@app.route("/api", methods=["POST", "GET"])
def washRoomLog(request):
    print(request)
    if request.method == "POST":
        if request.json['logEntry']:
            print(request.json['logEntry'])
            return 'done'
        else:
            return '404'

@app.route('/shutdown')
def shutdown(request):
    request.app.shutdown()
    return 'The server is shutting down...'
'''
try:
    #connect()
    onboardled.value(1)
    sleep(2)
    onboardled.value(0)
    #update_main_script()
    while True:
        try:
            ntptime.settime()
            print('ntp success')
            onboardled.value(1)
            sleep(1)
            onboardled.value(0)
            break
        except:
            print('ntp fail')
            sleep(1)
            pass
    response = urequests.get('https://timeapi.io/api/TimeZone/zone?timeZone=America/Denver')
    localUtcOffset = response.json()['currentUtcOffset']['seconds']
    logCleanup()
except KeyboardInterrupt:
    run_threads = False
'''
try:    
    second_thread = _thread.start_new_thread(core1, ())
except KeyboardInterrupt:
    run_threads = False
if __name__ == '__main__':
    try:
        app.run(port=80)
    except KeyboardInterrupt:
        run_threads = False


