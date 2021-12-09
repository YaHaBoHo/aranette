import utime
import machine
from network import WLAN
import lib.urequests as requests
from lib.ssd1306 import SSD1306, OledError
from lib.mqtt import MQTTClient, MQTTError
from lib.common import hash_sha256, time_of_day


CFG_SWITCH_BOUNCE = 150


class Aranette():

    def __init__(self,
                 wlan_ssid, wlan_password,
                 aranet_api, aranet_username, aranet_password, aranet_sensor,
                 mqtt_host, mqtt_user, mqtt_key, mqtt_topic,
                 oled_sda="P9", oled_scl="P10", oled_switch="P11",
                 interval=600, auto_reboot=1800, mqtt_port=1883):
        # OLED
        self.oled_sda = oled_sda
        self.oled_scl = oled_scl
        self._oled = self.get_oled()
        self._oled_buffer = list()
        self._oled_active = True
        self._oled_switch = machine.Pin(oled_switch, mode=machine.Pin.IN, pull=machine.Pin.PULL_DOWN)
        self._oled_switch.callback(machine.Pin.IRQ_FALLING, handler=self.toggle_oled)
        self._oled_switch_ticker = 0
        self.write_oled("Boot...")
        # WLAN
        self.write_oled("WiFi...")
        self.wlan_ssid = str(wlan_ssid)
        self.wlan_password = str(wlan_password)
        self._wlan = self.get_wlan()
        # NTP
        self.write_oled("NTP...")
        machine.RTC().ntp_sync("pool.ntp.org")
        # MQTT
        self.write_oled("MQTT...")
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_key = mqtt_key
        self.mqtt_topic = mqtt_topic
        self._mqtt = self.get_mqtt()
        self._last_published = 0
        # Aranet
        self.write_oled("Aranet...")
        self.aranet_api = str(aranet_api)
        self.aranet_username = str(aranet_username)
        self.aranet_password = str(aranet_password)
        self.aranet_sensor = str(aranet_sensor)
        self._last_measured = 0
        self._last_polled = 0
        self._next_poll = 0
        # Internals
        self.interval = int(interval)
        self.auto_reboot = int(auto_reboot)
        self._running = False

    def get_oled(self):
        oled = SSD1306.otronics(i2c_sda=self.oled_sda, i2c_scl=self.oled_scl)
        try:
            oled.initialize()
        except OledError as err:
            print("Could not initialize OLED : {}".format(err))
        return oled

    def get_wlan(self):
        wlan = WLAN(mode=WLAN.STA)
        wlan.connect(ssid=self.wlan_ssid, auth=(WLAN.WPA2, self.wlan_password))
        while not wlan.isconnected():
            machine.idle()
        return wlan

    def get_mqtt(self):
        mqtt = MQTTClient(
            client_id="aranette",
            server=self.mqtt_host, port=self.mqtt_port,
            user=self.mqtt_user, password=self.mqtt_key)
        mqtt.connect()
        return mqtt

    def hash_password(self, salt_perm, salt_ot):
        pass_hash = hash_sha256(text=self.aranet_password, rounds=5)
        perm_hash = hash_sha256(text=pass_hash + salt_perm)
        return hash_sha256(text=salt_ot + perm_hash)

    def fetch(self, payload):
        return requests.post(self.aranet_api, json=payload).json()

    def poll(self):
        # Fetch salts from API
        preauth = self.fetch(payload={"auth": {"username": self.aranet_username}})
        # Prepare payload
        payload = {
            "auth": {
                "username": self.aranet_username,
                "hash": self.hash_password(salt_perm=preauth['auth']['permasalt'], salt_ot=preauth['auth']['salt'])},
            "currData": 1}
        # Fetch data from API
        data = self.fetch(payload)
        # Extract sensor data
        for k, v in data['currData'].items():
            if k == self.aranet_sensor:
                return v

    def toggle_oled(self, pin):
        if abs(utime.ticks_diff(utime.ticks_ms(), self._oled_switch_ticker)) > CFG_SWITCH_BOUNCE:
            self._oled_switch_ticker = utime.ticks_ms()
            self._oled_active = not self._oled_active
            self.write_oled()

    def write_oled(self, text=None, stamp=True):
        # Clear screen
        self._oled.clear()
        # New text?
        if text:
            if stamp:
                self._oled_buffer.append("{}|{}".format(time_of_day(offset=1), text))
            else:
                self._oled_buffer.append(text)
        # Rotate buffer?
        if len(self._oled_buffer) > 8:
            self._oled_buffer = self._oled_buffer[-8:]
        try:
            # Print to OLED
            if self._oled_active:
                for i, line in enumerate(self._oled_buffer):
                    self._oled.draw_text(line, 0, i * 8)
            # Display
            self._oled.show()
        except OledError as err:
            print("({}) {}".format(err, text))

    def publish(self, metric):
        try:
            self._mqtt.publish(self.mqtt_topic, str(metric))
            self._last_published = utime.time()
        except MQTTError as err:
            print("Could not publish to MQTT : {}".format(err))

    def display(self, metric, warning=False):
        # Prepare nugget
        try:
            nugget = "{}%".format(round(metric))
        except TypeError:
            if metric is None:
                nugget = "N/A"
            else:
                nugget = str(metric)[:5]
        # Display
        self.write_oled("{} {}".format(nugget, "*" if warning else ""))

    def reboot(self, force=False):
        if force:
            print("Rebooting board [FORCED].")
            machine.reset()
        if self.auto_reboot > 0:
            if utime.time() > min(self._last_polled, self._last_published) + self.auto_reboot:
                print("Rebooting board. Auto reboot timer was exceeded.")
                machine.reset()

    def loop(self):
        self._running = True
        self._last_measured = 0
        self._next_poll = 0
        # Initialize those two to current time to avoid insta-reboot by watchdog
        self._last_polled = self._last_published = utime.time()
        self.write_oled("Start...")
        while self._running:
            if utime.time() > self._next_poll:
                # Reset next poll timer
                self._next_poll = utime.time() + self.interval
                # Extract metrics
                try:
                    sensor_data = self.poll()
                    self._last_polled = utime.time()
                    if sensor_data['time'] > self._last_measured:
                        # Note that _last_measured reflects Aranet OWN time, while _last_polled reflects board time
                        # We need both but they are not necessarily in sync, so we store both.
                        self._last_measured = sensor_data['time']
                        # Process results
                        self.publish(sensor_data['h'])
                        self.display(sensor_data['h'], warning=utime.time() > self._last_published + self.interval)
                    else:
                        self.display("Old")
                except requests.RequestError as err:
                    print("Could not fetch data from Aranet : {}".format(err))
                    self.display("Error")
            # Reboot needed?
            self.reboot(force=False)
            # Sleep until next poll
            utime.sleep(1)

    def go(self):
        try:
            self.loop()
        except Exception as err:
            self.write_oled("[CRASH]")
            self.write_oled(": {}".format(err.__class__.__name__), stamp=False)
            self.write_oled(": {}".format(err), stamp=False)


if __name__ == "__main__":
    # Load config
    import ujson
    with open("config.json") as f:
        ara_cfg = ujson.load(f)
    # Spawn handler
    ara = Aranette(**ara_cfg)
    # Go!
    ara.go()
