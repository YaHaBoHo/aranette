# WiPy driver for SSD1306
# https://www.sparkfun.com/products/14532
# https://cdn.sparkfun.com/assets/learn_tutorials/3/0/8/SSD1306.pdf
# Init settings follow Spakfun Arduino driver for LCD-14532
# https://github.com/sparkfun/SparkFun_Micro_OLED_Arduino_Library/blob/master/src/SFE_MicroOLED.cpp

import struct
import machine
import framebuf
from micropython import const


# Constants
# SSD1306 commands
DISPLAY_ON = const(0xaf)
DISPLAY_OFF = const(0xae)
SET_CLOCK_DIVIDER = const(0xd5)
SET_MULTIPLEXER_RATIO = const(0xa8)
SET_DISPLAY_OFFSET = const(0xd3)
SET_DISPLAY_START_LINE = const(0x40)
SET_DISPLAY_NORMAL = const(0xa6)
SET_DISPLAY_INVERTED = const(0xa7)
SET_DISPLAY_CONTRAST = const(0x81)
SET_OUTPUT_MEM = const(0xa4)
SET_OUTPUT_ALL = const(0xa5)
SET_CHARGE_PUMP = const(0x8d)
SET_SEGMENT_REMAP = const(0xa0)
SET_COM_OUTPUT_DIR = const(0xc8)
SET_COM_PIN_CONFIG = const(0xda)
SET_PRECHARGE_PERIOD = const(0xd9)
SET_VCOM_DESELECT = const(0xdb)
SET_MEMORY_MODE = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)


class OledError(Exception):
    pass


class SSD1306():

    def __init__(self, width,  height, i2c_id,
                 i2c_bus=0, i2c_sda="P9", i2c_scl="P10", ext_vcc=False):
        # Setup
        self.width = width
        self.height = height
        self.i2c_id = i2c_id
        self.i2c = machine.I2C(i2c_bus, pins=(i2c_sda, i2c_scl))
        self.ext_vcc = ext_vcc
        # Initialize
        self.pages = self.height // 8
        self.coffset = 32 if self.width == 64 else 0
        self.buffer = bytearray(self.width * self.pages)
        self.fb = framebuf.FrameBuffer(
            self.buffer, self.width, self.height, framebuf.MVLSB)
        self.i2c.init(machine.I2C.MASTER, baudrate=400000)

    def initialize(self):
        # Turn display off
        self.turn_off()
        # Execute initialization routine
        # TODO : Comment or document
        self.execute(
            SET_MEMORY_MODE, 0x00,
            SET_CLOCK_DIVIDER, 0x80,
            SET_MULTIPLEXER_RATIO, self.height - 1,
            SET_DISPLAY_OFFSET, 0x00,
            SET_DISPLAY_START_LINE | 0x00,
            SET_CHARGE_PUMP, 0x10 if self.ext_vcc else 0x14,  # ToCheck
            SET_PRECHARGE_PERIOD, 0x22 if self.ext_vcc else 0xf1,  # ToCheck
            SET_DISPLAY_NORMAL,
            SET_OUTPUT_MEM,
            SET_SEGMENT_REMAP | 0x01,
            SET_COM_OUTPUT_DIR,
            SET_COM_PIN_CONFIG, 0x02 if self.height == 32 else 0x12,  # ToCheck
            SET_DISPLAY_CONTRAST, 0x8f,
            SET_VCOM_DESELECT, 0x40)
        # Initialize display
        self.clear()
        self.show()
        # Turn display on
        self.turn_on()

    def cleanup(self):
        self.turn_off()
        self.i2c.deinit()

    def turn_on(self):
        self.execute(DISPLAY_ON)

    def turn_off(self):
        self.execute(DISPLAY_OFF)

    def clear(self):
        self.fb.fill(0)

    def draw_borders(self):
        self.fb.rect(0, 0, self.width, self.height, 1)

    def draw_text(self, string, x, y):
        self.fb.text(string, x, y, 1)

    def show(self,):
        self.execute(
            SET_COL_ADDR, 0x00 + self.coffset, self.width - 1 + self.coffset,
            SET_PAGE_ADDR, 0x00, self.pages - 1)
        self.send(self.buffer)

    def execute(self, *commands):
        try:
            for cmd in commands:
                buffer = struct.pack("BB", 0x80, cmd)
                self.i2c.writeto(self.i2c_id, buffer)
            return True
        except OSError as err:
            raise OledError("OLED Error : {}".format(err))
        return False

    def send(self, payload):
        try:
            buffer = struct.pack("B"*(len(payload)+1), 0x40, *payload)
            self.i2c.writeto(self.i2c_id, buffer)
            return True
        except OSError as err:
            raise OledError("OLED Error : {}".format(err))
        return False

    @classmethod
    def otronics(cls, i2c_bus=0, i2c_sda="P9", i2c_scl="P10", ext_vcc=False):
        return cls(
            width=128,
            height=64,
            i2c_id=0x3c,
            i2c_bus=i2c_bus,
            i2c_sda=i2c_sda,
            i2c_scl=i2c_scl,
            ext_vcc=ext_vcc)

    @classmethod
    def sparkfun(cls, i2c_bus=0, i2c_sda="P9", i2c_scl="P10", ext_vcc=False):
        return cls(
            width=64,
            height=48,
            i2c_id=0x3d,
            i2c_bus=i2c_bus,
            i2c_sda=i2c_sda,
            i2c_scl=i2c_scl,
            ext_vcc=ext_vcc)
