import utime
import time
import machine
from tx import TX
from tx.get_pin import pin

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
    
    #Washer door mag sensor
washerDoor = machine.Pin(16, machine.Pin.IN)
TX_POWER = machine.Pin(15, machine.Pin.OUT) #Power for radio transmit to ceiling fan
TX_POWER.value(1)  # Set TX_POWER pin to HIGH to provide 3.3V power
transmit = TX(pin(), 'washRoomCeilFan') #currently pin 14 (set in tx/get_pin.py)
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
last_closed_door_change = 0
door_closed_threshold = 30#0 #5 minutes
last_opened_door_change = 0
door_opened_threshold = 120#0 # 20 minutes
fan_stage = 1
while True:
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
    utime.sleep(5)

