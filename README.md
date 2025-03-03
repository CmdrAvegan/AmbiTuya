<p align="center">
  <img src="https://github.com/user-attachments/assets/141686f4-e568-45af-b43d-11923bb33f2e" alt="AmbiTuya"/>
</p>

<hr>
<p align="center">
  <img src="https://img.shields.io/github/license/cmdravegan/AmbiTuya?color=%23ff4800" alt="License"/>
  <a href="https://github.com/CmdrAvegan/AmbiTuya/releases/tag/AmbiTuya">
    <img src="https://img.shields.io/github/v/release/cmdravegan/AmbiTuya?display_name=release&style=flat&color=%23ff4800" alt="GitHub Release"/>
  </a>
  <img src="https://img.shields.io/github/issues/CmdrAvegan/AmbiTuya?color=%23ff4800" alt="GitHub issues"/>
</p>

<p align="center">
  <strong>AmbiTuya</strong> is a Python-based application that synchronizes your screen's colors with a Tuya-compatible addressable LED strip, creating an immersive ambient lighting experience reminiscent of Ambilight or Govee systems. No coding or Arduino setup is required—AmbiTuya operates entirely over your local network, making it easy to get started and enjoy dynamic, cinema-like lighting effects with minimal effort.
</p>
<br><br><br>

<p align="center">
  <img src="https://github.com/user-attachments/assets/822abba5-183e-4877-9af9-04d7f3c3c6b5" alt="ambituya"/>
</p>

