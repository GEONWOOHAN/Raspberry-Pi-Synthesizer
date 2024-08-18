import mido
import smbus2
import time
import threading
import logging
from collections import deque

I2C_SLAVE_ADDRESS = 0x08
BUS = smbus2.SMBus(1)
MIDI_BUFFER = deque()
I2C_BUFFER = deque()
BUFFER_LOCK = threading.Lock()
I2C_EVENT = threading.Event()
SUSTAIN_CYCLE_STATE = 1

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s')

def to_8bit_binary(value):
    return f'{value:08b}'

def percentage_to_8bit_binary(percentage):
    return to_8bit_binary(round(percentage * 1.27))

def get_sustain_cycle_value():
    global SUSTAIN_CYCLE_STATE
    cycle_value = f'{SUSTAIN_CYCLE_STATE:04b}'
    SUSTAIN_CYCLE_STATE = SUSTAIN_CYCLE_STATE % 3 + 1
    return cycle_value

def process_midi_message(msg):
    cycle_value = get_sustain_cycle_value()
    binary_code = None

    if msg.type == 'note_on' and msg.velocity > 0:
        binary_code = f'1001{cycle_value}{to_8bit_binary(msg.note)}{to_8bit_binary(msg.velocity)}'
    elif msg.type in ['note_off', 'note_on'] and msg.velocity == 0:
        binary_code = f'1001{cycle_value}{to_8bit_binary(msg.note)}00000000'
    elif msg.type == 'control_change' and msg.control == 7:
        binary_code = f'0001{cycle_value}{percentage_to_8bit_binary(msg.value / 127 * 100)}00000000'

    if binary_code:
        logging.debug(f"24-bit binary code: {binary_code}")
        with BUFFER_LOCK:
            for i in range(0, 24, 8):
                MIDI_BUFFER.append(f'0{binary_code[i:i+8]}1')

def handle_midi_input():
    while True:
        try:
            for msg in midi_in.iter_pending():
                process_midi_message(msg)
        except Exception as e:
            logging.error(f"Error in handle_midi_input: {e}")

def process_midi_data():
    while True:
        with BUFFER_LOCK:
            if len(MIDI_BUFFER) >= 7:
                seven_bits = ''.join(MIDI_BUFFER.popleft() for _ in range(7))
                parity_bit = '1' if seven_bits.count('1') % 2 == 0 else '0'
                final_byte = int(f'{seven_bits}{parity_bit}', 2)
                I2C_BUFFER.append(final_byte)
                I2C_EVENT.set()
        time.sleep(224.28e-6)  # 약 224.28 마이크로초

def i2c_send_data():
    while True:
        I2C_EVENT.wait()
        with BUFFER_LOCK:
            if I2C_BUFFER:
                data = I2C_BUFFER.popleft()
                try:
                    BUS.write_byte(I2C_SLAVE_ADDRESS, data)
                    logging.debug(f"Sent data to I2C: {data}")
                except OSError as e:
                    logging.error(f"Error sending data to I2C: {e}")
        I2C_EVENT.clear()

def select_midi_input():
    print("MIDI input port list:")
    for port in mido.get_input_names():
        print(port)
    selected_port = input("Select a MIDI input port: ")
    return mido.open_input(selected_port)

midi_in = select_midi_input()
midi_thread = threading.Thread(target=handle_midi_input)
process_thread = threading.Thread(target=process_midi_data)
i2c_thread = threading.Thread(target=i2c_send_data)

midi_thread.start()
process_thread.start()
i2c_thread.start()
