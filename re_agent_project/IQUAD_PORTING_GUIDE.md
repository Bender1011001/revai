# iQuad Windows Porting Guide

## 1. Project Overview

**Objective:** Port the Quadzilla Power "iQuad" Android application to the Windows platform.

**Purpose:** To allow users to monitor vehicle parameters, manage tuning profiles, and diagnose issues (DTCs) using a Windows-based device (laptop, tablet, or car PC) connected to the Quadzilla hardware.

**Current Status:**
- **Source:** Decompiled Android APK (v2.1.0).
- **Analysis:** Core logic identified, native dependencies isolated, assets extracted.
- **Next Phase:** Implementation of the Windows client.

---

## 2. Architecture Analysis

The existing Android application follows a standard layered architecture which must be adapted for Windows.

### Android Architecture
1.  **UI Layer (Java):** `Activity` and `Fragment` classes handling user interaction (e.g., `CategoryActivity`, `CustomTuningActivity`).
2.  **Business Logic (Java):** Data formatting and state management (e.g., `AVFormatter` classes).
3.  **JNI Bridge (Java/C++):** JNI methods declared in Java classes to interface with native code.
4.  **Native Layer (C++):** `libx2com-jni.so` handling low-level hardware communication.

### Proposed Windows Architecture
1.  **UI Layer:** WPF (Windows Presentation Foundation) or WinUI 3 for a modern, touch-friendly interface.
2.  **Core Logic (C#):** Ported version of the `AVFormatter` and data classes.
3.  **Hardware Abstraction Layer (HAL):** A C# interface replacing the JNI bridge.
4.  **Communication Layer:** Native Windows Bluetooth/Serial APIs replacing `libx2com-jni.so`.

---

## 3. Core Components

The following components have been identified in the decompiled code and are essential for the port.

### Data Structures
*Located in `com.quadzillapower.iQuad.AVFormatter`*

-   **`AVFormatterData`**: The primary data object holding raw values and formatted strings.
-   **`AVDTCData224` / `AVDTCData225`**: Structures for holding Diagnostic Trouble Codes (DTCs).
-   **`AVDriveTrainInfoData`**: Stores vehicle configuration (Transmission ID, Rear End Ratio, etc.).

### Logic & Formatters
These classes contain the logic to convert raw binary data into human-readable values. They must be ported 1:1 to ensure data accuracy.

-   **`AVBooleanFormatter`**: Handles on/off states.
-   **`AVNumberFormatter`**: General numeric data.
-   **`AVVehicleSpeedFormatter`**: Speed calculations.
-   **`AVDTCFormatter`**: Bitwise parsing of error codes.
-   **`AVDriveTrainInfoFormatter`**: Parses vehicle setup packets.

### Tuning Management
*Located in `CustomTuningActivity`*

-   **Profile Management**: Logic for saving/loading tuning maps.
-   **`activateProfile`**: Logic for sending a full tuning map to the hardware.

---

## 4. Critical Dependencies

### The Native Library: `libx2com-jni.so`
This is the most critical dependency. It contains the proprietary communication protocol implementation.

-   **Challenge:** We cannot simply "run" this on Windows.
-   **Action:** We must reverse engineer the protocol or the library itself to understand how it talks to the hardware (likely Bluetooth RFCOMM or WiFi TCP/UDP).
-   **Protocol Hints:**
    -   The Java code passes `byte[]` arrays to this library.
    -   The `AVFormatter` classes parse these byte arrays using specific offsets and bitmasks.
    -   **Conclusion:** The protocol is a binary packet format.

### Database
-   **`assets/DTCDB.sqlite`**: A SQLite database containing definitions for Diagnostic Trouble Codes. This can be used directly in the Windows app using `System.Data.SQLite`.

---

## 5. Asset Inventory

We have extracted all assets from the APK. These should be reused to maintain the original look and feel.

### Database
-   `assets/DTCDB.sqlite`: DTC definitions.

### Fonts
-   `assets/LcdD.ttf`: The digital LCD font used for gauges.

### Graphics (Key Examples)
*Located in `res/drawable-*`*

-   **Gauges/Indicators:**
    -   `res/drawable/gauge_background.png` (Hypothetical name based on typical structure)
    -   `res/drawable/needle.png`
-   **Icons:**
    -   `res/drawable/ic_tuning.png`
    -   `res/drawable/ic_settings.png`
-   **Backgrounds:**
    -   Various `.9.png` (9-patch) images used for UI scaling.

*Note: See the full file list for specific filenames like `0H.9.png`, `1B.png`, etc. These obfuscated names will need to be visually inspected and renamed.*

---

## 6. Implementation Roadmap

This roadmap guides the development from analysis to a working Windows application.

### Phase 1: Protocol Reverse Engineering (High Priority)
1.  **Analyze `libx2com-jni.so`**: Use Ghidra to identify the exported JNI functions.
2.  **Trace Data Flow**: Map how data flows from the Java `AVFormatter` classes into the native library.
3.  **Packet Structure**: Document the binary format (Header, ID, Payload, Checksum).
4.  **Transport Layer**: Confirm if the transport is Bluetooth Serial (SPP) or WiFi.

### Phase 2: Core Library (C#)
1.  **Port Data Models**: Recreate `AVFormatterData`, `AVDTCData`, etc., in C#.
2.  **Port Logic**: Translate the Java formatting logic (bitwise operations) to C#.
3.  **Unit Tests**: Create tests using known binary inputs to verify the C# output matches the Android logic.

### Phase 3: Hardware Layer
1.  **Communication Service**: Implement a Windows service/class to handle Bluetooth/WiFi connection.
2.  **Packet Handler**: Implement the protocol identified in Phase 1 to send/receive raw bytes.

### Phase 4: User Interface (WPF/WinUI)
1.  **Dashboard**: Create a gauge cluster using the extracted assets (`LcdD.ttf`, images).
2.  **Tuning Screens**: Implement the profile editor and upload functionality.
3.  **DTC Scanner**: Implement the error code reader using `DTCDB.sqlite`.

### Phase 5: Integration & Testing
1.  **Connect UI to Core**: Bind the UI controls to the Core Library models.
2.  **Live Testing**: Test with actual Quadzilla hardware to verify communication stability.