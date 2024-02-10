import sys
import uuid
import struct
import pyjson5 
import re
import string

def decode_length(file):
    """
    Decode the length encoded in two bytes according to the specified scheme.
    
    Args:
    - byte1: The first byte as an integer.
    - byte2: The second byte as an integer.
    
    Returns:
    - The decoded length as an integer.
    """

    byte1 = file.read(1)[0]
    if byte1 & 0b10000000:  # Check if the highest bit is set
        # Combine the bits from byte1 (excluding the highest bit) and byte2
        byte2 = file.read(1)[0]
        actual_length = (byte1 & 0b01111111) | (byte2 << 7)
    else:
        actual_length = byte1  # Use byte1 directly if the highest bit isn't set
    
    return actual_length

def decode_length_manual(byte1, byte2):
    """
    Decode the length encoded in two bytes according to the specified scheme.
    
    Args:
    - byte1: The first byte as an integer.
    - byte2: The second byte as an integer.
    
    Returns:
    - The decoded length as an integer.
    """
    if byte1 & 0b10000000:  # Check if the highest bit is set
        # Combine the bits from byte1 (excluding the highest bit) and byte2
        actual_length = (byte1 & 0b01111111) | (byte2 << 7)
    else:
        actual_length = byte1  # Use byte1 directly if the highest bit isn't set
    
    return actual_length

def read_until_marker(file, marker):
    """Reads file content until a specific marker is found. Returns the content up to (but not including) the marker."""
    content = b''
    marker_length = len(marker)
    read_bytes = 0
    while True:
        byte = file.read(1)
        read_bytes = read_bytes + 1
        if not byte:
            # End of file reached without finding the marker
            break
        content += byte
        # Check if the last part of content matches the marker
        if content[-marker_length:] == marker:
            # Remove the marker from the content before returning
            content = content[:-marker_length]
            break
    return read_bytes, content

def debug_bytes_to_string(byte_data):
    """Convert bytes to two debug strings: colored hex representation and printable characters.
    Non-printables and whitespace (except spaces) are replaced with ':', spaces remain unchanged."""
    hex_output = []  # For hex representation
    char_output = []  # For printable characters, with specific replacements for non-printables
    
    # ANSI color codes
    green = '\033[92m'  # Printable
    blue = '\033[94m'  # Whitespace
    red = '\033[91m'  # Non-printable
    reset = '\033[0m'  # Reset color
    
    for byte in byte_data:
        color = red  # Assume non-printable by default
        
        if chr(byte) in string.printable:
            if chr(byte) == ' ':
                color = green  # Keep spaces green (printable)
            elif chr(byte) in string.whitespace:
                color = blue  # Color other whitespace blue
                char_output.append(':')
                hex_output.append(f"{color}{byte:02x}{reset}")
                continue
            else:
                color = green  # Other printable characters
            char_output.append(chr(byte))
        else:
            char_output.append(':')
        
        hex_output.append(f"{color}{byte:02x}{reset}")
    
    # Join the parts into a single string for each representation
    hex_string = " ".join(hex_output) + f" {reset}({len(byte_data)} bytes)"
    char_string = "".join(char_output)
    
    return hex_string, char_string

def parse_json_from_file(file):
    prelude_bytes = b''  # To accumulate prelude data
    json_str = ''  # Initialize an empty string to accumulate JSON data
    depth = 0  # Keep track of the depth of nested objects
    in_json = False  # Flag to indicate whether we've encountered the opening brace
    prelude = ''  # To store prelude as string or hex string

    while True:
        byte = file.read(1)  # Read one byte at a time

        if not byte:
            # End of file reached
            break

        if not in_json and byte != b'{':
            prelude_bytes += byte
            continue

        if byte == b'{':
            if not in_json:  # Capture the prelude data
                try:
                    prelude = prelude_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    prelude = prelude_bytes.hex()  # Use hex if not UTF-8 decodable
            in_json = True
            depth += 1
        elif byte == b'}':
            depth -= 1

        if in_json:
            # Accumulate the JSON string
            json_str += byte.decode('utf-8')  # Safely decode
            #json_str += byte.decode('utf-8', errors='replace')  # Safely decode

        if in_json and depth == 0:
            # All braces are matched; the JSON object is complete
            break

    prelude_hex, prelude_chars = debug_bytes_to_string(prelude_bytes)

    return prelude_bytes, prelude_hex, prelude_chars, json_str 

