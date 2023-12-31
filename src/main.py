import urequests
import machine
import time
import network
import sys
import sys
import os
from src.ota_updater import OTAUpdater
# Add the parent directory to sys.path
sys.path.append("..")
from CONFIG import WIFI_SSID, WIFI_PASSWORD
from CONFIG import INFLUXDB_URL, INFLUX_DB_TOKEN
from CONFIG import GITHUB_PROJECT_URL

otaUpdater = OTAUpdater(GITHUB_PROJECT_URL, github_src_dir='', module='', main_dir='src')
#otaUpdater = OTAUpdater(GITHUB_PROJECT_URL)


# Sensor reading
SENSOR_PIN = 26

# Calibration values
MIN_MOISTURE = 14500
MAX_MOISTURE = 44050

# LED Indication status
INDICATION_LED = machine.Pin("LED", machine.Pin.OUT)

def blink_toggle(timer):
    INDICATION_LED.toggle()

def blink_sec(sleep_time):
    INDICATION_LED.on()
    time.sleep(sleep_time)
    INDICATION_LED.off()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        timer = machine.Timer()
        timer.init(freq=10, mode=machine.Timer.PERIODIC, callback=blink_toggle)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            pass
        timer.deinit()
    print("WiFi SSID:", WIFI_SSID)
    print("Wi-Fi connected!")
    print("PICO'S IP:", wlan.ifconfig()[0])

def send_to_influxdb(measurement, fields, tags=None):
    line_protocol = measurement
    for tag, value in tags.items():
        line_protocol += f",{tag}={value}"
    line_protocol += " "
    line_protocol += ",".join([f"{field}={value}" for field, value in fields.items()])
    headers = {
        "Authorization": "Token " + INFLUX_DB_TOKEN
    }
    try:
        print(line_protocol)
        response = urequests.post(INFLUXDB_URL, data=line_protocol,headers=headers)
        print("Response code:", response.status_code)
        print("Data sent to InfluxDB. Response:", response.text)
    except Exception as e:
        print("Failed to send data to InfluxDB:", e)

def read_sensor_value():
    adc = machine.ADC(machine.Pin(SENSOR_PIN))
    sensor_value = adc.read_u16()
    print("ss: ", sensor_value)
    sensor_value = MIN_MOISTURE / (sensor_value) * 100

    return sensor_value

def analog_to_moisture_percentage():
    analog_reading = machine.ADC(machine.Pin(SENSOR_PIN)).read_u16()
    # Define the analog reading range (adjust based on your sensor's specifications)
    analog_min = 40000  # Assume maximum analog value (no moisture)
    analog_max = 14000  # Assume minimum analog value (high moisture)

    # Map the analog reading to a moisture percentage (adjust based on your sensor's calibration)
    moisture_min = 0  # Minimum moisture percentage
    moisture_max = 100  # Maximum moisture percentage

    # Calculate the moisture percentage based on the analog reading
    moisture_percentage = moisture_min + ((analog_reading - analog_min) / (analog_max - analog_min)) * (moisture_max - moisture_min)

    # Ensure the moisture percentage is within the valid range
    moisture_percentage = max(min(moisture_percentage, moisture_max), moisture_min)

    return moisture_percentage

def build_soil_moisture_message(sensor_value):
    return {
        "measurement": "soil_moisture",
        "fields": {
            "value": sensor_value
        },
        "tags": {
            "device": "raspberry_pico_w"
        }
    }
    

def main():
    INDICATION_LED.off()
    connect_wifi()
    print('---------------------')
    while True:
        blink_sec(0.5)
        #sensor_value = read_sensor_value()
        sensor_value = analog_to_moisture_percentage()
        print("Sensor Data " + str(sensor_value))
        
        # Prepare data to send to InfluxDB
        message = build_soil_moisture_message(sensor_value)
        send_to_influxdb(message["measurement"], message["fields"], message["tags"])
        
        time.sleep(3)
        update_avail = otaUpdater.check_for_update_to_install_during_next_reboot()
        if update_avail:
            machine.reset()
        else:
            print("not new version to update")

def start():
    main()


def boot():
    updated = otaUpdater.install_update_if_available_after_boot(WIFI_SSID, WIFI_PASSWORD)
    if (updated):
        machine.reset()
    
    update_avail = otaUpdater.check_for_update_to_install_during_next_reboot()
    if (update_avail):
        machine.reset()
    start()

boot()