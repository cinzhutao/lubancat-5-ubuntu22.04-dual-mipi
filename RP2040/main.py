from machine import ADC,I2C,Pin
import micropython
import time
import sys
import rp2

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW, out_shiftdir=rp2.PIO.SHIFT_LEFT, autopull=True, pull_thresh=24)
def ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1)               .side(0)    [T3 - 1]
    jmp(not_x, "do_zero")   .side(1)    [T1 - 1]
    jmp("bitloop")          .side(1)    [T2 - 1]
    label("do_zero")
    nop()                   .side(0)    [T2 - 1]
    wrap()


# Create the StateMachine with the ws2812 program, outputting on Pin(4).
sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(16))

# Start the StateMachine, it will wait for data on its FIFO.
sm.active(1)
sm.put(0x080800)

#########################
SPI_SDO = Pin(0,Pin.IN)
SPI_CS = Pin(1,Pin.OUT)
SPI_SCK = Pin(2,Pin.IN)
SPI_SDI = Pin(3,Pin.IN)
SPI_CS.value(1)

I2C1 = I2C(id = 1,scl = Pin(7),sda = Pin(6),freq = 400000)

GPIO1 = Pin(8,Pin.OUT)
GPIO2 = Pin(9,Pin.IN)
GPIO3 = Pin(10,Pin.OUT)
GPIO4 = Pin(11,Pin.OUT)
GPIO5 = Pin(12,Pin.OUT)

OLED_RESET_PIN = 13
OLED_RESET = Pin(OLED_RESET_PIN,Pin.OUT)

SWIRE = Pin(14,Pin.IN)
AVDD_EN = Pin(15,Pin.IN)
TE = Pin(17,Pin.IN)

GPIO1.value(0)
# GPIO2.value(0)
GPIO3.value(1)
GPIO4.value(0)
GPIO5.value(0)

VDDI_EN = Pin(20,Pin.OUT)
NVMD_EN = Pin(21,Pin.OUT)
ELVDD_EN = Pin(24,Pin.OUT)
ELVSS_EN = Pin(22,Pin.OUT)
VCORE_EN = Pin(23,Pin.OUT)

VPMIC_EN = Pin(25,Pin.OUT)

# The first sequence prepares panel power before Linux starts. U-Boot display
# output is disabled in the no-video test image, so RP2040 must not send panel
# commands or run a timed second power cycle here.
SECOND_POWER_CYCLE_DELAY_S = 8
SECOND_POWER_OFF_DELAY_S = 1.0
G8103_ADDR = 0x23
LINUX_TRIGGER_MIN_INTERVAL_MS = 3000
LINUX_TRIGGER_MONITOR_WINDOW_MS = 40000
LINUX_TRIGGER_POLL_MS = 5
LINUX_TRIGGER_HEARTBEAT_MS = 5000
linux_trigger_armed = False
linux_trigger_running = False
linux_trigger_last_ms = 0
LOG_FILE = "rp2040_power.log"

def log_event(*items):
    msg = " ".join([str(item) for item in items])
    line = "[%d] %s" % (time.ticks_ms(), msg)
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as error:
        print("log write failed:", error)

def dump_log():
    try:
        with open(LOG_FILE, "r") as f:
            print(f.read())
    except Exception as error:
        print("log read failed:", error)

def clear_log():
    try:
        with open(LOG_FILE, "w") as f:
            f.write("")
        print("log cleared")
    except Exception as error:
        print("log clear failed:", error)

def oled_reset_assert():
    global OLED_RESET
    OLED_RESET = Pin(OLED_RESET_PIN, Pin.OUT)
    OLED_RESET.value(0)

def oled_reset_release():
    global OLED_RESET
    OLED_RESET = Pin(OLED_RESET_PIN, Pin.IN, Pin.PULL_UP)

def linux_trigger_irq(pin):
    global linux_trigger_running
    if not linux_trigger_armed or linux_trigger_running:
        return
    linux_trigger_running = True
    micropython.schedule(linux_trigger_power_cycle, 0)

