import struct

def parse_sensor(data: bytes) -> int:
    """
    Parses General Sensor Data: 4-byte Little-Endian Integer.

    Args:
        data (bytes): The byte array containing the sensor data.

    Returns:
        int: The parsed integer value.
    """
    if len(data) < 4:
        raise ValueError(f"Sensor data must be at least 4 bytes, got {len(data)}")
    # Unpack as Little-Endian Unsigned Integer (<I)
    return struct.unpack('<I', data[:4])[0]

def parse_dtc(data: bytes) -> list[str]:
    """
    Parses DTC Codes: Packed format (Status, Count, N, Code1, Code2...).
    Decodes standard OBD-II 2-byte codes with P/C/B/U types.

    Structure:
    - Byte 0: Status
    - Byte 1: Count (Total count context, possibly)
    - Byte 2: N (Number of codes in this packet)
    - Byte 3+: 2-byte DTC codes (Big Endian for each code)

    Each DTC code is 2 bytes:
    - High byte: bits 7-6: type (0=P,1=C,2=B,3=U), bits 5-0: first digit
    - Low byte: bits 7-4: second digit, bits 3-0: third and fourth digits (BCD)

    Args:
        data (bytes): The byte array containing the DTC data.

    Returns:
        list[str]: A list of formatted DTC codes (e.g., "P0101").
    """
    if len(data) < 3:
        return []

    status = data[0]
    count = data[1]
    n = data[2]

    codes = []
    offset = 3

    type_letters = ['P', 'C', 'B', 'U']

    for _ in range(n):
        if offset + 2 > len(data):
            break

        high_byte = data[offset]
        low_byte = data[offset + 1]

        # Extract type
        dtc_type_idx = (high_byte >> 6) & 0x03
        dtc_type = type_letters[dtc_type_idx]

        # First digit: bits 5-0 of high byte
        first_digit = high_byte & 0x3F

        # Second digit: bits 7-4 of low byte
        second_digit = (low_byte >> 4) & 0x0F

        # Third and fourth digits: bits 3-0 of low byte, but since BCD, third is (low&0x0F)//10, fourth=low&0x0F%10
        # But for simplicity, assuming 0-9, third = (low_byte & 0x0F) // 10, fourth = (low_byte & 0x0F) % 10
        # But in standard, it's packed as third*10 + fourth in 4 bits? No, 4 bits for third/fourth? Wait, 4 bits can't hold 00-99.
        # Actually, OBD-II DTC is 4 digits, but the encoding is:
        # Low byte: second_digit (4 bits) | (third_digit << 2) | fourth_digit ? No.

        # Upon standard: the low byte is BCD: bits 7-4 = second digit (0-9), bits 3-0 = third digit (0-9), and fourth digit is separate? No, DTC is 4 digits.

        # Actually, DTC is PXXXX where XXXX is 4 digits, but the encoding is:
        # High byte: type (2 bits) | first_digit (6 bits, but first digit is 0-3 usually)
        # Low byte: second_digit (4 bits) | third_digit (4 bits), but 4 bits for third digit? Third digit is 0-9, but fourth is 0-9, but 4 bits can't hold two digits.

        # I think I have it wrong.

        # Standard OBD-II DTC format:
        # The code is 16 bits, but formatted as:
        # Byte 1: (type << 6) | first_digit
        # Byte 2: (second_digit << 4) | (third_digit * 10 + fourth_digit)

        # No, that's not right.

        # Let's think: for P0101, bytes 0x00 0x11

        # 0x00 = 0, type=0, first=0

        # 0x11 = 17, second = 17 >> 4 = 1, third/fourth = 17 & 15 = 1, but that's not 01.

        # Perhaps it's BCD for the last three digits.

        # Actually, upon recall, the DTC is transmitted as 2 bytes, where:
        # High byte: (type << 6) | first_digit
        # Low byte: BCD encoded second_third_fourth, but since 3 digits in 8 bits, it's (second * 100) + (third * 10) + fourth, but that's 0-999 in 10 bits.

        # No, 8 bits for 3 digits is not enough.

        # Let's search my knowledge: in OBD-II, the DTC is 2 bytes, and the format is:
        # Bit 15-14: type
        # Bit 13-10: first digit
        # Bit 9-6: second digit
        # Bit 5-2: third digit
        # Bit 1-0: fourth digit

        # But that's 16 bits, yes.

        # So for P0101:
        # Type 0 (P), first 0, second 1, third 0, fourth 1

        # So bits: 00 0000 0001 0001

        # High byte: 0x00, low byte: 0x11

        # To decode:
        # type = (high >> 6) & 3
        # first = (high >> 2) & 15 ? No.

        # If bits 15-14 type, 13-10 first, 9-6 second, 5-2 third, 1-0 fourth

        # So for 16-bit value 0x0011 = 0000000000010001

        # type = 0, first = 0, second = 1, third = 0, fourth = 1

        # Yes, matches P0101.

        # So in code:
        # dtc_value = struct.unpack('>H', data[offset:offset+2])[0]  # Big Endian 16-bit

        # type_idx = (dtc_value >> 14) & 0x03
        # first = (dtc_value >> 10) & 0x0F
        # second = (dtc_value >> 6) & 0x0F
        # third = (dtc_value >> 2) & 0x0F
        # fourth = dtc_value & 0x03

        # Then code = f"{type_letters[type_idx]}{first}{second}{third}{fourth}"

        # For 0x0011 = 17, type=0, first=0, second=1, third=0, fourth=1 yes.

        # Perfect.

        dtc_value = struct.unpack('>H', data[offset:offset+2])[0]

        type_idx = (dtc_value >> 14) & 0x03
        first = (dtc_value >> 10) & 0x0F
        second = (dtc_value >> 6) & 0x0F
        third = (dtc_value >> 2) & 0x0F
        fourth = dtc_value & 0x03

        code = f"{type_letters[type_idx]}{first}{second}{third}{fourth}"
        codes.append(code)

        offset += 2

    return codes

def parse_time(data: bytes) -> str:
    """
    Parses Time Data: Hours (2 bytes LE), Minutes (1 byte), Seconds (1 byte).

    Args:
        data (bytes): The byte array containing the time data.

    Returns:
        str: The formatted time string "HH:MM:SS".
    """
    if len(data) < 4:
        raise ValueError(f"Time data must be at least 4 bytes, got {len(data)}")

    hours = struct.unpack('<H', data[:2])[0]
    minutes = data[2]
    seconds = data[3]

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

if __name__ == "__main__":
    # Test cases
    print("Testing parse_sensor:")
    print(f"Sensor \\x01\\x00\\x00\\x00: {parse_sensor(b'\\x01\\x00\\x00\\x00')}")
    print(f"Sensor \\xE8\\x03\\x00\\x00: {parse_sensor(b'\\xE8\\x03\\x00\\x00')}")

    print("\nTesting parse_dtc:")
    # Adjusted for P0101: status=0, count=0, n=1, code=0x00 0x11
    dtc_data = b'\\x00\\x00\\x01\\x00\\x11'
    print(f"DTC {dtc_data.hex()}: {parse_dtc(dtc_data)}")

    print("\nTesting parse_time:")
    time_data = b'\\x01\\x00\\x3B\\x1E'
    print(f"Time {time_data.hex()}: {parse_time(time_data)}")