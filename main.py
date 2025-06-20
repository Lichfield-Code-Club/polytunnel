import umqtt.robust as mqtt
import network
import json
import sys
import time
import urequests
import machine
import ntptime
import time

CONFIG_FILE = "config.json"
CACHE_FILE = "sensor_cache.json"
LOG_FILE = "runtime.log"

def log_event(message):
    """Append log entries to a file with a timestamp."""
    with open(LOG_FILE, "a") as f:  # "a" mode appends without overwriting
        timestamp = time.localtime()  # Use UTC or adjust for local time
        log_entry = "[{:04}-{:02}-{:02} {:02}:{:02}:{:02}] {}\n".format(
            timestamp[0], timestamp[1], timestamp[2], timestamp[3], timestamp[4], timestamp[5], message
        )
        f.write(log_entry)

def get_ip():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    return wlan.ifconfig()[0]  # Get device IP

def get_timestamp():
    """Returns current UTC timestamp in YYYY-MM-DDTHH:mm:SSZ format."""
    utc_now = time.gmtime()
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
        utc_now[0], utc_now[1], utc_now[2], utc_now[3], utc_now[4], utc_now[5]
    )

def get_readings(source):
  log_event("get_readings")
  sensor_data = {
    "temperature": 22.5,
    "humidity": 50,
    "pressure": 1013
  }
  payload = {
    "readings": sensor_data,
    "nickname": source,
    "model": f"{sys.implementation}",
    "timestamp": get_timestamp()
  }
  return payload

def load_local_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except OSError:
        return None

# Connect to Wi-Fi
def connect_wifi(config):
    log_event("connect_wifi")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(config["wifi_ssid"], config["wifi_pass"])
    for _ in range(10):  # Try for 10 seconds
        if wlan.isconnected():
            log_event(f"Connected to Wi-Fi: [{wlan.ifconfig()[0]}]")
            return True
        time.sleep(1)
    log_event("Wi-Fi unavailable")
    return False

# Save readings to local file if Wi-Fi is unavailable
def cache_readings():
    log_event("cache_readings")
    readings = get_readings("cached")
    try:
        with open(CACHE_FILE, "a") as f:
            f.write(json.dumps(readings) + "\n")
        log_event(f"Cached data: {readings}")
    except Exception as e:
        log_event(f"Error caching data: {e}")
        
def send_cached_data(config):
    log_event("send_cached_data")
    open(CACHE_FILE, "a").close()
    try:
        with open(CACHE_FILE, "r") as f:
            lines = f.readlines()
        if not lines:
            return

        client = mqtt.MQTTClient(
          client_id = config["mqtt_client_id"],
          server    = config["mqtt_broker"],
          user      = config["mqtt_user"],
          password  = config["mqtt_pass"]
        )

        log_event("SEND CACHE: connect")
        client.connect()
        for line in lines:
            client.publish(topic, line.strip())
        client.disconnect()

        # Clear cache after successful transmission
        open(CACHE_FILE, "w").close()
        log_event("Cached data sent and file cleared")
    except Exception as e:
        log_event(f"Error sending cached data: {e}")
        
# Publish data to MQTT broker
def publish_mqtt(config):
    log_event("publish_mqtt")
    log_event(config)
    topic = config["mqtt_topic"]
    log_event(f"Topic: {topic}")
    client = mqtt.MQTTClient(
        client_id = config["mqtt_client_id"],
        server    = config["mqtt_broker"],
        user      = config["mqtt_user"],
        password  = config["mqtt_pass"]
    )

    log_event("PUBLISH client connect")
    client.connect()
    log_event("Get Readings")
    payload = get_readings("latest")
    log_event("PAYLOAD")
    log_event(payload)
    client.publish(topic, json.dumps(payload))
    client.disconnect()
    log_event(f"Data published: {payload}")

def sync_time():
    """Attempts to sync time until it's updated."""
    while True:
        try:
            print("Trying to sync time...")
            ntptime.settime()  # Fetch time from NTP server
            current_time = time.localtime()
            if current_time[0] > 2000:  # Ensure the year is reasonable (not default 2000)
                print("Time synced successfully:", time.localtime())
                break  # Exit loop once time is set
        except Exception as e:
            print("Failed to sync time:", e)

        time.sleep(5)  # Retry after 5 seconds if sync fails

# Main loop
config = load_local_config()
if config:
    connected = connect_wifi(config)
    if connected:
        sync_time()
        while True:
            send_cached_data(config)
            publish_mqtt(config)
            time.sleep(300)
    else:
        log_event(f"Connect to wifi failed: {connected}")
else:
    log_event("No valid configuration found.")