def arm_linux_handoff_trigger():
    global linux_trigger_armed, linux_trigger_running, linux_trigger_last_ms
    linux_trigger_running = False
    linux_trigger_last_ms = time.ticks_ms()
    oled_reset_release()
    OLED_RESET.irq(trigger=Pin.IRQ_FALLING, handler=linux_trigger_irq)
    linux_trigger_armed = True
    log_event("linux handoff trigger armed on GP13/OLED_RESET",
              "reset=", OLED_RESET.value())

def linux_trigger_power_cycle(_):
    global linux_trigger_running, linux_trigger_last_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, linux_trigger_last_ms) < LINUX_TRIGGER_MIN_INTERVAL_MS:
        log_event("linux handoff trigger ignored by debounce",
                  "reset=", OLED_RESET.value())
        linux_trigger_running = False
        return

    log_event("linux handoff trigger: cold power cycle start",
              "reset=", OLED_RESET.value())
    OLED_RESET.irq(handler=None)
    panel_power_off(SECOND_POWER_OFF_DELAY_S, True)
    panel_power_on("linux-trigger")
    oled_reset_release()
    linux_trigger_last_ms = time.ticks_ms()
    OLED_RESET.irq(trigger=Pin.IRQ_FALLING, handler=linux_trigger_irq)
    linux_trigger_running = False
    log_event("linux handoff trigger: cold power cycle complete",
              "reset=", OLED_RESET.value())

def timed_second_power_cycle():
    log_event("timed second cold power cycle wait start",
              "delay_s=", SECOND_POWER_CYCLE_DELAY_S,
              "reset=", OLED_RESET.value())
    time.sleep(SECOND_POWER_CYCLE_DELAY_S)
    log_event("timed second cold power cycle start",
              "off_delay_s=", SECOND_POWER_OFF_DELAY_S,
              "reset=", OLED_RESET.value())
    panel_power_off(SECOND_POWER_OFF_DELAY_S, True)
    panel_power_on("timed-second")
    oled_reset_release()
    log_event("timed second cold power cycle complete",
              "reset=", OLED_RESET.value())

def monitor_linux_handoff_trigger(window_ms=LINUX_TRIGGER_MONITOR_WINDOW_MS):
    global linux_trigger_running
    end = time.ticks_add(time.ticks_ms(), window_ms)
    next_heartbeat = time.ticks_add(time.ticks_ms(), LINUX_TRIGGER_HEARTBEAT_MS)
    last_reset = OLED_RESET.value()

    log_event("linux handoff trigger monitor start",
              "window_ms=", window_ms,
              "reset=", last_reset)

    try:
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            now = time.ticks_ms()
            reset = OLED_RESET.value()
            if reset != last_reset:
                log_event("GP13/OLED_RESET transition",
                          "from=", last_reset,
                          "to=", reset)
                last_reset = reset

            if time.ticks_diff(now, next_heartbeat) >= 0:
                log_event("linux handoff trigger monitor heartbeat",
                          "reset=", reset)
                next_heartbeat = time.ticks_add(now,
                                                LINUX_TRIGGER_HEARTBEAT_MS)

            if linux_trigger_armed and not linux_trigger_running and reset == 0:
                linux_trigger_running = True
                log_event("linux handoff trigger detected by polling",
                          "reset=", reset)
                linux_trigger_power_cycle(0)
                last_reset = OLED_RESET.value()

            time.sleep_ms(LINUX_TRIGGER_POLL_MS)

        log_event("linux handoff trigger monitor end",
                  "reset=", OLED_RESET.value())
    except Exception as error:
        log_event("linux handoff trigger monitor exception:", error)

# SPI_CS = Pin(1,Pin.OUT)
# SPI_SCK = Pin(2,Pin.OUT)
# SPI_SDI = Pin(3,Pin.OUT)
# SPI_SDO = Pin(0,Pin.IN)