def read_json_blob(file):
    json_length = decode_length(file)
    json = file.read(json_length).decode('utf-8')
    return json

def read_text(file):
    length = decode_length(file)
    return file.read(length).decode('utf-8')

def read_uuid(file):
    # Read the next 32 ASCII characters for the UUID-like hexadecimal value
    hex_uuid = file.read(32)
    if len(hex_uuid) < 32:
        print("File does not contain enough data for a hex UUID.")
        return
    
    # Convert ASCII bytes to string
    hex_str = hex_uuid.decode('ascii')
    # Inserting hyphens to match the UUID format
    formatted_uuid_str = f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"
    try:
        # Attempt to create a UUID object from the formatted string
        extracted_uuid = uuid.UUID(formatted_uuid_str)
        return extracted_uuid
    except ValueError as e:
        print(f"Error interpreting extracted data as UUID: {e}")
    return ""

def peek(f, length=1):
    pos = f.tell()
    data = f.read(length) # Might try/except this line, and finally: f.seek(pos)
    f.seek(pos)
    return data

def parse_header(file):
    # Read the first 4 bytes as an offset
    magic_number_bytes = file.read(4)

    if len(magic_number_bytes) == 4:
        magic_number = struct.unpack('<I', magic_number_bytes)[0]  # '<I' specifies little-endian unsigned int
        if magic_number != 0xa18f40a:
            print("Magic Number wrong, got ", hex(magic_number))
            return
    else:
        print("file to short")
        return 

    
    # Expecting a separator byte (0x20)
    separator = file.read(1)
    if separator != b'\x20':
        print("Expected separator not found.")
        return
    print("Separator found.")

    # Read the next 32 ASCII characters for the UUID-like hexadecimal value
    hex_uuid = file.read(32)
    if len(hex_uuid) < 32:
        print("File does not contain enough data for a hex UUID.")
        return
    
    # Convert ASCII bytes to string
    hex_str = hex_uuid.decode('ascii')
    # Inserting hyphens to match the UUID format
    formatted_uuid_str = f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"
    try:
        # Attempt to create a UUID object from the formatted string
        extracted_uuid = uuid.UUID(formatted_uuid_str)
        print(f"Extracted UUID: {extracted_uuid}")
    except ValueError as e:
        print(f"Error interpreting extracted data as UUID: {e}")

    # lets continue decoding the rest of the file
    unknown_data = file.read(15)
    
    #marker = b'\x31\x32'  # Marker to look for after "Pilot"
    #read_bytes, content = read_until_marker(file, marker)
    #print(f"Read {read_bytes} bytes until marker.")

    length = decode_length(file)
    print("name length: ", length)

    name = file.read(length).decode('utf-8')
    print("name: " + name)

    for i in range(0, 12):
        marker = file.read(1)[0]

        print("marker: ", hex(marker))
        match marker:
            case 0x0a:
                subcmd = file.read(1)[0]
                match subcmd:
                    case 0x20: # uuid
                        uuid = read_uuid(file)
                        print("uuid: ", uuid)
                    case 0x02: # unknown
                        file.read(6) #03 a8 02 01 ba 02
            case 0x3a:
                json = read_json_blob(file)
                print("json: ", json)
            case 0x40:
                file.read(1)
                file.read(4)
                file.read(4)
                file.read(1)
                file.read(1)
            case 0x5a:
                json = read_json_blob(file)
                print("json: ", json)
            case 0x62:
                json = read_json_blob(file)
                print("json: ", json)
            case 0x6a:
                json = read_json_blob(file)
                print("json: ", json)
            case 0x72:
                json = read_json_blob(file)
                print("json: ", json)
            case 0x78:
                file.read(18)
                json = read_json_blob(file)
                print("json: ", json)
            case 0xb5:
                file.read(4)
                file.read(1)
            case 0xbd:
                file.read(4)
                file.read(1)
            case 0xc2:
                file.read(1)
                length = decode_length(file)
                unknown = file.read(length).decode('utf-8')
                print("unknown: ", unknown)
            case 0xd0:
                unknown = file.read(5)
                if peek(file, 1)[0] == 0x80:
                    unknown = file.read(5)
                    if peek(file, 1)[0] == 0x01:
                        file.read(1)
            case 0xaa:
                file.read(1)
                length = decode_length(file)
                unknown = file.read(length).decode('utf-8')
            case 0x10:
                file.read(6) # unknown
            case 0x18:
                file.read(4) # unknown
            case 0xb7:
                file.read(2) # 0x31 0x32
                length = decode_length(file)

            case _:
                print("unknown marker: ", hex(marker))

        print("")

