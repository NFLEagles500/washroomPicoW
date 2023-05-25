# washroomPicoW
micropython code to control the light and ceiling fan in Wash room

Using Thonny for the Raspberry Pico W
Be sure to install the following packages:
  microdot (Flask for Micropython)
  picozero (not used in this case, but goes with Pico W)
  utemplate (used for html pages)
  
  create a secrets.py file to store secrets (passwords, etc)
  
  In my case I'm using an RF transmitter module to interact with the Ceiling Fan)
  I have a AM312 PIR sensor with a 10uf and a 1uf capacitors between Data and Ground pin to improve reliability
  Using a Reed switch to detect whether the washer door is open or closed.
  Using a photoresistor to determine if the toggle command has turned the light on or off.
  