def spi_write(spi_data):
    SPI_CS.value(0)
    for i in range(0,8):
        time.sleep(0.00001)
        SPI_SCK.value(0)
        time.sleep(0.00001)
        if spi_data&0x80 == 0x80:
            SPI_SDI.value(1)
        else:
            SPI_SDI.value(0)
        time.sleep(0.00001)
        SPI_SCK.value(1)
        time.sleep(0.00001)
        spi_data=(spi_data<<1)

def spi_read():
    read_data = 0
    SPI_CS.value(0)
    time.sleep(0.0001)
    for i in range(0,8):
        time.sleep(0.0001)
        SPI_SCK.value(0)
        time.sleep(0.0001)
        read_data=(read_data<<1);
        SPI_SCK.value(1)
        time.sleep(0.0001)
        read_data =  read_data + SPI_SDO.value()
        time.sleep(0.0001)
    return read_data

def P40T_read(reg):
    SPI_CS.value(0)
    time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(0xFD)
    for i in range(0,4):
        time.sleep(0.0001)
        SPI_SDI.value(1)
        time.sleep(0.0001)
        SPI_SCK.value(0)
        time.sleep(0.0001)
        SPI_SCK.value(1)
        time.sleep(0.0001)
        spi_write(reg >> ((3-i)*8))
    spi_read()
    read_data = ''
    read_data = '%02x' % spi_read()
    read_data = read_data + '%02x' % spi_read()
    read_data = read_data + '%02x' % spi_read()
    read_data = read_data + '%02x' % spi_read()

    SPI_CS.value(1)
    print(read_data)
    return read_data

def P40T_write(reg,data):
    SPI_CS.value(0)
    time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(0xFC)
    for i in range(0,4):
        time.sleep(0.0001)
        SPI_SDI.value(1)
        time.sleep(0.0001)
        SPI_SCK.value(0)
        time.sleep(0.0001)
        SPI_SCK.value(1)
        time.sleep(0.0001)
        spi_write(reg >> ((3-i)*8))
    for i in range(0,4):
        time.sleep(0.0001)
        SPI_SDI.value(1)
        time.sleep(0.0001)
        SPI_SCK.value(0)
        time.sleep(0.0001)
        SPI_SCK.value(1)
        time.sleep(0.0001)
        spi_write(data >> ((3-i)*8))
    SPI_CS.value(1)


def P40T_write_UCS_MCS(reg,data):
    SPI_CS.value(0)
    time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(reg)
    time.sleep(0.0001)
    for i in range(0,len(data)):
        SPI_SDI.value(1)
        time.sleep(0.0001)
        SPI_SCK.value(0)
        time.sleep(0.0001)
        SPI_SCK.value(1)
        time.sleep(0.0001)
        spi_write(data[i])
        time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(0xFE)
    time.sleep(0.0001)
    SPI_CS.value(1)

def P40T_read_UCS_MCS(reg,num):

    SPI_CS.value(0)
    time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(0xFA)
    time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(reg)
    time.sleep(0.0001)
    read_data = ''
    for i in range(0,num):
        read_data = read_data + '%02x' % spi_read()
        time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(0xFB)
    time.sleep(0.0001)
    SPI_SDI.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(0)
    time.sleep(0.0001)
    SPI_SCK.value(1)
    time.sleep(0.0001)
    spi_write(0xFE)
    time.sleep(0.0001)
    SPI_CS.value(1)
    return read_data

def P40T_BIST():
    P40T_write(0x05040088,0x9B223005)
    P40T_write(0x0504008C,0x82123005)
    P40T_write(0x05040090,0x6E033005)
    P40T_write(0x05001044,0x01100000)
    P40T_write(0x05001040,0x00000028)
    P40T_write(0x05001048,0x000A8000)
    P40T_write(0x05001074,0x00000006)     #sysctrl_testpin_sel 6:DSS
    P40T_write(0x05040034,0x00000100)
    P40T_write(0x05020018,0x0000001C)

    P40T_write(0x0502100C,0x00000101)     #gmd_tpg_enable,bit0:0:TPG mode disable 1:TPG mode enable

    P40T_write(0x05021010,0x0a418829)
    P40T_write(0x05020018,0x0000001C)
    time.sleep(0.2)
    P40T_write_UCS_MCS(0x11,[])
    time.sleep(0.2)

