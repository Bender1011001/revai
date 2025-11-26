# Ghidra Export Analysis Report

## 1. Key Data Structures
The analysis identified several critical data structures used for formatting and handling vehicle data. These structures are primarily located in the `com.quadzillapower.iQuad.AVFormatter` package.

### Core Data Classes
- **`AVFormatterData`**: This appears to be the base data holder for formatted values. It likely contains the raw value, a formatted string representation, and potentially flags or status indicators.
- **`AVDTCData224` & `AVDTCData225`**: These classes are specific to Diagnostic Trouble Codes (DTCs). The "224" and "225" suffixes might refer to specific protocol versions or vehicle models (e.g., VP44 vs Common Rail). They contain lists of DTCs.
- **`AVDriveTrainInfoData`**: Stores vehicle configuration details such as:
    - `transmissionID`
    - `rearEndRatio`
    - `vehicleSelection`
    - `numberOfCharacters`

### Formatters
The application uses a variety of formatters to convert raw byte data from the hardware into human-readable formats.
- **`AVBooleanFormatter`**: Handles simple on/off or true/false states.
- **`AVDTCFormatter224` & `AVDTCFormatter225`**: Responsible for parsing the raw DTC byte streams into `AVDTCData` objects.
- **`AVDriveTrainInfoFormatter`**: Parses drivetrain configuration data.
- **`AVNumberFormatter`**: General purpose number formatting.
- **`AVTimeFormatter`**: Likely for engine runtime or other time-based metrics.
- **`AVVehicleSpeedFormatter`**: Handles speed data conversion.
- **`AVThreeCharBooleanFormatter` / `AVTwoCharBooleanFormatter`**: Specialized boolean formatters, possibly for compact displays.

## 2. Communication Protocols
While the export provided a limited view of the communication layer, we identified potential entry points and logic related to data exchange.

### Potential Communication Points
- **`CustomTuningActivity`**: This class seems to handle profile management, which likely involves sending tuning parameters to the hardware.
    - `activateProfile`: Suggests sending a full configuration to the device.
    - `importProfileUri`: Handling external profile files.
- **`CategoryActivity`**:
    - `diagTimerMethod`: This name suggests a periodic polling or diagnostic loop, which is common in OBD-II style communications.

### Protocol Observations
- The `AVFormatter` classes (e.g., `dataFromAV`) take `byte *` (byte arrays) as input. This confirms a binary protocol is used between the Android app and the hardware.
- The parsing logic in `AVDTCFormatter` shows bitwise operations (`& 0xc0`, `& 0x30`, etc.), indicating a packed binary format where specific bits represent flags or values.
- `AVDriveTrainInfoFormatter` uses specific offsets (e.g., `p1[1]`, `p1[2]`) to extract integer values, further confirming a fixed-structure binary packet format.

## 3. Main Application Logic
The application logic appears to be centered around:
1.  **Data Formatting**: A significant portion of the analyzed code is dedicated to converting raw binary data into structured objects (`AVFormatter` classes).
2.  **Tuning Management**: `CustomTuningActivity` indicates features for loading, saving, and activating tuning profiles.
3.  **UI/Display**: `CategoryActivity` and various adapters (`CategoryAttributeAdapter`) suggest a list-based UI for displaying vehicle parameters.

## 4. Challenges for Windows Port
- **Android Dependencies**: The code relies heavily on Android-specific classes:
    - `android.app.Activity` (implied by class names like `CategoryActivity`)
    - `android.widget.BaseAdapter` (implied by `Adapter` suffixes)
    - `java.util.ArrayList` (Standard Java, but heavily used)
    - `Locale` and `NumberFormat` (Standard Java)
- **JNI/Native Libraries**: The presence of `libx2com-jni.so` in the file list (from environment details) strongly suggests that the low-level communication with the hardware is handled in C/C++ via JNI. The Java code we analyzed likely sits on top of this native layer. **Crucially, this native library will need to be recompiled or reverse-engineered for Windows.**
- **UI Rewrite**: The Android UI logic (Activities, Adapters) will need to be completely rewritten for a Windows framework (e.g., WPF, WinForms, or Qt).

## 5. Next Steps
1.  **Analyze Native Library**: The `libx2com-jni.so` file is critical. We need to understand the functions it exports to replicate the communication layer.
2.  **Reconstruct Protocol**: Use the `AVFormatter` logic to document the binary packet structure for all supported parameters.
3.  **Isolate Business Logic**: Separate the pure logic (formatting, data models) from the Android UI code to create a portable core library.