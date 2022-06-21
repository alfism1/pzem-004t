import http.client
import sys
import time
import json
import serial
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
from signal import signal, SIGTERM, SIGHUP, pause
from rpi_lcd import LCD
import RPi.GPIO as GPIO


GPIO.setmode(GPIO.BCM)  # GPIO Numbers instead of board numbers


def update_stopkontak_status(status="active"):
    conn = http.client.HTTPSConnection("ufatech.id")
    payload = json.dumps({
        "stopkontak": "stopkontak_0001",
        "status": status
    })
    headers = {
        'Content-Type': 'application/json'
    }
    conn.request("POST", "/pln/api/update_stopkontak.php", payload, headers)
    res = conn.getresponse()
    data = res.read()
    print(data.decode("utf-8"))


def splu_process():
    lcd = LCD(bus=1)
    quotaKwH = int(sys.argv[3])

    RELAIS_1_GPIO = int(sys.argv[2])
    GPIO.setup(RELAIS_1_GPIO, GPIO.OUT)  # GPIO Assign mode

    def toggle_relay(gpio=RELAIS_1_GPIO, status=""):
        if status == "on":
            GPIO.output(gpio, GPIO.LOW)
        if status == "off":
            GPIO.output(gpio, GPIO.HIGH)

    def safe_exit(signum, frame):
        exit(1)

    def calculate_quotaKwH(kwH_usage):
        return quotaKwH - kwH_usage

    def kwH_usage(energyWh, initialWh):
        return energyWh - initialWh

    try:
        toggle_relay(RELAIS_1_GPIO, "on")
        signal(SIGTERM, safe_exit)
        signal(SIGHUP, safe_exit)

        # lcd.text("Hello,", 1)
        # lcd.text("Raspberry Pi!", 2)

        print("Connection to serial...")
        # Connect to the slave
        ser = serial.Serial(
            port=sys.argv[1],
            baudrate=9600,
            bytesize=8,
            parity='N',
            stopbits=1,
            xonxoff=0
        )
        i = 0
        initialKwH = 0
        update_stopkontak_status(status="active")

        while True:
            try:
                print("Connecting to modbus...")
                time.sleep(3)
                master = modbus_rtu.RtuMaster(ser)
                master.set_timeout(2.0)
                master.set_verbose(True)
                # Changing power alarm value to 100 W
                # master.execute(1, cst.WRITE_SINGLE_REGISTER, 1, output_value=100)
                dict_payload = dict()

                while True:
                    data = master.execute(1, cst.READ_INPUT_REGISTERS, 0, 10)

                    dict_payload["voltage"] = data[0] / 10.0
                    dict_payload["current_A"] = (
                        data[1] + (data[2] << 16)) / 1000.0  # [A]
                    dict_payload["power_W"] = (
                        data[3] + (data[4] << 16)) / 10.0  # [W]
                    dict_payload["energy_Wh"] = data[5] + \
                        (data[6] << 16)  # [Wh]
                    dict_payload["frequency_Hz"] = data[7] / 10.0  # [Hz]
                    dict_payload["power_factor"] = data[8] / 100.0
                    dict_payload["alarm"] = data[9]  # 0 = no alarm
                    dict_payload["initialKwH"] = initialKwH
                    str_payload = json.dumps(dict_payload, indent=2)
                    # print(str_payload)

                    if initialKwH == 0:
                        print("initialKwH inisiated...")
                        initialKwH = dict_payload["energy_Wh"]

                    # lcd.text(
                    #     str(round(dict_payload["energy_Wh"]/1000, 3)) + " kWh", 1)
                    lcd.text("Sisa Wh:" +
                             str(calculate_quotaKwH(kwH_usage(dict_payload["energy_Wh"], initialKwH))) + " Wh", 1)
                    lcd.text("Power W:" +
                             str(dict_payload["power_W"]) + " W", 2)

                    # Block process once reach the quota. Go to finally
                    if calculate_quotaKwH(kwH_usage(dict_payload["energy_Wh"], initialKwH)) == 0:
                        return

                    # lcd.text(
                    #     str(kwH_usage(dict_payload["energy_Wh"], initialKwH)) + " Wh", 2)

                    time.sleep(1)
            except Exception as e:
                print(e)
                print("Attempts:", i)
                i = i + 1
                continue
            finally:
                print("Closing...")
                # lcd.clear()
                master.close()
                # toggle_relay(RELAIS_1_GPIO, "off")
                print("Closed")

    except KeyboardInterrupt:
        print('exiting pzem script')
    except Exception as err:
        print("Serial connection failed")
        print("Serial error: ", err)
        toggle_relay(RELAIS_1_GPIO, "off")
    finally:
        update_stopkontak_status("nonactive")
        toggle_relay(RELAIS_1_GPIO, "off")
        lcd.clear()
        lcd.text("Kuota kWh tidak tersedia", 1)
        # GPIO.cleanup()


splu_process()