def P40T_Init():
    P40T_read(0x050010E0) #read,0xP40T,0xversion
    P40T_read(0x0500400c) #crg_clk_sel

    P40T_read(0x05026C20)

    P40T_write(0x05001044,0x01100000)
    P40T_write(0x05020400,0x00000004) #2jinzhi,0x1100
    P40T_write(0x05004000,0x00080000)
    ###################dsc########################
    P40T_write(0x05020c3c,0x0f180010)
    P40T_write(0x05020c40,0x2f001600)
    P40T_write(0x05020c44,0xc10bdc01)
    P40T_write(0x05020c48,0x35000150)
    P40T_write(0x05020c4c,0x340b4005)
    P40T_write(0x05020c50,0xd0168005)
    P40T_write(0x05020c54,0xab900414)
    P40T_write(0x05020c5c,0x000080ad)
    P40T_write(0x05020c60,0x000080ad)
    P40T_write(0x05020c64,0x000080ad)
    P40T_write(0x05020c68,0x000080ad)
    P40T_write(0x05020c78,0x00000019)
    P40T_write(0x05020c80,0x0000007d)
    P40T_write(0x05020c88,0xFFFF0000)
    ###################vo#########################

    P40T_write(0x05026c24,0x000B0010)
    P40T_write(0x05026c28,0x00100010)
    P40T_write(0x05026c30,0x00030002)
    P40T_write(0x05026c2c,0x0EFF0DDF)
    P40T_write(0x05020410,0x0B3F0A67)
    P40T_write(0x0502000C,0x0EFF0DDF)
    P40T_write(0x05026c2c,0x0EFF0DDF)
    P40T_write(0x05021408,0x0EFF0DDF)
    ###################mipi#######################
    P40T_write(0x05010400,0x00000004)
    P40T_write(0x05010440,0x00000001)
    P40T_write(0x05010444,0x0000000f)
    P40T_write(0x05010600,0x00000001)
    P40T_write(0x05010608,0x00000002)
    P40T_write(0x0501060c,0x00000002)
    P40T_write(0x05010610,0x00000002)
    P40T_write(0x05010614,0x00000001)
    P40T_write(0x05010618,0x00000001)
    P40T_write(0x0501062c,0x00000001)
    P40T_write(0x05010604,0x00000003)

    P40T_write(0x05011400,0x00000004)
    P40T_write(0x05011440,0x00000001)
    P40T_write(0x05011444,0x0000000f)
    P40T_write(0x05011600,0x00000001)
    P40T_write(0x05011608,0x00000002)
    P40T_write(0x0501160c,0x00000002)
    P40T_write(0x05011610,0x00000002)
    P40T_write(0x05011614,0x00000001)
    P40T_write(0x05011618,0x00000001)
    P40T_write(0x0501162c,0x00000001)
    P40T_write(0x05011604,0x00000003)

    P40T_write(0x0501060C,0x00000001)
    P40T_write(0x0501160C,0x00000001)

    P40T_write(0x05010610,0x00000002)
    P40T_write(0x05011610,0x00000002)
    P40T_write(0x05011628,0x00000001)
    P40T_write(0x05010628,0x00000001)

    ###################vi########################
    P40T_write(0x05020400,0x00000007)
    P40T_write(0x05020404,0x00000001)
    P40T_write(0x05040034,0x00000100)
    P40T_write(0x05001074,0x00000009)
    P40T_write(0x05012090,0x00000030)
    P40T_write(0x05026D08,0x00000001)
    P40T_write(0x05026D0C,0x03FF03FF)

    P40T_write_UCS_MCS(0x11,[])
    P40T_write_UCS_MCS(0x29,[])
    P40T_write(0x05021404,0x00000110) #,0xscaler,0xenable,0xmipi,0x29后
    P40T_read(0x05020c90)
    P40T_read(0x05020c94)
    P40T_read(0x05020c98)
    P40T_read(0x05020c9C)