<br><br>
## $${\color{orange}Table \space of \space Contents}$$
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Device Setup](#device-setup)
- [Configuration](#configuration)
- [Basic Settings](#basic-settings)
- [Segment Editor](#segment-editor)
- [Advanced Settings](#advanced-settings)
- [Preventing Device Overload](#preventing-device-overload)
- [Recovering an Unresponsive Device](#recovering-an-unresponsive-device)
- [Error Codes](#error-codes)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

<a id="features" style="display:none;"></a>
## $${\color{orange}Features}$$
- **Device Setup:**  
  - Configure your Tuya device credentials and automatically retrieve device details.
- **Segment Editor:**  
  - Adjust and customize the regions of your screen used for individual LED segments.
- **Real-time Screen Color Syncing:**  
  - Dynamically adjusts LED colors based on your screen content.
- **Multi-monitor Support:**  
  - Capture and sync colors from multiple displays.
- **Letterbox Detection & Color Boost:**  
  - Automatically removes black bars and offers options for uniform brightness and saturation enhancement.
- **Automatic Device Setup:**  
  - Simplifies configuration using the TinyTuya Wizard.

<a id="requirements" style="display:none;"></a>
## $${\color{orange}Requirements}$$
- **Operating System:** Windows-based 64-bit systems (currently, AmbiTuya is not supported on Linux or macOS).
- **Python:** 3.6 or higher
- **Libraries:**
  - [OpenCV](https://opencv.org/) (cv2)
  - [PyQt6](https://riverbankcomputing.com/software/pyqt/intro)
  - [TinyTuya](https://github.com/jasonacox/tinytuya)
  - [mss](https://python-mss.readthedocs.io/)
- **Hardware:**  
  A Tuya-compatible LED strip device with addressable segments (currently supports up to 20 segments).

<a id="installation" style="display:none;"></a>
## $${\color{orange}Installation}$$
**Windows Installer:** A dedicated installer for Windows x64 is available to simplify the setup process.  
If you prefer, you can also manually clone the repository:

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/CmdrAvegan/AmbiTuya
   cd AmbiTuya
   ```
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *Alternatively:*
   ```bash
   pip install opencv-python PyQt6 tinytuya mss
   ```

**C++ Module Compiling and Script Instructions**

**Dependencies**

- OpenCV (Core and ImgProc modules)
- jsoncpp (JSON library, include <json/json.h>)
- RapidJSON
- Windows SDK (for <windows.h>)
- Standard C++ libraries (iostream, vector, sstream, etc.)

AmbiTuya includes a C++ module (with time.cpp and time_bindings.cpp) that handles screen capture and LED control. To compile the module on Windows, follow these steps:

Open a Developer Command Prompt for Visual Studio.

Navigate to the Repository:
```bash
cd AmbiTuya
```

Create and Enter a Build Directory:
```bash
mkdir build
cd build
```

Generate the Visual Studio Solution using CMake:
```bash
cmake -G "Visual Studio 17 2022" -A x64 ..
```

Build the Project in Release Mode:
```bash 
cmake --build . --config Release
```

After successful compilation, the C++ module (e.g., time_bindings.pyd) will be available in the build folder. You can then integrate it with the Python script. For example:
```bash
import time_bindings
```

Process the screen and retrieve JSON output from the C++ module.
```bash
output = time_bindings.process_screen()
print(output)
```
Ensure that the compiled module is in your Python path or the same directory as your Python scripts.

<a id="usage" style="display:none;"></a>
## $${\color{orange}Usage}$$
1. **Run the Application:**
   ```bash
   python time.py
   ```
2. **Configure Your Device:**
   - Open the **Device Setup** tab.
   - Enter your Tuya Device ID, IP, Key, and Version.
   - Click **Save Device Setup** to establish the connection.
   - Alternatively, use the **Automatic Setup** option to configure via the TinyTuya Wizard.
3. **Adjust Settings:**
   - Select the monitor you want to capture.
   - Define and save active screen segments using the Segment Editor and Active Segments Checkboxes.
   - Adjust brightness and color boost options.
   - Click **Start Syncing** to begin the ambient lighting effect.

<a id="device-setup" style="display:none;"></a>
## $${\color{orange}Device \space Setup}$$
To set up your Tuya device:
1. **Create a Tuya Developer Account:**  
   Visit [iot.tuya.com](https://iot.tuya.com) and register.
2. **Create a Cloud Project:**  
   Click the **Cloud** icon and select **Create Cloud Project**. Choose the appropriate Data Center (e.g., `us`, `eu`).
3. **Obtain API Credentials:**  
   In your project overview, copy your **API ID** and **API Secret**.
4. **Link Your Tuya App Account:**  
   Use the QR code provided in the developer portal to link your Smart Life/Tuya app.
5. **Configure in AmbiTuya:**  
   Enter your credentials in the **Automatic Setup** section or manually configure in **Device Setup**.
6. **Save Device Setup**
   Click to reconnect and apply any changes made to the device's setup information.

See **Automatic Setup & Instructions** for more detailed instructions on setting up your device using the TinyTuya Wizard.

> **Note:** The IoT Core service subscription is time-limited. By default, your initial subscription lasts for one month. After expiration, the setup wizard will no longer be able to communicate with your Tuya account, so the subscription must be renewed. As of November 12, 2024, renewals are available for periods of 1, 3, or 6 months. To renew, simply complete a form with some basic details (e.g., the purpose of your project and your developer type).

<a id="configuration" style="display:none;"></a>
## $${\color{orange}Configuration}$$
AmbiTuya stores its settings in several JSON files:
- **settings.json:** General settings (monitor selection, brightness, etc.).
- **segments.json:** Data for active screen segments.
- **segments_inactive.json:** Data for inactive segments.
- **segment_editor_settings.json:** Editor-specific settings (grid size, snap-to-grid options).

<a id="basic-settings" style="display:none;"></a>
## $${\color{orange}Basic \space Settings}$$
The Basic Settings tab provides a user-friendly interface for common functions:
- **Monitor/Screen Selection:**  
  Choose which screen to capture from using the drop-down.
- **Sync Controls:**  
  - **Start Syncing:** Begins syncing your screen’s colors to the device.  
  - **Stop Syncing:** Halts the color synchronization process.
- **Brightness Control:**  
  Enables a uniform brightness level across all colors via a slider.
- **Color Boost:**  
  - **Enable Color Boost:** Activates an additional saturation boost.  
  - **Color Boost Factor:** Adjusts the boost intensity (1.0 means no boost; higher values increase saturation).
- **Threshold Controls:**  
  - **Individual Threshold:** Minimum change in any color channel (RGB) required to trigger an update.  
  - **Distance Threshold:** Overall color difference needed before sending a command.
- **Letterbox Detection:**  
  Automatically detects and crops black letterbox bars from the screen capture.
- **Active Segments:**  
  Select which segments receive color updates by checking/unchecking corresponding boxes.
- **Editing & Mapping:**  
  Opens the Segment Editor for fine-tuning segment positions and sizes.
- **Reset to Defaults:**  
  Quickly restores all Basic Settings to their default values.

<a id="segment-editor" style="display:none;"></a>
## $${\color{orange}Segment \space Editor}$$
The Segment Editor is a useful tool for visually customizing the areas of your screen used for LED color extraction:
- **Visual Editing:**  
  Displays a grid overlay with draggable and resizable rectangles for each LED segment.
- **Adjusting Segments:**  
  Click and drag a segment to reposition or resize it to ensure accurate color mapping.
- **Purpose:**  
  Calibrate the LED display layout, especially useful for non-standard setups.
- **Saving Changes:**  
  Click **Save Changes** to update the segment configuration.

<a id="adding-and-removing-segments" style="display:none;"></a>
## $${\color{orange}Adding \space and \space Removing \space Segments}$$
Manage your active LED segments easily:
- **Removing Segments:**  
  Uncheck a segment's box to disable color updates.
- **Adding Segments:**  
  Check a segment's box to enable it; active segments will be added to the Segment Editor.
- **Segment Limit:**  
  Currently supports a maximum of 20 segments.

<a id="advanced-settings" style="display:none;"></a>
## $${\color{orange}Advanced \space Settings}$$
Customize underlying parameters to optimize performance and command frequency:
- **Max Ping Time:**  
  Maximum ping time (in seconds) for determining sleep intervals. Lower values may cause unresponsiveness.
- **Retries:**  
  Number of retry attempts before giving up on sending a command.
- **Max Sleep Interval:**  
  Maximum time (in seconds) before sending a heartbeat command.
- **Back Off Timer:**  
  Initial back-off time (in seconds) when retrying commands.
- **Reconnect Delay:**  
  Delay (in seconds) after a lost packet before reconnecting.
- **Extra Sleep (Initial & Later):**  
  Additional sleep time (in seconds) to prevent command bursts (e.g., 0.05–0.15 seconds).
- **Max Color Commands:**  
  Limits the number of commands sent without a color change before pausing.
- **Pause Duration:**  
  Duration (in seconds) to pause command processing.
- **No Color Heartbeat:**  
  Time (in seconds) after which a heartbeat command is sent if there’s no color change.
- **Overlay Opacity:**  
  Adjust the opacity of the segment mapping overlay (0.0 for transparent, 1.0 for opaque).
- **Letterbox Threshold:**  
  Sets the maximum brightness for a letterbox to be considered “black.”
- **Theme Selection:**  
  Choose between Light and Dark themes for the interface.

<a id="preventing-device-overload" style="display:none;"></a>
## $${\color{orange}Preventing \space Device \space Overload}$$
Sending too many commands too quickly can overload your device. To prevent this:
- **Increase the Sleep Interval:**  
  In Advanced Settings, adjust the **Max Sleep Interval** (e.g., 0.2–1 second) to reduce command frequency.
- **Adjust Color Thresholds:**  
  - Increase the **Individual Threshold** so minor changes do not trigger updates.
  - Increase the **Distance Threshold** to require a significant color change before sending a command.
- **Enable Extra Sleep:**  
  Set **Extra Sleep (Initial)** and **Extra Sleep (Later)** to small positive values (e.g., 0.05–0.15 seconds) to avoid command bursts.
- **Reduce Active Segments:**  
  Disable some segments in Basic Settings if the device struggles with performance.

<a id="recovering-an-unresponsive-device" style="display:none;"></a>
## $${\color{orange}Recovering \space an \space Unresponsive \space Device}$$
If your device becomes unresponsive:
- **Unplug and Replug the Device:**  
  Disconnect the device from power for 3–5 seconds, then reconnect.
- **Reconnect the Device:**  
  Go to the Device Setup tab, verify your device details, and click **Save Device Setup** to force a reconnection.
- **Reduce Command Frequency:**  
  Adjust Advanced Settings to lower the rate of command updates.

<a id="error-codes" style="display:none;"></a>
## $${\color{orange}Error \space Codes}$$
- **Error 901:**  
  Indicates a network connectivity issue. Verify your network connection and ensure your computer and device are on the same network.
- **Error 905:**  
  Suggests a problem with device information. Check the Device Setup tab to ensure the correct Device ID, IP, and other details are entered.
- **Error 914:**  
  Means the Device Key or Version might be incorrect. Revisit the Device Setup tab and verify these details.

<a id="troubleshooting" style="display:none;"></a>
## $${\color{orange}Troubleshooting}$$
- **Device Connection:**  
  If your device is not detected, verify the device settings under the Device Setup tab. Ensure that your computer and device are on the same network. If you re-pair your device, the Device Key may change—rerun the Automatic Setup to update your credentials.
- **Display Issues:**  
  Confirm that the correct monitor is selected in `settings.json`.
- For additional support, consult the [TinyTuya Documentation](https://github.com/jasonacox/tinytuya).

<a id="contributing" style="display:none;"></a>
## $${\color{orange}Contributing}$$
Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Implement your changes.
4. Submit a pull request with a detailed description of your updates.

<a id="license" style="display:none;"></a>
## $${\color{orange}License}$$
This project is licensed under the [MIT License](LICENSE).

<a id="acknowledgments" style="display:none;"></a>
## $${\color{orange}Acknowledgments}$$
- [TinyTuya](https://github.com/jasonacox/tinytuya) for the Tuya communication library.
- [PyQt6](https://riverbankcomputing.com/software/pyqt/intro) for the GUI framework.
- [OpenCV](https://opencv.org/) for powerful image processing.
- [mss](https://python-mss.readthedocs.io/) for efficient cross-platform screen capture.

<!-- Tuya, Ambilight, LED Sync, Smart Home, TinyTuya, Python, Screen Capture, Home Automation, Tuya Ambilight Github, Tuya Govee, Github, Tuya LED Ambient Lighting -->
