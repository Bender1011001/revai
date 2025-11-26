# iQuad Protocol Specification

## 1. Overview
This document defines the communication protocol used by the Quadzilla iQuad hardware. The protocol specification is derived from the reverse engineering of the Android `libx2com-jni.so` library and the associated Java `AVFormatter` classes. This protocol is used to communicate between the client application (Android/Windows) and the iQuad hardware module via a binary stream (likely Bluetooth SPP or similar serial connection).

## 2. JNI Interface
The following native methods were identified in `libx2com-jni.so` and serve as the primary interface for the application to interact with the hardware.

| Method Name | Java Signature | Description |
| :--- | :--- | :--- |
| `sendCmd` | `(I[B)V` | Sends a command to the hardware. Takes an integer command ID and a byte array payload. |
| `readData` | `()[B` | Reads a generic data packet from the hardware. Returns a byte array. |
| `getCanData` | `()[B` | Reads CAN bus data. Returns a byte array. |
| `getDtcData` | `()[B` | Reads Diagnostic Trouble Code (DTC) data. Returns a byte array. |
| `getVersion` | `()Ljava/lang/String;` | Retrieves the library or firmware version string. |

## 3. Data Packet Structures

### 3.1 General Sensor Data
Sensor values are typically transmitted as 4-byte Little-Endian integers.

*   **Format:** 4 bytes
*   **Endianness:** Little-Endian (`<I` in Python struct format)
*   **Conversion Formula:**
    To convert the raw integer value to a human-readable float:
    ```
    DisplayValue = (RawValue * Multiplier) + Offset
    ```
    *Note: Multipliers and offsets are specific to each sensor type (e.g., EGT, Boost, RPM) and are defined in the application's `AVFormatter` logic.*

### 3.2 DTC Data (Diagnostic Trouble Codes)
DTC data is transmitted in a packed binary format containing a header and a list of 2-byte codes.

*   **Structure:**
    *   **Byte 0:** Status (Flags indicating system status)
    *   **Byte 1:** Count (Total count context)
    *   **Byte 2:** N (Number of codes in this packet)
    *   **Byte 3+:** List of N * 2-byte DTC codes

*   **DTC Code Format (2 Bytes):**
    Each DTC is encoded in 16 bits (Big Endian).
    *   **Bits 15-14:** Type (0=P, 1=C, 2=B, 3=U)
    *   **Bits 13-10:** First Digit (0-9)
    *   **Bits 9-6:** Second Digit (0-9)
    *   **Bits 5-2:** Third Digit (0-9)
    *   **Bits 1-0:** Fourth Digit (0-9)

*   **Decoding Logic:**
    ```python
    # Python Example
    dtc_value = (byte1 << 8) | byte2
    type_idx = (dtc_value >> 14) & 0x03
    first = (dtc_value >> 10) & 0x0F
    second = (dtc_value >> 6) & 0x0F
    third = (dtc_value >> 2) & 0x0F
    fourth = dtc_value & 0x03
    
    code_string = f"{['P','C','B','U'][type_idx]}{first}{second}{third}{fourth}"
    ```

### 3.3 Time Data
Time data (e.g., engine runtime) is transmitted as a 4-byte structure.

*   **Format:**
    *   **Bytes 0-1:** Hours (Little-Endian unsigned short)
    *   **Byte 2:** Minutes (Unsigned byte)
    *   **Byte 3:** Seconds (Unsigned byte)

*   **Display Format:** `HH:MM:SS`

## 4. Implementation Guide (C# Porting)

When porting this protocol to C# for the Windows client, developers should adhere to the following guidelines:

### 4.1 Serial Communication
*   Use `System.IO.Ports.SerialPort` for communication if the device appears as a COM port (standard for Bluetooth SPP).
*   Ensure the baud rate and parity settings match the hardware requirements (typically 9600 or 115200, 8N1, but requires verification).

### 4.2 Endianness Handling
*   The protocol uses **Little-Endian** for integer values (Sensor Data, Time Hours).
*   The protocol uses **Big-Endian** for packed DTC codes.
*   C# `BitConverter` uses the system endianness (usually Little-Endian on Windows).
    *   For Little-Endian fields: Use `BitConverter.ToInt32()` or `BitConverter.ToUInt16()` directly.
    *   For Big-Endian fields (DTCs): You must reverse the byte order before using `BitConverter`, or manually shift bits as shown in the decoding logic.

### 4.3 BinaryReader Extensions
It is recommended to create extension methods for `BinaryReader` to handle the specific data types:

```csharp
public static class BinaryReaderExtensions
{
    public static int ReadInt32LE(this BinaryReader reader)
    {
        return reader.ReadInt32(); // Standard Little-Endian
    }

    public static string ReadDTC(this BinaryReader reader)
    {
        byte b1 = reader.ReadByte();
        byte b2 = reader.ReadByte();
        ushort val = (ushort)((b1 << 8) | b2); // Big-Endian
        
        // ... Implement bitwise decoding logic here ...
    }
}