def panel_power_off(delay_s, disable_pmic_outputs):
    log_event("panel power off", "disable_pmic_outputs=", disable_pmic_outputs)
    oled_reset_assert()

    if disable_pmic_outputs:
        try:
            I2C1.writeto_mem(G8103_ADDR,0x00,b'\x00')
        except OSError as error:
            log_event("PMIC output disable failed:", error)

    ELVSS_EN.value(0)
    ELVDD_EN.value(0)
    VCORE_EN.value(0)
    NVMD_EN.value(0)
    VDDI_EN.value(0)
    VPMIC_EN.value(0)
    time.sleep(delay_s)
    log_event("panel power off complete",
              "VPMIC=", VPMIC_EN.value(),
              "VDDI=", VDDI_EN.value(),
              "NVMD=", NVMD_EN.value(),
              "VCORE=", VCORE_EN.value(),
              "ELVDD=", ELVDD_EN.value(),
              "ELVSS=", ELVSS_EN.value())

def panel_power_on(cycle_name):
    log_event("panel power on:", cycle_name)

    VPMIC_EN.value(1)
    time.sleep(0.1)
    VDDI_EN.value(1)
    NVMD_EN.value(1)
    VCORE_EN.value(1)
    ELVDD_EN.value(1)
    ELVSS_EN.value(1)
    time.sleep(0.5)

    # PMIC Init
    I2C1.writeto_mem(G8103_ADDR,0x00,b'\x00')  # Output Enable
    I2C1.writeto_mem(G8103_ADDR,0x09,b'\x05')  # VCL-VAR -2.5V
    I2C1.writeto_mem(G8103_ADDR,0x03,b'\x0A')  # ELVDD2-ELVDD 3V
    I2C1.writeto_mem(G8103_ADDR,0x02,b'\x10')  # ELVDD1-AVDD  3.3V
    I2C1.writeto_mem(G8103_ADDR,0x07,b'\x00')  # ELVSS-H
    I2C1.writeto_mem(G8103_ADDR,0x08,b'\xAC')  # ELVSS-L -6.3V
    I2C1.writeto_mem(G8103_ADDR,0x0D,b'\x32')  # VCORE 1.8V
    #I2C1.writeto_mem(G8103_ADDR,0xFF,b'\x80')  # Write to ROM

    I2C1.writeto_mem(G8103_ADDR,0x00,b'\x0A') #AVDD ON
    time.sleep(0.01)
    I2C1.writeto_mem(G8103_ADDR,0x00,b'\x4E') #VAR/GVSS ON

    I2C1.writeto_mem(G8103_ADDR,0x00,b'\x5E') #ELVDD ON
    time.sleep(0.01)

    oled_reset_assert()
    time.sleep(0.1)
    oled_reset_release()

    time.sleep(3)

    I2C1.writeto_mem(G8103_ADDR,0x00,b'\x5E') #ELVDD ON
    time.sleep(0.01)
    I2C1.writeto_mem(G8103_ADDR,0x00,b'\x7E') #ELVSS ON

    try:
        pmic_output = I2C1.readfrom_mem(G8103_ADDR, 0x00, 1)[0]
        pmic_fault = I2C1.readfrom_mem(G8103_ADDR, 0x10, 1)[0]
    except OSError as error:
        pmic_output = -1
        pmic_fault = -1
        log_event("PMIC status read failed:", error)

    log_event("panel power on complete:", cycle_name,
              "pmic00=0x%02x" % pmic_output,
              "fault10=0x%02x" % pmic_fault,
              "reset=", OLED_RESET.value())

# Prepare PMIC rails and OLED_RESET before Linux initializes DSI.
panel_power_off(0.1, False)
panel_power_on("pre-linux")

# Keep the panel powered. Linux will be the first RK3588 stage to configure
# DSI Host/PHY/DSC and send panel-init-sequence.

# P40T_Init()
# P40T_BIST()
# P40T_write_UCS_MCS(0x29,[])
sm.put(0x000800)
# P40T_read(0x0502100C)

    










