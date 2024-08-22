import mido
import serial
import time
import logging
import threading

uart = serial.Serial('/dev/serial0', baudrate=31250, timeout=1)

sustain_cycle_state = 1

def to_8bit_binary(value):
    return f'{value:08b}'

def percentage_to_8bit_binary(percentage):
    value = round(percentage * 1.27)
    return to_8bit_binary(value)

def get_sustain_cycle_value():
    global sustain_cycle_state
    value = sustain_cycle_state
    sustain_cycle_state = sustain_cycle_state % 3 + 1
    return '{:04b}'.format(value)

def send_binary_code_to_uart(binary_code):
    for i in range(0, len(binary_code), 8):
        byte = binary_code[i:i+8]
        uart.write(bytes([int(byte, 2)]))
        time.sleep(0.001)

def handle_midi_input():
    def process_midi_message(msg):
        global sustain_cycle_state
        sustain_cycle_binary = '{:04b}'.format(sustain_cycle_state)
        if msg.type == 'note_on' and msg.velocity > 0:
            note_binary = to_8bit_binary(msg.note)
            velocity_binary = to_8bit_binary(msg.velocity)
            binary_code = f'1001{sustain_cycle_binary}{note_binary}{velocity_binary}'
            logging.debug(f"24-bit binary code (Note On): {binary_code}")
            print(binary_code)
            send_binary_code_to_uart(binary_code)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            note_binary = to_8bit_binary(msg.note)
            binary_code = f'1001{sustain_cycle_binary}{note_binary}00000000'
            logging.debug(f"24-bit binary code (Note Off): {binary_code}")
            print(binary_code)
            send_binary_code_to_uart(binary_code)
        elif msg.type == 'control_change':
            if msg.control == 7:
                volume_percentage = (msg.value / 127) * 100
                volume_binary = percentage_to_8bit_binary(volume_percentage)
                binary_code = f'0001{sustain_cycle_binary}{volume_binary}00000000'
                logging.debug(f"24-bit binary code (Volume): {binary_code}")
                print(binary_code)
                send_binary_code_to_uart(binary_code)
            elif msg.control == 64:
                sustain_cycle_binary = get_sustain_cycle_value()

    while True:
        try:
            for msg in midi_in.iter_pending():
                process_midi_message(msg)
        except Exception as e:
            logging.error(f"Error in handle_midi_input: {e}")

def select_midi_input():
    print("MIDI input port list:")
    for port in mido.get_input_names():
        print(port)
   
    selected_port = input("Select a MIDI input port: ")
    return mido.open_input(selected_port)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s')

midi_in = select_midi_input()

midi_thread = threading.Thread(target=handle_midi_input)
midi_thread.start()
