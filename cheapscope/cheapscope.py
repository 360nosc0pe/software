import sys, struct
from mmio import MMIO
import numpy as np
import time

class Clock:
    def __init__(self):
        pass
    
    def init(self):
        self.set(b"\x40\x31\x20") # CONTROL
        self.set(b"\x04\xE1\x42") # NCOUNTER
        self.set(b"\x00\x07\xD1") # RCOUNTER
    
    def set(self, x):
        f = open("/dev/spidev32766.0", "wb")
        f.write(x)
        f.close()

class AdcIf:
    def __init__(self):
        self.m = MMIO(0x83C00000, 0x10000)

    def reset(self):
        self.m.write32(0, 1)
        print("%08x" % self.m.read32(4))
        self.m.write32(0, 0)
        print("%08x" % self.m.read32(4))

        
class ADC:
    def __init__(self, ch):
        self.ch = ch
    
    def data_mode(self):
        self.set_reg(0, 0x0001)
        time.sleep(.1)
        self.set_reg(0xF, 0x200)
        time.sleep(.1)
        self.set_reg(0x31, 0x0001)
#        self.set_reg(0x53, 0x0000)
#        self.set_reg(0x31, 0x0008)
#        self.set_reg(0x53, 0x0004)

        self.set_reg(0x0F, 0x0000)
        self.set_reg(0x30, 0x0008)
        self.set_reg(0x3A, 0x0202)
        self.set_reg(0x3B, 0x0202)
        self.set_reg(0x33, 0x0001)
        self.set_reg(0x2B, 0x0222)
        self.set_reg(0x2A, 0x2222)
        self.set_reg(0x25, 0x0000)
        self.set_reg(0x31, 0x0001) # clk_divide = /1, single channel interleaving ADC1..4

    def set_reg(self, reg, value):
        print("write ADC%d %02x := %04x" % (self.ch, reg, value))
        f = open("/dev/spidev32766.%d" % (self.ch + 1), "wb")
        f.write(struct.pack(">BH", reg, value))
        f.close()

    def ramp(self):
        self.set_reg(0x25, 0x0040)
        
    def single(self, pattern):
        self.set_reg(0x25, 0x0010)
        self.set_reg(0x26, pattern)

    def dual(self, pattern0, pattern1):
        self.set_reg(0x25, 0x0020)
        self.set_reg(0x26, pattern0)
        self.set_reg(0x27, pattern1)

    def pat_deskew(self):
        self.set_reg(0x25, 0x0000)
        self.set_reg(0x45, 2)

    def pat_sync(self):
        self.set_reg(0x25, 0x0000)
        self.set_reg(0x45, 1)

class DMA:
    def __init__(self, base = 0x80400000, mem_base = 0x0F000000, mem_size = 0x00001000):
    
        self.mem_base = mem_base
        self.mem_size = mem_size
#        assert mem_size <= 4096

        self.dma = MMIO(base, 0x100)
        self.mem = MMIO(self.mem_base, self.mem_size)


    def read(self):
        self.dma.write32(0x30, 1<<2) # reset
        while True:
            d = self.dma.read32(0x30)
            if not (d & (1<<2)):
                break

        self.dma.write32(0x30, 1)
        self.dma.write32(0x48, self.mem_base)
#        print("reading %08x bytes" % self.mem_size)
        self.dma.write32(0x58, self.mem_size)
#        print("S2MM_LENGTH: %08x, S2MM_DMACR: %08x, SR %08x, adr %08x" % (self.dma.read32(0x58), self.dma.read32(0x30), self.dma.read32(0x34), self.dma.read32(0x48)))
        while self.dma.read32(0x30) & 1:
            print("... going")

        return self.mem.read(0, self.mem_size)[1024:]

class OffsetDAC:
    def __init__(self):
        self.m = MMIO(0x83C00000, 0x10000)
        print("1 %08x" % self.m.read32(0))
        print("4 %08x control, clkdiv, enable" % self.m.read32(0x804))

    def set_ch(self, ch, val):
        self.m.write32(0x810 + ch * 4 - 4, val)

class Frontend:
    def __init__(self, adc0, adc1, offsetdac):
        self.adcs = [adc0, adc1]
        self.offsetdac = offsetdac
    
    def set_adc_reg(self, adc, reg, value):
        self.adcs[adc].set_reg(reg, value)

    def set_frontend(self, data):
        print(len(data), data)
        assert len(data) == 5
        assert data[0] == 0
        f = open("/dev/spidev32766.3", "wb")
        f.write(data)
        f.close()

    def set_vga(self, ch, gain):
        f = open("/dev/spidev32766.%d" % (4 + ch), "wb")
        f.write(bytes([gain]))
        f.close()
    

    def set_ch1_1v(self):
        self.set_frontend(bytes([0, 0x7A, 0x7A, 0x7A, 0x7E]))
        self.set_vga(0, 0x1F)
        self.set_adc_reg(0, 0x2B, 00)

    def set_ch1_100mv(self):
        self.set_frontend(bytes([0, 0x7A, 0x7A, 0x7A, 0x78]))
        self.set_vga(0, 0xad)
        self.set_adc_reg(0, 0x2B, 00)


clock = Clock()
clock.init()

adc0 = ADC(0)
adc0.data_mode()

adcif = AdcIf()
adcif.reset()
adcif.reset()

offsetdac = OffsetDAC()
frontend = Frontend(adc0, None, offsetdac)
frontend.set_ch1_100mv()
dma = DMA(mem_base = 0x90000000, mem_size = 16384)

#adc0.ramp()
#adc0.dual(0xfeed,0xbabe)

import time

#for i in range(0x0000, 0xf800, 0x100):
#    offsetdac.set_ch(4, i)
#    time.sleep(.1)
#    data = dma.read()
#    print("%08x %d" % (i,  sum(data)/len(data)))

for ch in range(4, 8):
    offsetdac.set_ch(ch, 0x25e0)

m = open("/dev/fb0", "wb")

stride = 800 * 4
framebuffer = np.zeros((600, 800, 3), dtype=np.uint8)
bpp = 3


while True:
    data = dma.read()
#    print(data[:16])

    t1 = False
    t2 = False
    
    trig_level = 128
    
    for x, y in enumerate(data):
        if y > trig_level + 20:
            t1 = True
        if t1 and y < trig_level - 20:
            t2 = True
        if t2:
            break
    
    if len(data) - x < 800:
        x = 0
    
    data = data[x:]
    
#    framebuffer[:] -= framebuffer[:]//10
    framebuffer[:] = 0
    for x, y in enumerate(data):
        if x//4 >= 800:
            break
        framebuffer[y][x//4][0] = 0xFf
        framebuffer[y][x//4][1] = 0xFf
        framebuffer[y][x//4][2] = 0xFf

    m.seek(0)
    m.write(framebuffer.tobytes())