def debug_content(file):
    for i in range(0, 100):
        # Parse the first JSON object
        prelude_bytes, prelude_hex, prelude_chars, first_json = parse_json_from_file(file)
        if first_json is not None:
            print("prelude:", prelude_hex)
            print("", prelude_chars)
            print("JSON object length:", len(first_json))
            if len(prelude_bytes) > 2:
                print("decoded: ", decode_length_manual(prelude_bytes[1], prelude_bytes[2]))
            print("")

def hex_format(data):
    return " ".join([f"{byte:02x}" for byte in data])

def parse_note_tree(f):
    start = f.read(5)
    assert(start[0] == 0x0a)
    assert(start[3] == 0x0a)
    assert(start[4] == 0x20)
    uuid = read_uuid(f)

    block = f.read(15)
    print("block: ", hex_format(block))
    assert(block[13] == 0x31, hex_format(block))
    if block[14] == 0x22:
        assert(f.read(1)[0] == 0x20)
        uuid = read_uuid(f)
        print("unknown uuid: ", uuid)
        assert(f.read(1)[0] == 0x32)
    else:
        assert(block[14] == 0x32, hex_format(block))

    print("peek: ", hex_format(peek(f, 10)))
    name = read_text(f)

    print("uuid: ", uuid)
    print("name: ", name)
    
    assert(f.read(1)[0] == 0x3a)

    active_scene = read_json_blob(f)
    print("json: ", active_scene)

    # 0x40
    assert(f.read(1)[0] == 0x40)
    f.read(1)
    f.read(4)
    f.read(4)
    f.read(1)
    f.read(1)


    # 0x5a
    assert(f.read(1)[0] == 0x5a)
    json = read_json_blob(f)
    print("json: ", json)

    assert(f.read(1)[0] == 0x62)
    json = read_json_blob(f)
    print("json: ", json)

    assert(f.read(1)[0] == 0x6a)
    json = read_json_blob(f)
    print("json: ", json)

    assert(f.read(1)[0] == 0x72)
    json = read_json_blob(f)
    print("json: ", json)

    assert(f.read(1)[0] == 0x78)
    f.read(18)
    json = read_json_blob(f)
    print("json: ", json)

    # differs
    assert(f.read(1)[0] == 0xaa)
    f.read(1)
    json = read_json_blob(f)
    print("json: ", json)

    # 0xb5
    assert(f.read(1)[0] == 0xb5)
    f.read(4)
    f.read(1)

    # 0xbd
    assert(f.read(1)[0] == 0xbd)
    f.read(4)
    f.read(1)

    # 0xc2
    assert(f.read(1)[0] == 0xc2)
    f.read(1)
    length = decode_length(f)
    unknown = f.read(length).decode('utf-8')
    print("unknown: ", unknown)

    # 0xd0
    assert(f.read(1)[0] == 0xd0)
    unknown = f.read(5)
    if peek(f, 1)[0] == 0x80:
        unknown = unknown + f.read(5)
        if peek(f, 1)[0] == 0x01:
            unknown = unknown + f.read(1)
    unknown = unknown + f.read(8)
    expected_end = bytes([0xa0, 0x02, 0x03, 0xa8, 0x02, 0x01, 0xba, 0x02])
    assert unknown[-len(expected_end):] == expected_end, f"unknown does not end with the expected byte sequence {unknown.hex()}"

    #a0 73 68 61 72 65 5f 75 73 65 72
    expected = bytes([0x0a, 0x73, 0x68, 0x61, 0x72, 0x65, 0x5f, 0x75, 0x73, 0x65, 0x72])
    unknown = f.read(11)

    if peek(f, 1)[0] != 0x0a:
        f.read(3) # this is optional, could differ in size, we don't know

    assert unknown == expected, f"unknown does not end with the expected byte sequence. \nExpected: {expected.hex()}\nActual:   {unknown.hex()}"

    next_start = peek(f, 5)
    print("next start: ", next_start.hex())
    print("")


def parse_file_for_offset_and_hex_uuid(file_path, debug):
    try:
        with open(file_path, 'rb') as file:

            if debug:
                debug_content(file)
            else:
                #parse_header(file)

                while True:
                    parse_note_tree(file)

    except IOError as e:
        print(f"Error reading file {file_path}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <path_to_binary_file>")
    else:
        parse_file_for_offset_and_hex_uuid(sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == "-d")
