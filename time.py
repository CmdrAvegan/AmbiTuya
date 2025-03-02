import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QLabel, QSlider, QWidget, QDialog, QCheckBox, QGraphicsView, QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem, QDoubleSpinBox, QSpinBox, QScrollArea, QGroupBox, QHBoxLayout, QGraphicsItem, QSizePolicy, QMessageBox, QTabWidget, QFormLayout, QLineEdit, QDialogButtonBox, QComboBox, QTextEdit, QSplashScreen
from PyQt6.QtGui import QColor, QImage, QPixmap, QPainter, QPen, QBrush, QPainterPath, QFont, QIcon, QTextFormat
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint, QSize, QRectF, QPointF, QSizeF, QUrl, QTimer
import tinytuya
import subprocess
import json
import time
import mss
import numpy as np
import time_bindings  # Import the compiled C++ module
import logging
import threading

# Save the original __init__ method
_original_outlet_init = tinytuya.OutletDevice.__init__

# Define a new __init__ that overrides the retry parameters.
def patched_outlet_init(self, dev_id, address, local_key, connection_timeout=5, connection_retry_limit=5, connection_retry_delay=5, *args, **kwargs):
    # Call the original __init__ with modified values.
    return _original_outlet_init(
        self,
        dev_id,
        address,
        local_key,
        connection_timeout=1,
        connection_retry_limit=1,
        connection_retry_delay=0.5,
        *args,
        **kwargs
    )

# Monkey-patch the __init__ of OutletDevice.
tinytuya.OutletDevice.__init__ = patched_outlet_init

# Save the original status() method.
_original_status = tinytuya.OutletDevice.status

def patched_status(self, *args, **kwargs):
    result = _original_status(self, *args, **kwargs)
    # Check if the status response has the error.
    if (isinstance(result, dict) and 
        result.get("Error") == "Network Error: Device Unreachable" and 
        str(result.get("Err")) == "905"):
        # Stop further connection by raising an exception.
        raise Exception("Device Unreachable (905) – ")
    return result

# Monkey-patch the status method so that the error stops the connection.
tinytuya.OutletDevice.status = patched_status

# Resource path for PyInstaller helper
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Custom logging handler that updates the splash screen
class SplashScreenHandler(logging.Handler):
    def __init__(self, splash):
        super().__init__()
        self.splash = splash
        # Use a formatter that only outputs the message.
        self.setFormatter(logging.Formatter("%(message)s"))
        
    def emit(self, record):
        try:
            msg = self.format(record)
            # Shorten the splash screen's message if it's too wide.
            fm = self.splash.fontMetrics()
            max_width = self.splash.size().width() - 20  # leave a small margin
            elided_msg = fm.elidedText(msg, Qt.TextElideMode.ElideRight, max_width)
            self.splash.showMessage(elided_msg,
                                    Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                                    Qt.GlobalColor.white)
            QApplication.processEvents()
        except Exception:
            self.handleError(record)

class SetupInstructionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tuya Device Setup Instructions")
        self.resize(750, 600)

        main_layout = QVBoxLayout(self)

        # Create a scroll area to hold the instructions and screenshots
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        content_layout = QVBoxLayout(content_widget)

        # Title
        title = QLabel("<h3>How to Set Up Your Tuya Device for AmbiTuya</h3>", self)
        title.setTextFormat(Qt.TextFormat.RichText)
        content_layout.addWidget(title)

        # Define the steps
        steps = [
            """
            <head>
                <style>
                    body { font-family: Arial, sans-serif; font-size: 14px; }
                    h2 { color: #ff4800; }
                    h3 { color: #ff4800; }
                    a { color: #ff4800; }
                </style>
            </head>
            <b>Create a Tuya Developer Account:</b><br>
            Go to <a href='https://iot.tuya.com'>iot.tuya.com</a> and create a developer account. 
            When prompted for the 'Account Type', you can choose to skip this step if available.""",
            """<b>Create a Cloud Project:</b><br>
            Click on the 'Cloud' icon and select 'Create Cloud Project'. 
            Make sure to pick the correct Data Center (Region) for your location. 
            This region will be used by TinyTuya to connect to your devices.""",
            """<b>Obtain API Credentials:</b><br>
            After creating your project, navigate to the 'Project Overview' page. 
            Here you will find your <i><u>API ID</u></i> and <i><u>API Secret</u></i>. 
            Copy these values, as you will need to enter them in the fields provided in this program.""",
            """<b>Link Your Tuya App Account:</b><br>
            Within your cloud project, click on the 'Cloud' icon and select 'Devices'. 
            Then click on 'Link Tuya App Account'. You will see a dialog pop-up with two options: 
            choose 'Automatic' and 'Read Only Status'. This will generate a QR code.""",
            """<b>Pair Your Device:</b><br>
            Open the Smart Life app on your phone. Go to the 'Me' tab and tap the QR code button 
            in the upper right corner to scan the QR code displayed by the developer portal. 
            This links your app account with the cloud project, so your device appears on the portal.""",
            """<b>Subscribe to Required APIs:</b><br>
            Under the 'Service API' tab in your cloud project, ensure that the following APIs are enabled: 
            <i>IoT Core</i> and <i>Authorization</i>. If they are not enabled, click the 'Go to Authorize' button, 
            select the appropriate API groups, and subscribe. (Note: The subscription for IoT Core initially lasts one month 
            and will need to be renewed.)""",
            """<b>Enter Your Credentials in the Program:</b><br>
            Return to this program and select 'Run Automatic Setup' then enter your Tuya API ID, API Secret, and select the correct region. 
            Then click on the 'Ok' button to retrieve your device information automatically."""
        ]

        # For each step, add the instruction text and then a screenshot image between steps
        for index, step_html in enumerate(steps, start=1):
            step_label = QLabel(step_html, self)
            step_label.setWordWrap(True)
            step_label.setTextFormat(Qt.TextFormat.RichText)
            content_layout.addWidget(step_label)

            # Load and add the screenshot image
            screenshot_path = resource_path(os.path.join("screenshots", f"step{index}.png"))
            if os.path.exists(screenshot_path):
                screenshot_label = QLabel(self)
                pixmap = QPixmap(screenshot_path)
                # Scale image to a fixed width while preserving aspect ratio
                pixmap = pixmap.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation)
                screenshot_label.setPixmap(pixmap)
                screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                content_layout.addWidget(screenshot_label)

            # Add a little spacing after each step
            content_layout.addSpacing(10)

        # Add note
        note_label = QLabel(
            """
            <head>
                <style>
                    body { font-family: Arial, sans-serif; font-size: 14px; }
                    h2 { color: #ff4800; }
                    h3 { color: #ff4800; }
                    a { color: #ff4800; }
                </style>
            </head>
            <b>Note:</b><br>
            If you re-pair your device, the Device Key will change and you will need to run the Automatic Setup again to get the new key.<br>
            <p>If you encounter any issues, please refer to the TinyTuya documentation at 
            <a href='https://github.com/jasonacox/tinytuya'>https://github.com/jasonacox/tinytuya</a> for more details.</p>""",
            self)
        note_label.setWordWrap(True)
        note_label.setTextFormat(Qt.TextFormat.RichText)
        content_layout.addWidget(note_label)

        # Add the scroll area to the main layout
        main_layout.addWidget(scroll_area)

        # Add a close button at the bottom
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.accept)
        main_layout.addWidget(close_button)

        self.setLayout(main_layout)

class DeviceSelectionDialog(QDialog):
    def __init__(self, devices, parent=None):
        """
        devices: A list of dictionaries, each representing a device.
                 Each dictionary includes keys like 'id', 'name', 'ip', 'key', 'version', etc.
        """
        super().__init__(parent)
        self.setWindowTitle("Select a Device")
        self.selected_device = None

        layout = QVBoxLayout(self)

        # Inform the user to select a device.
        info_label = QLabel("Multiple devices were found. Please select one to use:")
        layout.addWidget(info_label)

        # Create a combo box to list the devices.
        self.device_combo = QComboBox(self)
        for device in devices:
            # Use the device name if available; otherwise, fall back to its ID.
            device_name = self.device.get("name", self.device.get("id", "Unknown Device"))
            display_str = (
                f"{device_name} "
                f"(IP: {self.device.get('ip', 'N/A')}, "
                f"Version: {self.device.get('version', '3.5')})"
            )
            # Store the full device dictionary.
            self.device_combo.addItem(display_str, device)
        layout.addWidget(self.device_combo)

        # Add OK and Cancel buttons.
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_device(self):
        """Return the device dictionary stored in the current combo box item."""
        return self.device_combo.currentData()

class WizardInputDialog(QDialog):
    def __init__(self, parent=None, saved_credentials=None):
        """
        saved_credentials: Dictionary with 'api_key', 'api_secret', 'api_region'
        """
        super().__init__(parent)
        self.setWindowTitle("Enter Tuya API Credentials")
        layout = QFormLayout(self)
        self.resize(375, 150)

        # Create QLineEdits for API Key and Secret
        self.api_key_edit = QLineEdit(self)
        self.api_secret_edit = QLineEdit(self)
        layout.addRow("Tuya API Key:", self.api_key_edit)
        self.api_secret_edit.setToolTip("Enter your Tuya API Secret from (https://iot.tuya.com) Project Overview page.")
        layout.addRow("Tuya API Secret:", self.api_secret_edit)
        self.api_key_edit.setToolTip("Enter your Tuya API Key from (https:// iot.tuya.com) Project Overview page.")
        # Create a dropdown (QComboBox) for selecting a region
        self.api_region_dropdown = QComboBox(self)
        self.api_region_dropdown.addItems(["cn", "us", "us-e", "eu", "eu-w", "in"])
        self.api_region_dropdown.setToolTip(
            "Select your Tuya API region:\n"
            "  cn   - China Data Center\n"
            "  us   - US - Western America Data Center\n"
            "  us-e - US - Eastern America Data Center\n"
            "  eu   - Central Europe Data Center\n"
            "  eu-w - Western Europe Data Center\n"
            "  in   - India Data Center"
        )
        layout.addRow("Tuya Region:", self.api_region_dropdown)

        # Add "Save Credentials" checkbox
        self.save_credentials_checkbox = QCheckBox("Save credentials")
        layout.addRow(self.save_credentials_checkbox)

        # Prefill fields if saved API info exists
        if saved_credentials:
            self.api_key_edit.setText(saved_credentials.get("api_key", ""))
            self.api_secret_edit.setText(saved_credentials.get("api_secret", ""))
            self.api_region_dropdown.setCurrentText(saved_credentials.get("api_region", ""))
            self.save_credentials_checkbox.setChecked(True)

        # Add OK and Cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_inputs(self):
        """Return the user inputs as a dictionary."""
        return {
            "api_key": self.api_key_edit.text().strip(),
            "api_secret": self.api_secret_edit.text().strip(),
            "api_region": self.api_region_dropdown.currentText().strip(),
            "save_credentials": self.save_credentials_checkbox.isChecked(),
        }


        ########################
        #    SEGMENT EDITOR    #
        ########################

INACTIVE_SEGMENTS_FILE = "segments_inactive.json"

def load_inactive_segments():
    """Load the inactive segments data from file."""
    if os.path.exists(INACTIVE_SEGMENTS_FILE):
        try:
            with open(INACTIVE_SEGMENTS_FILE, "r") as file:
                return json.load(file)
        except (json.JSONDecodeError, IOError):
            pass
    # Return an empty dict if file does not exist or fails to load.
    return {}

def save_inactive_segments(inactive_data):
    """Save the inactive segments data to file."""
    try:
        with open(INACTIVE_SEGMENTS_FILE, "w") as file:
            json.dump(inactive_data, file, indent=4)
    except IOError as e:
        print(f"Error saving inactive segments: {e}")

class SegmentEditor(QMainWindow):
    SETTINGS_FILE = "segment_editor_settings.json"  # file for editor settings

    def __init__(self, device, active_segments, segment_data_file="segments.json", screen_size=None):
        super().__init__()
        self.setWindowTitle("Segment Editor")
        self.unsaved_changes = False  # Tracks if changes were made
        self.setWindowIcon(QIcon(resource_path("icons/editor_icon.png")))
        # Use the active_segments list passed in (or a default if none provided)
        if active_segments and len(active_segments) > 0:
            self.segment_numbers = active_segments
        else:
            self.segment_numbers = list(range(1, 21))  # default to segments 1 to 20

        # Load the segments data
        self.segment_data_file = segment_data_file
        self.segment_data = self.load_segments()
        self.device = device
        
        # Determine the screen size
        if screen_size is None:
            screen_size = QApplication.primaryScreen().size()
        self.screen_width, self.screen_height = screen_size.width(), screen_size.height()

        # Create the scene and view
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene, self)
        self.view.setRenderHints(self.view.renderHints() | QPainter.RenderHint.Antialiasing)
        self.view.setSceneRect(0, 0, self.screen_width, self.screen_height)

        # Grid setup
        self.grid_size = 50  # Adjustable grid size
        self.grid_items = []  # will hold grid line items
        self.draw_grid()

        self.init_segments()

        # Create Save Changes button
        save_button = QPushButton("Save Changes")
        save_button.clicked.connect(self.save_segments)

        save_button.setFixedHeight(30)
        save_button.setMinimumWidth(200)
        save_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Create Snap to Grid checkbox (default unchecked)
        self.snap_checkbox = QCheckBox("Snap to Grid")
        self.snap_checkbox.setChecked(False)

        # Create Grid Size spinbox to allow for grid size adjustments.
        grid_label = QLabel("|  Grid Size:")
        self.grid_spinbox = QSpinBox()
        self.grid_spinbox.setRange(5, 200)
        self.grid_spinbox.setSingleStep(1)
        self.grid_spinbox.setValue(self.grid_size)
        self.grid_spinbox.valueChanged.connect(self.on_grid_size_changed)

        self.segment_info_label = QLabel(" ")
        self.segment_info_label.setMinimumWidth(250)

        # Create the Grid controls in a sub-layout
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(5)
        grid_layout.addWidget(grid_label)
        grid_layout.addWidget(self.grid_spinbox)

        # Create the main bottom layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.snap_checkbox)      

        button_layout.addLayout(grid_layout)

        # Insert a stretch to push the Save Changes button into the center.
        button_layout.addStretch(1)
        button_layout.addWidget(save_button)

        # Insert another stretch so that the Save Changes button remains centered.
        button_layout.addStretch(1)
        button_layout.addWidget(self.segment_info_label)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.view)
        main_layout.addLayout(button_layout)

        # Create a central widget, set its layout, and assign it to the window
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Load editor settings
        self.load_settings()

        # Show the window maximized
        self.showMaximized()

    def update_selected_segment_info(self):
        selected_item = None
        # Look for a segment that is selected.
        for seg, item in self.segment_items.items():
            if item.isSelected():
                selected_item = item
                break

        if selected_item is not None:
            pos = selected_item.scenePos()
            rect = selected_item.rect()
            self.segment_info_label.setText(
                f"Segment {selected_item.segment_id}:    X: {pos.x():.0f}, Y: {pos.y():.0f}. "
                f"  W: {rect.width():.0f}, H: {rect.height():.0f}"
            )
        else:
            self.segment_info_label.setText(" ")

    def on_grid_size_changed(self, new_size):
        """Called when the grid size spinbox value changes."""
        self.grid_size = new_size
        self.draw_grid()

    def draw_grid(self):
        """Draws a grid aligned with the center of the screen.
        Clears any existing grid lines first."""
        # Remove existing grid lines from the scene.
        for item in self.grid_items:
            self.scene.removeItem(item)
        self.grid_items.clear()

        # Define pens: one for regular grid lines, one for the center line.
        grid_pen = QPen(QColor(150, 150, 150, 150))
        grid_pen.setWidth(1)
        center_pen = QPen(QColor(120, 120, 120, 200))
        center_pen.setWidth(2)

        # Get center of the scene.
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2

        # figure out how many lines needed to go left and right from the center.
        n_min = -((center_x) // self.grid_size) - 1
        n_max = ((self.screen_width - center_x) // self.grid_size) + 1

        for n in range(n_min, n_max + 1):
            x = center_x + n * self.grid_size
            # Only draw if within the scene boundaries.
            if 0 <= x <= self.screen_width:
                pen = center_pen if n == 0 else grid_pen
                line = self.scene.addLine(x, 0, x, self.screen_height, pen)
                self.grid_items.append(line)

        n_min = -((center_y) // self.grid_size) - 1
        n_max = ((self.screen_height - center_y) // self.grid_size) + 1

        for n in range(n_min, n_max + 1):
            y = center_y + n * self.grid_size
            if 0 <= y <= self.screen_height:
                pen = center_pen if n == 0 else grid_pen
                line = self.scene.addLine(0, y, self.screen_width, y, pen)
                self.grid_items.append(line)

    def load_settings(self):
        """Load grid size and snap-to-grid checkbox state from a settings file."""
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, "r") as file:
                    settings = json.load(file)
                self.grid_size = settings.get("grid_size", 30)
                snap_state = settings.get("snap_to_grid", True)
                self.snap_checkbox.setChecked(snap_state)
                self.grid_spinbox.setValue(self.grid_size)
                #print("Loaded settings:", settings)    # DEBUG
            except Exception as e:
                print("Error loading settings:", e)
        else:
            print("No settings file found; using defaults.")

    def save_settings(self):
        """Save grid size and snap-to-grid checkbox state to a settings file."""
        settings = {
            "grid_size": self.grid_size,
            "snap_to_grid": self.snap_checkbox.isChecked()
        }
        try:
            with open(self.SETTINGS_FILE, "w") as file:
                json.dump(settings, file, indent=4)
            #print("Saved settings:", settings)   # DEBUG
        except Exception as e:
            print("Error saving settings:", e)

    def load_segments(self):
        try:
            with open(self.segment_data_file, "r") as file:
                data = json.load(file)
            # Ensure that all segments in self.segment_numbers have a record. (Only active segments are in segments.json.)
            for segment in self.segment_numbers:
                str_segment = str(segment)
                if str_segment not in data:
                    # If a segment is not in active data, ignore it. (Its geometry will be stored in segments_inactive.json)
                    pass
                else:
                    for key in ("x", "y", "width", "height"):
                        if key not in data[str_segment]:
                            data[str_segment][key] = 0 if key in ("x", "y") else 100
            return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            #print(f"Error loading segment data: {e}")      # DEBUG
            # Only return data for segments that are active (with default values)
            return {str(segment): {"x": 0, "y": 0, "width": 100, "height": 100}
                    for segment in self.segment_numbers}

    def save_segments(self):
        """Saves segment data and marks changes as saved."""
        new_segment_data = {}
        for segment, rect_item in self.segment_items.items():
            rect = rect_item.rect()
            pos = rect_item.scenePos()
            new_segment_data[str(segment)] = {
                "x": pos.x(),
                "y": pos.y(),
                "width": rect.width(),
                "height": rect.height(),
            }
        try:
            with open(self.segment_data_file, "w") as file:
                json.dump(new_segment_data, file, indent=4)
            self.unsaved_changes = False  # Reset flag after saving
            #print("Saved data:", new_segment_data)     # DEBUG
        except IOError as e:
            print(f"Error saving segment data: {e}")

    def update_labels_after_load(self):
        for segment, rect_item in self.segment_items.items():
            rect = rect_item.rect()
            pos = rect_item.pos()  # Get the position of the rect item in its parent (not scene position)
            label_x = pos.x() + rect.width() / 2 - rect_item.label.boundingRect().width() / 2
            label_y = pos.y() + rect.height() / 2 - rect_item.label.boundingRect().height() / 2
            rect_item.label.setPos(label_x, label_y)
            #print(f"Label updated to actual position for segment {segment}: {label_x}, {label_y}")     # DEBUG

    def init_segments(self):
        self.segment_items = {}
        for segment in self.segment_numbers:
            data = self.segment_data[str(segment)]
            x, y = data["x"], data["y"]
            width, height = data["width"], data["height"]
            #print(f"Initializing segment {segment} at position ({x}, {y}) with size ({width}, {height})")      # DEBUG
            rect_item = ResizableRect(QRectF(x, y, width, height), segment, self)
            rect_item.setBrush(QBrush(QColor(255, 72, 0, 100)))
            rect_item.setPen(QPen(Qt.GlobalColor.black, 1.0))
            rect_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            rect_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
            rect_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
            self.scene.addItem(rect_item)
            self.segment_items[segment] = rect_item
            #print(f"Initialized segment {segment} at position ({x}, {y}) with size ({width}, {height})")       # DEBUG
            self.update_labels_after_load()
        self.reset_segment_positions()

    def reset_segment_positions(self):
        for segment, rect_item in self.segment_items.items():
            data = self.segment_data[str(segment)]
            x, y = data["x"], data["y"]
            rect_item.setPos(x, y)
            rect_item.setRect(QRectF(0, 0, rect_item.rect().width(), rect_item.rect().height()))
            #print(f"Reset segment {segment} to position ({x}, {y}) with size ({rect_item.rect().width()}, {rect_item.rect().height()})")       # DEBUG
            scene_x, scene_y = rect_item.scenePos().x(), rect_item.scenePos().y()
            #print(f"Scene position for segment {segment}: ({scene_x}, {scene_y})")     # DEBUG

    def snap_to_grid(self, position, snap_size, max_size):
        snapped = round(position / snap_size) * snap_size
        return max(0, min(snapped, max_size))

    def update_segment_data(self):
        """Updates segment data and marks changes as unsaved."""
        self.segment_data = {}
        for segment, rect_item in self.segment_items.items():
            rect = rect_item.rect()
            pos = rect_item.scenePos()
            self.segment_data[str(segment)] = {
                "x": pos.x(),
                "y": pos.y(),
                "width": rect.width(),
                "height": rect.height(),
            }
        self.unsaved_changes = True  # Changes detected
        #print("Segments updated:", self.segment_data)      # DEBUG

    def closeEvent(self, event):
        """Intercept the close event to ask if the user wants to save first."""
        # Ensure grid size and snap-to-grid settings are saved before closing.
        self.save_settings()

        if self.unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.save_segments()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()  # Close without saving segment changes
            else:
                event.ignore()  # Cancel closing
        else:
            event.accept()  # No unsaved segment changes, close normally


class ResizableRect(QGraphicsRectItem):
    def __init__(self, rect, segment_id, parent):
        super().__init__(rect)
        self.segment_id = segment_id
        self.parent = parent
        self.label = QGraphicsTextItem(f"Segment {segment_id}", self)
        self.label.setDefaultTextColor(Qt.GlobalColor.black)
        self.update_label_position()
        self.setBrush(QBrush(Qt.GlobalColor.red))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.resizing = False
        self.resize_direction = None
        self.resize_start_pos = QPointF()
        self.original_rect = QRectF()
        self.snap_value = 10  # Snap value for both moving and resizing
        self.min_size = QSizeF(20, 20)  # Minimum width and height

    def hoverMoveEvent(self, event):
        rect = self.rect()
        margin = 10
        pos = event.pos()
                # Check for corners first
        if pos.x() <= rect.left() + margin and pos.y() <= rect.top() + margin:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.resize_direction = "top-left"
            return
        elif pos.x() >= rect.right() - margin and pos.y() <= rect.top() + margin:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            self.resize_direction = "top-right"
            return
        elif pos.x() <= rect.left() + margin and pos.y() >= rect.bottom() - margin:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            self.resize_direction = "bottom-left"
            return
        elif pos.x() >= rect.right() - margin and pos.y() >= rect.bottom() - margin:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.resize_direction = "bottom-right"
            return

        if rect.left() <= event.pos().x() <= rect.left() + margin:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.resize_direction = 'left'
        elif rect.right() - margin <= event.pos().x() <= rect.right():
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.resize_direction = 'right'
        elif rect.top() <= event.pos().y() <= rect.top() + margin:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.resize_direction = 'top'
        elif rect.bottom() - margin <= event.pos().y() <= rect.bottom():
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            self.resize_direction = 'bottom'
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.resize_direction = None

    def mousePressEvent(self, event):
        # Bring this item to the front.
        self.setZValue(100)
        rect = self.rect()
        margin = 10
        if (rect.left() <= event.pos().x() <= rect.left() + margin or
            rect.right() - margin <= event.pos().x() <= rect.right() or
            rect.top() <= event.pos().y() <= rect.top() + margin or
            rect.bottom() - margin <= event.pos().y() <= rect.bottom()):
            self.resizing = True
            self.resize_start_pos = event.pos()
            self.original_rect = QRectF(self.rect())
            # Record fixed boundaries based on the resize direction.
            if self.resize_direction in ['left', 'top-left', 'bottom-left']:
                self.fixed_right = self.scenePos().x() + rect.width()
            if self.resize_direction in ['top', 'top-left', 'top-right']:
                self.fixed_bottom = self.scenePos().y() + rect.height()
            if self.resize_direction in ['right', 'top-right', 'bottom-right']:
                self.fixed_left = self.scenePos().x()
            if self.resize_direction in ['bottom', 'bottom-left', 'bottom-right']:
                self.fixed_top = self.scenePos().y()
            # Deselect all other segments so this one is exclusively selected.
            for seg, item in self.parent.segment_items.items():
                if item is not self:
                    item.setSelected(False)
            self.setSelected(True)
        else:
            self.resizing = False

            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            new_rect = QRectF(self.original_rect)  # copy the original rect
            grid_enabled = self.parent.snap_checkbox.isChecked()
            grid_size = self.parent.grid_size

            if self.resize_direction == 'right':
                # Get the new right edge in local coordinates.
                new_right_local = event.pos().x()
                # Convert to scene coordinate.
                scene_right = self.scenePos().x() + new_right_local
                if grid_enabled:
                    center_x = self.parent.screen_width // 2
                    snapped_scene_right = center_x + round((scene_right - center_x) / grid_size) * grid_size
                else:
                    snapped_scene_right = scene_right
                # Clamp so that the the segment does not extend past the screen.
                snapped_scene_right = min(snapped_scene_right, self.parent.screen_width)
                # Ensure minimum width.
                min_scene_right = self.scenePos().x() + self.min_size.width()
                snapped_scene_right = max(snapped_scene_right, min_scene_right)
                # The new width is the snapped scene right minus the current scene x-position.
                new_width = snapped_scene_right - self.scenePos().x()
                new_rect.setWidth(new_width)

            elif self.resize_direction == 'bottom':
                new_bottom_local = event.pos().y()
                scene_bottom = self.scenePos().y() + new_bottom_local
                if grid_enabled:
                    center_y = self.parent.screen_height // 2
                    snapped_scene_bottom = center_y + round((scene_bottom - center_y) / grid_size) * grid_size
                else:
                    snapped_scene_bottom = scene_bottom
                snapped_scene_bottom = min(snapped_scene_bottom, self.parent.screen_height)
                min_scene_bottom = self.scenePos().y() + self.min_size.height()
                snapped_scene_bottom = max(snapped_scene_bottom, min_scene_bottom)
                new_height = snapped_scene_bottom - self.scenePos().y()
                new_rect.setHeight(new_height)

            elif self.resize_direction == 'left':
                # event.scenePos() is already in scene coordinates.
                new_left_scene = event.scenePos().x()
                if grid_enabled:
                    center_x = self.parent.screen_width // 2
                    snapped_new_left = center_x + round((new_left_scene - center_x) / grid_size) * grid_size
                else:
                    snapped_new_left = new_left_scene
                snapped_new_left = max(snapped_new_left, 0)
                new_width = self.fixed_right - snapped_new_left
                if new_width < self.min_size.width():
                    new_width = self.min_size.width()
                    snapped_new_left = self.fixed_right - new_width
                self.setPos(QPointF(snapped_new_left, self.scenePos().y()))
                new_rect = QRectF(0, 0, new_width, self.original_rect.height())

            elif self.resize_direction == 'top':
                new_top_scene = event.scenePos().y()
                if grid_enabled:
                    center_y = self.parent.screen_height // 2
                    snapped_new_top = center_y + round((new_top_scene - center_y) / grid_size) * grid_size
                else:
                    snapped_new_top = new_top_scene
                snapped_new_top = max(snapped_new_top, 0)
                new_height = self.fixed_bottom - snapped_new_top
                if new_height < self.min_size.height():
                    new_height = self.min_size.height()
                    snapped_new_top = self.fixed_bottom - new_height
                self.setPos(QPointF(self.scenePos().x(), snapped_new_top))
                new_rect = QRectF(0, 0, self.original_rect.width(), new_height)

            #   Diagonal (Corner) Resizing
            elif self.resize_direction == 'top-left':
                new_left_scene = event.scenePos().x()
                new_top_scene = event.scenePos().y()
                if grid_enabled:
                    center_x = self.parent.screen_width // 2
                    new_left_scene = center_x + round((new_left_scene - center_x) / grid_size) * grid_size
                    center_y = self.parent.screen_height // 2
                    new_top_scene = center_y + round((new_top_scene - center_y) / grid_size) * grid_size
                new_left_scene = max(new_left_scene, 0)
                new_top_scene = max(new_top_scene, 0)
                new_width = self.fixed_right - new_left_scene
                new_height = self.fixed_bottom - new_top_scene
                if new_width < self.min_size.width():
                    new_width = self.min_size.width()
                    new_left_scene = self.fixed_right - new_width
                if new_height < self.min_size.height():
                    new_height = self.min_size.height()
                    new_top_scene = self.fixed_bottom - new_height
                self.setPos(QPointF(new_left_scene, new_top_scene))
                new_rect = QRectF(0, 0, new_width, new_height)

            elif self.resize_direction == 'top-right':
                new_right_scene = event.scenePos().x()
                new_top_scene = event.scenePos().y()
                if grid_enabled:
                    center_x = self.parent.screen_width // 2
                    new_right_scene = center_x + round((new_right_scene - center_x) / grid_size) * grid_size
                    center_y = self.parent.screen_height // 2
                    new_top_scene = center_y + round((new_top_scene - center_y) / grid_size) * grid_size
                new_right_scene = min(new_right_scene, self.parent.screen_width)
                new_top_scene = max(new_top_scene, 0)
                new_width = new_right_scene - self.fixed_left
                new_height = self.fixed_bottom - new_top_scene
                if new_width < self.min_size.width():
                    new_width = self.min_size.width()
                    new_right_scene = self.fixed_left + new_width
                if new_height < self.min_size.height():
                    new_height = self.min_size.height()
                    new_top_scene = self.fixed_bottom - new_height
                self.setPos(QPointF(self.fixed_left, new_top_scene))
                new_rect = QRectF(0, 0, new_width, new_height)

            elif self.resize_direction == 'bottom-left':
                new_left_scene = event.scenePos().x()
                new_bottom_scene = event.scenePos().y()
                if grid_enabled:
                    center_x = self.parent.screen_width // 2
                    new_left_scene = center_x + round((new_left_scene - center_x) / grid_size) * grid_size
                    center_y = self.parent.screen_height // 2
                    new_bottom_scene = center_y + round((new_bottom_scene - center_y) / grid_size) * grid_size
                new_left_scene = max(new_left_scene, 0)
                new_bottom_scene = min(new_bottom_scene, self.parent.screen_height)
                new_width = self.fixed_right - new_left_scene
                new_height = new_bottom_scene - self.fixed_top
                if new_width < self.min_size.width():
                    new_width = self.min_size.width()
                    new_left_scene = self.fixed_right - new_width
                if new_height < self.min_size.height():
                    new_height = self.min_size.height()
                    new_bottom_scene = self.fixed_top + new_height
                self.setPos(QPointF(new_left_scene, self.fixed_top))
                new_rect = QRectF(0, 0, new_width, new_height)

            elif self.resize_direction == 'bottom-right':
                new_right_scene = event.scenePos().x()
                new_bottom_scene = event.scenePos().y()
                if grid_enabled:
                    center_x = self.parent.screen_width // 2
                    new_right_scene = center_x + round((new_right_scene - center_x) / grid_size) * grid_size
                    center_y = self.parent.screen_height // 2
                    new_bottom_scene = center_y + round((new_bottom_scene - center_y) / grid_size) * grid_size
                new_right_scene = min(new_right_scene, self.parent.screen_width)
                new_bottom_scene = min(new_bottom_scene, self.parent.screen_height)
                new_width = new_right_scene - self.fixed_left
                new_height = new_bottom_scene - self.fixed_top
                if new_width < self.min_size.width():
                    new_width = self.min_size.width()
                    new_right_scene = self.fixed_left + new_width
                if new_height < self.min_size.height():
                    new_height = self.min_size.height()
                    new_bottom_scene = self.fixed_top + new_height
                self.setPos(QPointF(self.fixed_left, self.fixed_top))
                new_rect = QRectF(0, 0, new_width, new_height)

            self.setRect(new_rect)
            self.parent.update_segment_data()
            self.update_label_position()
            self.parent.update_selected_segment_info()
        else:
            super().mouseMoveEvent(event)
            if self.parent.snap_checkbox.isChecked():
                self.snap_to_grid()
            self.update_label_position()
            self.parent.update_selected_segment_info()

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.parent.update_segment_data()
        else:
            super().mouseReleaseEvent(event)
            if self.parent.snap_checkbox.isChecked():
                self.snap_to_grid()
        self.setPos(self.scenePos())
        self.update_label_position()
        self.parent.update_selected_segment_info()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.parent.unsaved_changes = True  # Mark changes as unsaved
            if value:  # the item is now selected
                self.setZValue(100)
                if not self.parent.device:
                    QMessageBox.warning(self.parent, "Error", "Device not initialized!")
                else:
                    selected_seg = self.segment_id
                    # Command codes to highlight selected segment.
                    orange_codes = {
                        1: "AAIAFAEAEAPoA+iBFA==",
                        2: "AAIAFAEAEAPoA+iBEw==",
                        3: "AAIAFAEAEAPoA+iBEg==",
                        4: "AAIAFAEAEAPoA+iBEQ==",
                        5: "AAIAFAEAEAPoA+iBEA==",
                        6: "AAIAFAEAEAPoA+iBDw==",
                        7: "AAIAFAEAEAPoA+iBDg==",
                        8: "AAIAFAEAEAPoA+iBDQ==",
                        9: "AAIAFAEAEAPoA+iBDA==",
                        10: "AAIAFAEAEAPoA+iBCw==",
                        11: "AAIAFAEAEAPoA+iBCg==",
                        12: "AAIAFAEAEAPoA+iBCQ==",
                        13: "AAIAFAEAEAPoA+iBCA==",
                        14: "AAIAFAEAEAPoA+iBBw==",
                        15: "AAIAFAEAEAPoA+iBBg==",
                        16: "AAIAFAEAEAPoA+iBBQ==",
                        17: "AAIAFAEAEAPoA+iBBA==",
                        18: "AAIAFAEAEAPoA+iBAw==",
                        19: "AAIAFAEAEAPoA+iBAg==",
                        20: "AAIAFAEAEAPoA+iBAQ=="
                    }
                    black_codes = {
                        1: "AAIAFAEAAAAAAACBFA==",
                        2: "AAIAFAEAAAAAAACBEw==",
                        3: "AAIAFAEAAAAAAACBEg==",
                        4: "AAIAFAEAAAAAAACBEQ==",
                        5: "AAIAFAEAAAAAAACBEA==",
                        6: "AAIAFAEAAAAAAACBDw==",
                        7: "AAIAFAEAAAAAAACBDg==",
                        8: "AAIAFAEAAAAAAACBDQ==",
                        9: "AAIAFAEAAAAAAACBDA==",
                        10: "AAIAFAEAAAAAAACBCw==",
                        11: "AAIAFAEAAAAAAACBCg==",
                        12: "AAIAFAEAAAAAAACBCQ==",
                        13: "AAIAFAEAAAAAAACBCA==",
                        14: "AAIAFAEAAAAAAACBBw==",
                        15: "AAIAFAEAAAAAAACBBg==",
                        16: "AAIAFAEAAAAAAACBBQ==",
                        17: "AAIAFAEAAAAAAACBBA==",
                        18: "AAIAFAEAAAAAAACBAw==",
                        19: "AAIAFAEAAAAAAACBAg==",
                        20: "AAIAFAEAAAAAAACBAQ=="
                    }
                    commands = {}
                    # For the selected segment, send the orange command:
                    commands[f"61_{selected_seg}"] = orange_codes[selected_seg]
                    # For every active segment (from segment_items) that's not selected, send the black command:
                    for seg in self.parent.segment_items:
                        if seg != selected_seg:
                            commands[f"61_{seg}"] = black_codes[seg]
                    # Also include inactive segments from file:
                    inactive_data = load_inactive_segments()  # call the global function
                    for seg_str in inactive_data.keys():
                        seg = int(seg_str)
                        if f"61_{seg}" not in commands:
                            commands[f"61_{seg}"] = black_codes[seg]
                    payload = self.parent.device.generate_payload(tinytuya.CONTROL, commands)
                    self.parent.device._send_receive(payload)
                if hasattr(self.parent, "sendBlackToInactiveSegments"):
                    self.parent.sendBlackToInactiveSegments()
            else:
                self.setZValue(0)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            newPos = value  # new position is a QPointF
            rect = self.rect()
            if newPos.x() < 0:
                newPos.setX(0)
            elif newPos.x() + rect.width() > self.parent.screen_width:
                newPos.setX(self.parent.screen_width - rect.width())
            if newPos.y() < 0:
                newPos.setY(0)
            elif newPos.y() + rect.height() > self.parent.screen_height:
                newPos.setY(self.parent.screen_height - rect.height())
            return newPos
        return super().itemChange(change, value)




    def shape(self):
        path = QPainterPath()
        rect = self.rect()
        margin = 5
        inflated_rect = rect.adjusted(-margin, -margin, margin, margin)

        # Pass individual coordinates to addRect to avoid negative width/height
        path.addRect(inflated_rect.x(), inflated_rect.y(), inflated_rect.width(), inflated_rect.height())

        return path

    def snap_to_grid(self):
        rect = self.rect()
        grid_size = self.parent.grid_size
        center_x = self.parent.screen_width // 2
        center_y = self.parent.screen_height // 2
        
        new_x = center_x + round((self.x() - center_x) / grid_size) * grid_size
        new_y = center_y + round((self.y() - center_y) / grid_size) * grid_size
        
        new_x = max(0, min(new_x, self.parent.screen_width - rect.width()))
        new_y = max(0, min(new_y, self.parent.screen_height - rect.height()))
        
        self.setPos(new_x, new_y)
        self.snap_to_adjacent_segments()
        self.update_label_position()

    def snap_to_adjacent_segments(self):
        rect = self.rect()
        for item in self.parent.scene.items():
            if isinstance(item, ResizableRect) and item != self:
                other_rect = item.rect()
                if abs(rect.right() - other_rect.left()) <= self.snap_value:
                    rect.setRight(other_rect.left())
                elif abs(rect.left() - other_rect.right()) <= self.snap_value:
                    rect.setLeft(other_rect.right())
                elif abs(rect.bottom() - other_rect.top()) <= self.snap_value:
                    rect.setBottom(other_rect.top())
                elif abs(rect.top() - other_rect.bottom()) <= self.snap_value:
                    rect.setTop(other_rect.bottom())
        self.setRect(rect)
        self.update_label_position()

    def update_label_position(self):
        rect = self.rect()
        label_x = rect.x() + rect.width() / 2 - self.label.boundingRect().width() / 2
        label_y = rect.y() + rect.height() / 2 - self.label.boundingRect().height() / 2
        label_x = max(min(label_x, self.parent.screen_width - self.label.boundingRect().width()), 0)
        label_y = max(min(label_y, self.parent.screen_height - self.label.boundingRect().height()), 0)
        self.label.setPos(label_x, label_y)




        ########################
        #    SEGMENT DISPLAY   #
        ########################

def get_available_monitors():
    with mss.mss() as sct:
        monitors = sct.monitors  # List of all monitors (first entry is the virtual full-screen)
    return monitors[1:]  # Skip the first entry (it's the full virtual screen)

class SegmentDisplayDialog(QDialog):
    def __init__(self, active_segments=None, overlay_opacity=0.5, monitor_index=1):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icons/main_icon.png")))
        self.setWindowTitle("Segment Visualization")
        
        # Store the monitor index.
        self.monitor_index = monitor_index

        # Determine the selected monitor's resolution.
        import mss
        with mss.mss() as sct:
            monitors = sct.monitors
            if self.monitor_index < 1 or self.monitor_index >= len(monitors):
                self.monitor_index = 1
            mon = monitors[self.monitor_index]
            mon_width = mon["width"]
            mon_height = mon["height"]

        # Set the dialog size to a fixed width, adjusting height to match the monitor's aspect ratio.
        desired_width = 800
        desired_height = int(desired_width * mon_height / mon_width)
        self.resize(desired_width, desired_height)
        # Always keep this window on top.
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)

        # Load active_segments (falling back to file if necessary)
        if active_segments is None:
            try:
                with open('segments.json', 'r') as f:
                    active_segments = json.load(f)
            except Exception as e:
                active_segments = {}

        # Check for segment file; if none found, inform the user.
        if not active_segments:
            QMessageBox.information(
                self,
                "No Segments Found",
                "No segments have been saved. Please create segments before attempting to view them."
            )
            self.close()
            return

        self.active_segments = active_segments

        # Store the captured screen as a QPixmap.
        self.original_screen = None
        self.overlay_opacity = overlay_opacity

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.refresh_capture()


    def refresh_capture(self):
        """Capture the screen of the selected monitor and store it as a scaled QPixmap."""
        with mss.mss() as sct:
            monitors = sct.monitors
            if self.monitor_index < 1 or self.monitor_index >= len(monitors):
                self.monitor_index = 1
            screen = sct.grab(monitors[self.monitor_index])
            frame = np.array(screen)
            # Convert BGRA to RGB.
            frame = frame[:, :, :3][:, :, ::-1]
            h, w, _ = frame.shape
            qimage = QImage(frame.tobytes(), w, h, 3 * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)
            # Scale the captured image to the dialog's size while keeping aspect ratio.
            self.original_screen = pixmap.scaled(
                self.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
        self.update()

    def paintEvent(self, event):
        """Draw the captured screen and overlay the segment mapping."""
        painter = QPainter(self)
        if self.original_screen is not None:
            painter.drawPixmap(self.rect(), self.original_screen)
        if self.active_segments:
            for seg_id, seg_data in self.active_segments.items():
                x = seg_data.get("x", 0)
                y = seg_data.get("y", 0)
                width = seg_data.get("width", 100)
                height = seg_data.get("height", 100)
                hue = (int(seg_id) * 150) % 360
                color = QColor.fromHsv(hue, 200, 255, int(255 * self.overlay_opacity))
                painter.setBrush(QBrush(color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(int(x), int(y), int(width), int(height))
                painter.setPen(QColor(0, 0, 0, 200))
                painter.drawRect(int(x), int(y), int(width), int(height))
                painter.setPen(Qt.GlobalColor.black)
                font = QFont("Arial", 12, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(int(x), int(y), int(width), int(height),
                                 Qt.AlignmentFlag.AlignCenter, f"Segment {seg_id}")


        ########################
        #    CALL C++ MODULE   #
        ########################

def call_cpp_processor():
    try:
        output = time_bindings.process_screen()
        ##print("C++ Output:", output)      # DEBUG
        return json.loads(output)
    except json.JSONDecodeError as e:
        #print(f"JSONDecodeError: {e}")     # DEBUG
        return {"commands": {}}
    except Exception as e:
        #print(f"Error calling C++ function: {e}")      # DEBUG
        return {"commands": {}}
    
class Worker(QThread):
    stop_signal = pyqtSignal()
    errorOccurred = pyqtSignal(str)  # For reporting errors to the main thread

    def __init__(self, callback, device, reconnect_callback):
        super().__init__()
        self.callback = callback
        self._running = True
        self.sleep_interval = 0.1  # Default sleep interval (in seconds)
        self.device = device
        self.reconnect_callback = reconnect_callback

    def run(self):
        while self._running:
            try:
                self.callback()
                # Run device.status in a separate thread so it won’t block forever.
                result = [None]
                def call_status():
                    try:
                        result[0] = self.device.status()
                    except Exception as ex:
                        result[0] = ex
                t = threading.Thread(target=call_status)
                t.start()
                t.join(timeout=0.5)
                if t.is_alive():
                    raise Exception("Device Unreachable (905) - status call timeout")
                if isinstance(result[0], Exception):
                    raise result[0]
                if (isinstance(result[0], dict) and 
                    ("Network Error" in (result[0].get("Error") or "") and 
                    ("905" in str(result[0].get("Err")) or "901" in str(result[0].get("Err"))))):
                    raise Exception("Device Error (" + str(result[0].get("Err")) + ") .")
            except Exception as e:
                error_message = str(e)
                if "905" in error_message or "901" in error_message:
                    self.errorOccurred.emit(error_message)
                    self._running = False
                    break
                else:
                    self.reconnect_callback()
            time.sleep(self.sleep_interval)

    def stop(self):
        self._running = False





        ########################
        #    MAIN WINDOW APP   #
        ########################

class ColorPicker(QMainWindow):
    deviceOffline = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icons/main_icon.png")))
        self.setWindowTitle("AmbiTuya")
        self.setGeometry(100, 100, 375, 650)
        self.sleep_interval = 0.1

        self.device = None


        self.worker = None
        self.sync_running = False
        self.full_screen = True
        self.commands = {}
        self.prev_colors = {}  # Dictionary to store previous colors
        self.last_sent_payloads = {}  # Dictionary to store last sent payloads
        self.inactive_segments_set = False

        self.segment_checkboxes = {}  # key: segment number (int), value: QCheckBox
        self.total_segments = 20  # Total number of segments

        # Define advanced defaults...
        self.advanced_defaults = {
            "retries": 3,
            "max_sleep_interval": 9,
            "back_off_timer": 2.0,
            "reconnect_delay": 10.0,
            "extra_sleep_initial": 0.05,
            "extra_sleep_later": 0.12,
            "no_color_change_threshold": 20,
            "pause_duration": 0.50,
            "command_elapsed_threshold": 11,
            "max_ping_time": 0.11,
            "overlay_opacity": 0.5,
            "threshold_value": 10
        }
        # Initialize advanced settings from defaults.
        self.advanced_retries = self.advanced_defaults["retries"]
        self.advanced_max_sleep_interval = self.advanced_defaults["max_sleep_interval"]
        self.advanced_back_off_timer = self.advanced_defaults["back_off_timer"]
        self.advanced_reconnect_delay = self.advanced_defaults["reconnect_delay"]
        self.advanced_extra_sleep_initial = self.advanced_defaults["extra_sleep_initial"]
        self.advanced_extra_sleep_later = self.advanced_defaults["extra_sleep_later"]
        self.advanced_no_color_change_threshold = self.advanced_defaults["no_color_change_threshold"]
        self.advanced_pause_duration = self.advanced_defaults["pause_duration"]
        self.advanced_command_elapsed_threshold = self.advanced_defaults["command_elapsed_threshold"]
        self.advanced_max_ping_time = self.advanced_defaults["max_ping_time"]
        self.advanced_overlay_opacity = self.advanced_defaults["overlay_opacity"]

        # Device Setup defaults (if not set in settings, these will be used)
        self.device_default = {
            "device_id": "DeviceID",
            "device_ip": "DeviceIP",
            "device_key": "SecretKey",
            "device_version": "3.5"
        }

        self.initUI()

        # Worker will be created later after the device is initialized...
        self.sync_running = False  
        self.worker = None  
        self.deviceOffline.connect(self.showDeviceOfflineDialog)


    def initUI(self):
        # Create a QTabWidget to hold Basic and Advanced Settings tabs
        self.tab_widget = QTabWidget()

        ########################
        # Basic Settings Tab 
        ########################
        basic_tab = QWidget()

        # Create the main layout for the tab.
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === Sync Controls (Start/Stop) ===
        sync_layout = QHBoxLayout()
        self.auto_color_button = QPushButton(' Start Syncing')
        self.auto_color_button.setToolTip("Start syncing the screen’s colors to the device. This will begin the automatic color update process.")
        self.auto_color_button.clicked.connect(self.startSyncing)
        self.auto_color_button.setFixedHeight(40)
        sync_layout.addWidget(self.auto_color_button)
        self.auto_color_button.setIcon(QIcon(resource_path("icons/start_icon.png")))

        self.stop_button = QPushButton(' Stop Syncing')
        self.stop_button.setToolTip("Stop syncing the screen’s colors to the device.")
        self.stop_button.clicked.connect(self.stopSyncing)
        self.stop_button.setFixedHeight(40)
        sync_layout.addWidget(self.stop_button)
        main_layout.addLayout(sync_layout)
        self.stop_button.setIcon(QIcon(resource_path("icons/stop_icon.png")))

        # === Monitor Selection Controls ===
        monitor_layout = QVBoxLayout()
        monitor_label = QLabel("Select Monitor:")
        self.monitor_combobox = QComboBox()
        # Populate monitor combobox using mss to list monitors
        try:
            with mss.mss() as sct:
                # sct.monitors[0] is the full virtual screen, so skip it.
                monitors = sct.monitors[1:]
            for i, monitor in enumerate(monitors, start=1):
                self.monitor_combobox.addItem(
                    f"Monitor {i} ({monitor['width']}x{monitor['height']})", i
                )
        except Exception as e:
            #print("Error retrieving monitors:", e)     # DEBUG
            self.monitor_combobox.addItem("Primary Monitor", 1)
        self.monitor_combobox.currentIndexChanged.connect(self.monitor_selection_changed)
        monitor_layout.addWidget(monitor_label)
        monitor_layout.addWidget(self.monitor_combobox)
        main_layout.addLayout(monitor_layout)

        # === Brightness Controls ===
        brightness_layout = QHBoxLayout()
        self.set_brightness_checkbox = QCheckBox('Set Brightness')
        self.set_brightness_checkbox.setToolTip("Enable to apply a uniform brightness to all colors. When enabled, the brightness slider will adjust the brightness level.")
        self.set_brightness_checkbox.stateChanged.connect(self.toggleSetBrightness)
        brightness_layout.addWidget(self.set_brightness_checkbox)

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(1000)  # Brightness range
        self.brightness_slider.setValue(50)       # Default value
        self.brightness_slider.setEnabled(False)   # Initially disabled
        self.brightness_slider.setToolTip("Adjust the brightness value to send to the device (only used when 'Set Brightness' is enabled).")
        self.brightness_slider.valueChanged.connect(self.updateBrightnessValue)
        brightness_layout.addWidget(self.brightness_slider)
        main_layout.addLayout(brightness_layout)

        self.brightness_value_label = QLabel("100 %")
        self.brightness_value_label.setToolTip("Current brightness value")
        self.brightness_value_label.setFixedWidth(30)
        self.brightness_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        brightness_layout.addWidget(self.brightness_value_label)

        # === Color Boost Controls ===
        color_boost_layout = QHBoxLayout()
        self.set_color_boost_checkbox = QCheckBox('Enable Color Boost')
        self.set_color_boost_checkbox.setToolTip("Enable an additional saturation boost for colors. When checked, the color boost factor can be adjusted.")
        self.set_color_boost_checkbox.stateChanged.connect(self.toggleColorBoost)
        color_boost_layout.addWidget(self.set_color_boost_checkbox)

        color_boost_layout.addWidget(QLabel("Color Boost Factor:"))
        self.color_boost_spinbox = QDoubleSpinBox()
        self.color_boost_spinbox.setMinimum(1.0)   # 1.0 means no boost
        self.color_boost_spinbox.setMaximum(3.0)   # Maximum boost factor
        self.color_boost_spinbox.setSingleStep(0.1)
        self.color_boost_spinbox.setValue(1.0)         # Default boost factor
        self.color_boost_spinbox.setEnabled(False)     # Only enabled if boost is checked
        self.color_boost_spinbox.setToolTip("Set the color boost factor. (1.0 means no boost, higher values increase saturation.)")
        self.color_boost_spinbox.valueChanged.connect(self.save_settings)
        color_boost_layout.addWidget(self.color_boost_spinbox)
        main_layout.addLayout(color_boost_layout)

        # === Threshold Controls ===
        threshold_group = QGroupBox("Minimum Color Change Thresholds")
        threshold_group.setToolTip("Thresholds to determine whether a change in color is significant enough to update the device.")
        threshold_layout = QFormLayout()

        # Individual (RGB) Threshold
        self.component_threshold_spinbox = QSpinBox()
        self.component_threshold_spinbox.setMinimum(0)
        self.component_threshold_spinbox.setMaximum(1000)
        self.component_threshold_spinbox.setValue(250)  # Default value
        self.component_threshold_spinbox.setToolTip("A change in any single channel must exceed this value to be considered significant.")
        self.component_threshold_spinbox.valueChanged.connect(self.save_settings)
        threshold_layout.addRow("Individual Threshold: ", self.component_threshold_spinbox)

        # Manhattan (Distance) Threshold
        self.manhattan_threshold_spinbox = QDoubleSpinBox()
        self.manhattan_threshold_spinbox.setMinimum(0.0)
        self.manhattan_threshold_spinbox.setMaximum(1000.0)
        self.manhattan_threshold_spinbox.setSingleStep(1.0)
        self.manhattan_threshold_spinbox.setValue(150.0)  # Default value
        self.manhattan_threshold_spinbox.setToolTip("The sum of differences in R, G, and B must exceed this value to trigger an update.")
        self.manhattan_threshold_spinbox.valueChanged.connect(self.save_settings)
        threshold_layout.addRow("Distance Threshold: ", self.manhattan_threshold_spinbox)

        threshold_group.setLayout(threshold_layout)
        main_layout.addWidget(threshold_group)

        # === Letterbox Detection ===
        self.letterbox_checkbox = QCheckBox('Enable Letterbox Detection')
        self.letterbox_checkbox.setToolTip("Enable detection and cropping of black letterbox bars from the screen capture. Disabling this will leave the full screen intact.")
        self.letterbox_checkbox.setChecked(True)  # default: enabled
        self.letterbox_checkbox.stateChanged.connect(self.toggleLetterboxDetection)
        main_layout.addWidget(self.letterbox_checkbox)

        # === Active Segments Group ===
        segment_group = QGroupBox("Select Active Segments")
        segment_group.setToolTip("Select which segments should be active for color synchronization.")
        segment_layout = QVBoxLayout()

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()

        # Load active segments (self.load_active_segments() returns a list of active segments)
        active_segments = self.load_active_segments()
        self.segment_checkboxes = {}  # To store the checkboxes

        for segment in range(1, self.total_segments + 1):
            cb = QCheckBox(f"Segment {segment}")
            cb.setChecked(segment in active_segments)  # Set checked if segment is active
            cb.setToolTip(self.get_segment_tooltip(cb.isChecked(), segment))
            # Update tooltip when state changes.
            cb.stateChanged.connect(lambda state, s=segment, cb=cb: 
                cb.setToolTip(self.get_segment_tooltip(state == Qt.CheckState.Checked.value, s)))
            cb.stateChanged.connect(self.update_segments_json_from_checkboxes)
            self.segment_checkboxes[segment] = cb
            scroll_layout.addWidget(cb)
            
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        segment_layout.addWidget(scroll_area)
        segment_group.setLayout(segment_layout)
        main_layout.addWidget(segment_group)

        # === Bottom Buttons ===
        button_layout = QHBoxLayout()
        self.edit_segments_button = QPushButton('Edit Segments')
        self.edit_segments_button.setToolTip("Manually edit segment positions and sizes.")
        self.edit_segments_button.clicked.connect(self.save_device_setup)
        self.edit_segments_button.clicked.connect(self.edit_segments)
        button_layout.addWidget(self.edit_segments_button)
        
        self.full_screen_button = QPushButton('Show Segment Mapping')
        self.full_screen_button.setToolTip("View a full screen preview of the segment mapping overlay.")
        self.full_screen_button.clicked.connect(self.showSegments)
        button_layout.addWidget(self.full_screen_button)
        main_layout.addLayout(button_layout)

        # === Reset to Defaults Button ===
        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        reset_basic_button = QPushButton("Reset to Defaults")
        reset_basic_button.setToolTip("Restore all basic settings to their default values.")
        reset_basic_button.clicked.connect(self.reset_basic_defaults)
        reset_layout.addWidget(reset_basic_button)
        reset_layout.addStretch()
        main_layout.addLayout(reset_layout)

        # Create a container widget for the main layout.
        basic_container = QWidget()
        basic_container.setLayout(main_layout)

        # Place the container inside a scroll area.
        scroll_area_basic = QScrollArea()
        scroll_area_basic.setWidgetResizable(True)
        scroll_area_basic.setWidget(basic_container)

        # Set the layout for the basic_tab.
        basic_tab_layout = QVBoxLayout(basic_tab)
        basic_tab_layout.addWidget(scroll_area_basic)


        ########################
        # Advanced Settings Tab
        ########################
        advanced_tab = QWidget()

        # Create the main layout for advanced settings.
        adv_main_layout = QVBoxLayout()
        adv_main_layout.setSpacing(10)
        adv_main_layout.setContentsMargins(10, 10, 10, 10)

        # Create a form layout for the settings.
        form_layout = QFormLayout()

        # Max Ping Time Setting
        self.max_ping_time_spinbox = QDoubleSpinBox()
        self.max_ping_time_spinbox.setRange(0.01, 1.0)
        self.max_ping_time_spinbox.setSingleStep(0.01)
        self.max_ping_time_spinbox.setValue(self.advanced_max_ping_time)
        self.max_ping_time_spinbox.setToolTip("Warning: Low values may cause the device to become unresponsive. Maximum ping time (in seconds) used for determining sleep intervals.")
        self.max_ping_time_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('max_ping_time', val))
        form_layout.addRow("Max Ping Time:", self.max_ping_time_spinbox)

        # Retries
        self.retries_spinbox = QSpinBox()
        self.retries_spinbox.setRange(1, 10)
        self.retries_spinbox.setValue(self.advanced_retries)
        self.retries_spinbox.setToolTip("Number of retry attempts before giving up.")
        self.retries_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('retries', val))
        form_layout.addRow("Retries:", self.retries_spinbox)

        # Maximum Sleep Interval
        self.max_sleep_spinbox = QDoubleSpinBox()
        self.max_sleep_spinbox.setRange(1.0, 20.0)
        self.max_sleep_spinbox.setValue(self.advanced_max_sleep_interval)
        self.max_sleep_spinbox.setToolTip("Maximum time (in seconds) before sending a heartbeat command.")
        self.max_sleep_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('max_sleep_interval', val))
        form_layout.addRow("Max Sleep Interval:", self.max_sleep_spinbox)

        # Back Off Timer
        self.back_off_spinbox = QDoubleSpinBox()
        self.back_off_spinbox.setRange(0.1, 10.0)
        self.back_off_spinbox.setValue(self.advanced_back_off_timer)
        self.back_off_spinbox.setToolTip("Initial back-off time (in seconds) used when retrying commands.")
        self.back_off_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('back_off_timer', val))
        form_layout.addRow("Back Off Timer:", self.back_off_spinbox)

        # Reconnect Delay
        self.reconnect_delay_spinbox = QDoubleSpinBox()
        self.reconnect_delay_spinbox.setRange(0.1, 20.0)
        self.reconnect_delay_spinbox.setValue(self.advanced_reconnect_delay)
        self.reconnect_delay_spinbox.setToolTip("Delay (in seconds) after a lost packet before reconnecting.")
        self.reconnect_delay_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('reconnect_delay', val))
        form_layout.addRow("Reconnect Delay:", self.reconnect_delay_spinbox)

        # Extra Sleep (Initial)
        self.extra_sleep_initial_spinbox = QDoubleSpinBox()
        self.extra_sleep_initial_spinbox.setRange(0.0, 1.0)
        self.extra_sleep_initial_spinbox.setSingleStep(0.01)
        self.extra_sleep_initial_spinbox.setValue(self.advanced_extra_sleep_initial)
        self.extra_sleep_initial_spinbox.setToolTip("Additional sleep time (in seconds) when command count is below 5.")
        self.extra_sleep_initial_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('extra_sleep_initial', val))
        form_layout.addRow("Extra Sleep (Initial):", self.extra_sleep_initial_spinbox)

        # Extra Sleep (Later)
        self.extra_sleep_later_spinbox = QDoubleSpinBox()
        self.extra_sleep_later_spinbox.setRange(0.0, 1.0)
        self.extra_sleep_later_spinbox.setSingleStep(0.01)
        self.extra_sleep_later_spinbox.setValue(self.advanced_extra_sleep_later)
        self.extra_sleep_later_spinbox.setToolTip("Additional sleep time (in seconds) when command count is 5 or more.")
        self.extra_sleep_later_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('extra_sleep_later', val))
        form_layout.addRow("Extra Sleep (Later):", self.extra_sleep_later_spinbox)

        # No Color Change Threshold
        self.no_color_change_spinbox = QDoubleSpinBox()
        self.no_color_change_spinbox.setRange(1, 60)
        self.no_color_change_spinbox.setValue(self.advanced_no_color_change_threshold)
        self.no_color_change_spinbox.setToolTip("Maximum number of commands sent with color change before activating the 'Pause Duration'.")
        self.no_color_change_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('no_color_change_threshold', val))
        form_layout.addRow("Max Color Commands:", self.no_color_change_spinbox)

        # Pause Duration
        self.pause_duration_spinbox = QDoubleSpinBox()
        self.pause_duration_spinbox.setRange(0.1, 5.0)
        self.pause_duration_spinbox.setValue(self.advanced_pause_duration)
        self.pause_duration_spinbox.setToolTip("Duration (in seconds) to pause command processing to allow the device to process commands.")
        self.pause_duration_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('pause_duration', val))
        form_layout.addRow("Pause Duration:", self.pause_duration_spinbox)

        # Command Elapsed Threshold
        self.command_elapsed_spinbox = QDoubleSpinBox()
        self.command_elapsed_spinbox.setRange(1, 30)
        self.command_elapsed_spinbox.setValue(self.advanced_command_elapsed_threshold)
        self.command_elapsed_spinbox.setToolTip("Time (in seconds) to send a heartbeat if there is no color change.")
        self.command_elapsed_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('command_elapsed_threshold', val))
        form_layout.addRow("No Color Heartbeat:", self.command_elapsed_spinbox)

        # Overlay Opacity Setting
        self.overlay_opacity_spinbox = QDoubleSpinBox()
        self.overlay_opacity_spinbox.setRange(0.0, 1.0)
        self.overlay_opacity_spinbox.setSingleStep(0.01)
        self.overlay_opacity_spinbox.setValue(self.advanced_overlay_opacity)
        self.overlay_opacity_spinbox.setToolTip("Set the opacity for the segment mapping overlay (0.0 = fully transparent, 1.0 = fully opaque)")
        self.overlay_opacity_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('overlay_opacity', val))
        form_layout.addRow("Overlay Opacity:", self.overlay_opacity_spinbox)

        # Letterbox Threshold Controls
        self.threshold_value_spinbox = QSpinBox()
        self.threshold_value_spinbox.setRange(1, 255)
        self.threshold_value_spinbox.setValue(10) 
        self.threshold_value_spinbox.setToolTip("Adjust the threshold value for black bar detection. Set to a higher value for brighter letterboxing.")
        self.threshold_value_spinbox.valueChanged.connect(lambda val: self.set_advanced_setting('threshold_value', val))
        form_layout.addRow("Letterbox Threshold:", self.threshold_value_spinbox)

        # Create a QComboBox for theme selection.
        self.theme_combobox = QComboBox()
        self.theme_combobox.addItems(["Light Theme", "Dark Theme"])
        self.theme_combobox.setToolTip("Select the application theme: Light or Dark")
        self.theme_combobox.currentIndexChanged.connect(self.change_theme)
        form_layout.addRow("Theme Selection:", self.theme_combobox)

        # Add the form layout to the main advanced layout.
        adv_main_layout.addLayout(form_layout)

        # Reset Defaults Button
        reset_button = QPushButton("Reset to Defaults")
        reset_button.setToolTip("Restore all advanced settings to their default values.")
        reset_button.clicked.connect(self.reset_advanced_defaults)
        adv_main_layout.addWidget(reset_button)

        # Create a container widget for advanced settings.
        advanced_container = QWidget()
        advanced_container.setLayout(adv_main_layout)

        # Create the scroll area and add the container.
        scroll_area_advanced = QScrollArea()
        scroll_area_advanced.setWidgetResizable(True)
        scroll_area_advanced.setWidget(advanced_container)

        # Set the outer layout of advanced_tab to include the scroll area.
        advanced_tab_outer_layout = QVBoxLayout(advanced_tab)
        advanced_tab_outer_layout.addWidget(scroll_area_advanced)

        # Add the tabs to the tab widget.
        self.tab_widget.addTab(basic_tab, "Basic Settings")
        self.tab_widget.addTab(advanced_tab, "Advanced Settings")
        self.setCentralWidget(self.tab_widget)

        ########################
        # Device Setup Tab 
        ########################
        device_setup_tab = QWidget()

        # Main layout for the Device Setup tab
        main_layout = QVBoxLayout()

        # Device Information Group
        info_group = QGroupBox("Device Information")
        info_layout = QFormLayout()
        info_layout.setSpacing(15)

        # Device ID field
        self.device_id_lineedit = QLineEdit()
        self.device_id_lineedit.setToolTip("Enter the Device ID to use with TinyTuya.")
        info_layout.addRow("Device ID:", self.device_id_lineedit)

        # Device IP field
        self.device_ip_lineedit = QLineEdit()
        self.device_ip_lineedit.setToolTip("Enter the Device local IP address to use with TinyTuya.")
        info_layout.addRow("Device IP:", self.device_ip_lineedit)

        # Device Key field with toggle button to show/hide
        self.device_key_lineedit = QLineEdit()
        self.device_key_lineedit.setToolTip("Enter the Device Key (Secret) to use with TinyTuya.")
        self.device_key_lineedit.setEchoMode(QLineEdit.EchoMode.Password)

        self.toggle_device_key_button = QPushButton("Show")
        self.toggle_device_key_button.setCheckable(True)
        self.toggle_device_key_button.setFixedWidth(50)
        self.toggle_device_key_button.clicked.connect(self.toggle_device_key_visibility)

        # Horizontal layout to hold the device key field and toggle button
        device_key_layout = QHBoxLayout()
        device_key_layout.addWidget(self.device_key_lineedit)
        device_key_layout.addWidget(self.toggle_device_key_button)
        info_layout.addRow("Device Key:", device_key_layout)

        # Device Version field
        self.device_version_lineedit = QLineEdit()
        self.device_version_lineedit.setToolTip("Enter the Device Version (e.g., 3.3 or 3.5) to use with TinyTuya.")
        info_layout.addRow("Device Version:", self.device_version_lineedit)

        # Button: Save Device Setup
        save_device_button = QPushButton("Save Device Setup")
        save_device_button.setToolTip("Save the device details and reconnect to the device.")
        save_device_button.clicked.connect(self.save_device_setup)
        info_layout.addRow(save_device_button)

        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)

        # Actions Group
        actions_group = QGroupBox("Auto-Setup && Instructions")
        actions_layout = QVBoxLayout()

        # Button: Run Automatic Setup
        auto_setup_button = QPushButton("Run Automatic Setup")
        auto_setup_button.setToolTip("Automatically retrieve your device info using the TinyTuya wizard.")
        auto_setup_button.clicked.connect(self.run_automatic_setup)
        actions_layout.addWidget(auto_setup_button)

        # Button: How to Setup Your Tuya Device
        instructions_button = QPushButton("How to Setup Your Tuya Device")
        instructions_button.setToolTip("View instructions on how to set up your Tuya device for TinyTuya.")
        instructions_button.clicked.connect(self.show_setup_instructions)
        actions_layout.addWidget(instructions_button)

        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)

        device_setup_tab.setLayout(main_layout)


        ########################
        # Help Tab
        ########################
        help_tab = QWidget()
        help_layout = QVBoxLayout(help_tab)

        # Create a read-only text edit to display help information
        help_text_edit = QTextEdit()
        help_text_edit.setReadOnly(True)
        help_text_edit.setHtml("""
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; font-size: 14px; }
                h2 { color: #ff4800; }
                h3 { color: #ff4800; }
                a { color: #ff4800; }
                ul { margin-left: 20px; }
            </style>
        </head>
        <body>
            <h2>Help & FAQ</h2>
            <p>AmbiTuya allows you to control and sync your LED strip with your screen colors using a Tuya device.</p>

            <h3>Features</h3>
            <ul>
                <li><b>Basic Settings:</b> Monitor selection, start/stop syncing, brightness adjustments, and selecting active segments.</li>
                <li><b>Advanced Settings:</b> Fine-tune retry parameters, sleep intervals, color thresholds, and other advanced options.</li>
                <li><b>Device Setup:</b> Configure your Tuya device credentials and automatically retrieve device details.</li>
                <li><b>Segment Editor:</b> Adjust and customize the regions of your screen used for LED color extraction.</li>
            </ul>

            <h3>Device Setup</h3>
            <p>The Device Setup tab is where you configure your Tuya device details and connection parameters:</p>
            <ul>
                <li><b>Device Information:</b> Enter the Device ID, Device IP, Device Key, and Device Version required to connect to your Tuya device. For security, the Device Key is hidden by default and can be toggled visible.</li>
                <li><b>Save Device Setup:</b> Click this button to save your device details and reconnect to the device.</li>
                <li><b>Automatic Setup & Instructions:</b> Use the "Run Automatic Setup" button to automatically retrieve your device info using the TinyTuya Wizard, or click "How to Setup Your Tuya Device" to view detailed instructions.</li>
            </ul>

            <h3>Preventing Device Overload</h3>
            <p>Each device handles incoming commands differently, and sending too many commands too quickly can overload the device, causing it to slow down or even become unresponsive. To help prevent this, you can:</p>
            <ul>
                <li><b>Increase the Sleep Interval:</b> In the Advanced Settings tab, adjust the <b>Max Sleep Interval</b> to a higher value (for example, 0.2 – 1 second) to reduce the command frequency.</li>
                <li><b>Adjust the Color Thresholds:</b>
                    <ul>
                        <li>Increase the <b>Individual Threshold</b> so that minor color changes do not trigger an update.</li>
                        <li>Increase the <b>Distance Threshold</b> to require a more significant overall color change before sending a command.</li>
                    </ul>
                </li>
                <li><b>Enable Extra Sleep:</b> Set the <b>Extra Sleep (Initial)</b> and <b>Extra Sleep (Later)</b> to small positive values (e.g., 0.05 – 0.15 seconds) to prevent bursts of commands.</li>
                <li><b>Reduce Active Segments:</b> If your device struggles with performance, consider disabling some segments in the Basic Settings tab.</li>
            </ul>

            <h3>Recovering an Unresponsive Device</h3>
            <p>If your device becomes unresponsive after receiving too many commands, try the following steps:</p>
            <ul>
                <li><b>Unplug and Replug the Device:</b> Disconnect the device from its power source for about 3–5 seconds, then plug it back in.</li>
                <li><b>Reconnect the Device:</b> Go to the Device Setup tab, verify your device details, and click <b>Save Device Setup</b> to force a reconnection.</li>
                <li><b>Reduce Command Frequency:</b> Adjust your Advanced Settings to lower the rate of command updates and prevent future overloads.</li>
            </ul>

            <h3>Basic Settings </h3>
            <p>The Basic Settings tab provides a user-friendly interface for the most common functions:</p>
            <ul>
                <li><b>Monitor/Screen Selection:</b> 
                    <ul>
                        <li><i>Select Monitor:</i> Choose which screen to capture from using the drop-down selections.</li>
                    </ul>
                </li>
                <li><b>Sync Controls:</b> 
                    <ul>
                        <li><i>Start Syncing:</i> Begins syncing your screen’s colors to the device.</li>
                        <li><i>Stop Syncing:</i> Halts the color synchronization process.</li>
                    </ul>
                </li>
                <li><b>Brightness Control:</b> 
                    <ul>
                        <li><i>Set Brightness:</i> When enabled, applies a uniform brightness to all colors. Use the slider to adjust the brightness level.</li>
                    </ul>
                </li>
                <li><b>Color Boost:</b> 
                    <ul>
                        <li><i>Enable Color Boost:</i> Activates an additional saturation boost.</li>
                        <li><i>Color Boost Factor:</i> Adjust the boost intensity (1.0 means no boost; higher values increase saturation).</li>
                    </ul>
                </li>
                <li><b>Threshold Controls:</b> 
                    <ul>
                        <li><i>Individual Threshold:</i> Sets the minimum change required in any single color channel (RGB) to trigger an update.</li>
                        <li><i>Distance Threshold:</i> Specifies the overall color difference needed before an update is sent.</li>
                    </ul>
                </li>
                <li><b>Letterbox Detection:</b>
                    <ul>
                        <li><i>Automatically detects and crops black letterbox bars from the screen capture so that only active areas are processed.</li>
                    </ul>
                <li><b>Active Segments:</b> 
                    <ul>
                        <li>Select which segments of your LED strip receive color updates by checking or unchecking the corresponding boxes.</li>
                        <li>The status of each segment is reflected in its tooltip, letting you know if clicking will activate or deactivate that segment.</li>
                    </ul>
                </li>
                <li><b>Editing & Mapping:</b> 
                    <ul>
                        <li><i>Edit Segments:</i> Opens the Segment Editor for fine-tuning segment positions and sizes.</li>
                        <li><i>Show Segment Mapping:</i> Provides a full-screen preview of the current segment layout.</li>
                    </ul>
                </li>
                <li><b>Reset to Defaults:</b> Quickly restores all Basic Settings to their default values.</li>
            </ul>

            <h3>Segment Editor</h3>
            <p>The Segment Editor is a powerful tool that allows you to visually customize the areas of your screen that are used to extract colors for your LED strip. Here’s how it works and what it’s used for:</p>
            <ul>
                <li><b>Visual Editing:</b> When you open the Segment Editor, you’ll see a grid overlay representing your screen with draggable and resizable rectangles. Each rectangle corresponds to a segment of the LED strip.</li>
                <li><b>Adjusting Segments:</b> Click on a segment to select it, then drag to reposition or resize the segment as needed. This allows you to fine-tune the mapping so that each LED segment accurately represents the corresponding screen area.</li>
                <li><b>Purpose:</b> Use the Segment Editor to calibrate the LED display layout, ensuring that colors are extracted from the correct regions. This is especially useful if your screen or LED setup has a non-standard layout.</li>
                <li><b>Saving Changes:</b> Once you’re satisfied with the adjustments, click the <b>Save Changes</b> button to update the segment configuration.</li>
            </ul>

            <h3>Adding and Removing Segments</h3>
            <p>Toggle any unused segments by simply checking or un-checking the segment's checkbox within the 'Select Active Segments' section.</p>
            <ul>
                <li><b>Removing Segments:</b> Uncheck a segment's box to disable it from receiving color updates.</li>
                <li><b>Adding Segments:</b> Check a segment's box to enable it; active segments will be added to the Segment Editor and used for color syncing.</li>
                <li><b>Segment Limit:</b> Currently, the program supports a maximum of 20 segments.</li>
            </ul>

            <h3>Advanced Settings</h3>
            <p>The Advanced Settings tab lets you customize the underlying parameters to optimize device performance and command frequency:</p>
            <ul>
                <li><b>Max Ping Time:</b> Sets the maximum ping time (in seconds) used for determining sleep intervals. <i>Warning:</i> Lower values may cause the device to become unresponsive.</li>
                <li><b>Retries:</b> Determines the number of retry attempts before giving up on sending a command.</li>
                <li><b>Max Sleep Interval:</b> Specifies the maximum time (in seconds) before sending a heartbeat command.</li>
                <li><b>Back Off Timer:</b> Sets the initial back-off time (in seconds) used when retrying commands.</li>
                <li><b>Reconnect Delay:</b> Defines the delay (in seconds) after a lost packet before reconnecting to the device.</li>
                <li><b>Extra Sleep (Initial):</b> Adds extra sleep time (in seconds) when the command count is low (below 5), helping to prevent command bursts.</li>
                <li><b>Extra Sleep (Later):</b> Adds additional sleep time (in seconds) when the command count is 5 or more, to further alleviate device load.</li>
                <li><b>Max Color Commands:</b> (No Color Change Threshold) Limits the number of commands sent with no color change before activating a pause.</li>
                <li><b>Pause Duration:</b> Determines the duration (in seconds) to pause command processing, allowing the device time to process previous commands.</li>
                <li><b>No Color Heartbeat:</b> (Command Elapsed Threshold) Sets the time (in seconds) after which a heartbeat command is sent if there’s no color change.</li>
                <li><b>Overlay Opacity:</b> Adjusts the opacity of the segment mapping overlay (0.0 for fully transparent, 1.0 for fully opaque).</li>
                <li><b>Letterbox Threshold:</b> Sets the max brightness for a letterbox to be considered “black.” A higher threshold means that letterboxing with brighter pixels (darker grays rather than near-black) will qualify as letterbox areas.</li>
                <li><b>Theme Selection:</b> Choose between Light and Dark themes for the application interface.</li>
            </ul>
            
            <h3>Error Codes</h3>
            <ul>
                <li><b>Error 901:</b> Indicates a network connectivity issue. Verify your network connection and ensure your computer and device are on the same network.</li>
                <li><b>Error 905:</b> Suggests a problem with device information. Check the Device Setup tab to ensure that the correct device ID, IP, and other details are entered correctly.</li>
                <li><b>Error 914:</b> Means the device key or version might be incorrect. Revisit the Device Setup tab and verify that the Device Key and Version are correct.</li>
            </ul>
                                           
            <h3>Troubleshooting</h3>
            <ul>
                <li>If your device is not detected, verify the device settings under the Device Setup tab.</li>
                <li>Ensure that your computer and device are on the same network.</li>
                <li>Use the <b>Automatic Setup</b> option to refresh device information.</li>
                <li>For more help, see the <a href="https://github.com/jasonacox/tinytuya">TinyTuya Documentation</a>.</li>
            </ul>

            <h3>Support</h3>
            <p>If issues persist, please check all settings and consult the documentation. Contact support if needed.</p>
        </body>
        </html>
        """)

        help_layout.addWidget(help_text_edit)
        help_tab.setLayout(help_layout)

        ##################################
        # Add all tabs to the QTabWidget #
        ##################################

        self.tab_widget.addTab(device_setup_tab, "Device Setup")
        self.tab_widget.addTab(basic_tab, "Basic Settings")
        self.tab_widget.addTab(advanced_tab, "Advanced Settings")
        self.tab_widget.addTab(help_tab, "Help")
        self.setCentralWidget(self.tab_widget)

        # Add the sync indicator icon in the top-right corner
        self.syncIndicator = QLabel()
        self.syncIndicator.setFixedSize(24, 24)
        # Syncing is off so show a greyed-out icon.
        self.syncIndicator.setPixmap(
            QPixmap(resource_path("icons/grey_icon.png")).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )
        # Place it in the top-right corner of the tab widget.
        self.tab_widget.setCornerWidget(self.syncIndicator, Qt.Corner.TopRightCorner)

        # Load settings and connect signals
        self.settings = {}
        self.load_settings()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)



        ########################
        #    GUI FUNCTIONS     #
        ########################

        ### General Settings ###
    def on_tab_changed(self, index):
        self.settings["last_tab_index"] = index
        self.save_settings()

    def toggle_device_key_visibility(self):
        if self.toggle_device_key_button.isChecked():
            self.device_key_lineedit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_device_key_button.setText("Hide")
        else:
            self.device_key_lineedit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_device_key_button.setText("Show")


        ### Monitor and Segment Operations ###

    def monitor_selection_changed(self):
        """Save the selected monitor index and switch capture immediately."""
        selected_monitor_index = self.monitor_combobox.itemData(self.monitor_combobox.currentIndex())
        if selected_monitor_index is not None:
            self.settings["selected_monitor_index"] = selected_monitor_index
            self.save_settings()
            # Switch monitor capture in the C++ code.
            time_bindings.switchMonitorCapture()
            #print(f"Switched monitor capture to index {selected_monitor_index}.")      # DEBUG

    def update_segments_json_from_checkboxes(self):
        """
        Called whenever a segment checkbox is toggled.
        This function updates the active segments file (segments.json)
        and the inactive segments file (segments_inactive.json) accordingly.
        """
        # Create a list of active segment numbers (as ints)
        active_segments = [
            segment for segment, cb in self.segment_checkboxes.items() if cb.isChecked()
        ]
        
        # All segment numbers (1..total_segments)
        all_segments = list(range(1, self.total_segments + 1))
        # The inactive segments are the ones not in the active list.
        inactive_segments = [seg for seg in all_segments if seg not in active_segments]

        # Load current active segments from segments.json
        try:
            with open("segments.json", "r") as f:
                active_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default data for all segments if needed.
            active_data = {str(seg): {"x": 0, "y": 0, "width": 100, "height": 100} for seg in all_segments}

        # Load current inactive segments from the inactive file.
        inactive_data = load_inactive_segments()

        # Process inactive segments:
        for seg in inactive_segments:
            seg_key = str(seg)
            if seg_key in active_data:
                # Save the geometry into the inactive file and remove from active data.
                inactive_data[seg_key] = active_data.pop(seg_key)

        # Process active segments:
        for seg in active_segments:
            seg_key = str(seg)
            if seg_key in inactive_data:
                # If the segment was previously inactive, restore its geometry.
                active_data[seg_key] = inactive_data.pop(seg_key)
            elif seg_key not in active_data:
                # If no geometry exists at all, create a default entry.
                active_data[seg_key] = {"x": 0, "y": 0, "width": 100, "height": 100}

        # Save the active segments back to segments.json
        try:
            with open("segments.json", "w") as f:
                json.dump(active_data, f, indent=4)
        except IOError as e:
            print(f"Error saving active segments: {e}")

        # Save the inactive segments back to segments_inactive.json
        save_inactive_segments(inactive_data)

    def get_segment_tooltip(self, is_active, segment):
        """Returns the appropriate tooltip text for a segment checkbox."""
        if is_active:
            return f"Deactivate Segment {segment}. Inactive segments will not receive color updates."
        else:
            return f"Activate Segment {segment}. Only active segments will receive color updates and are added to the Segment Editor."

    def edit_segments(self):
        if self.device is None:
            QMessageBox.warning(self, "Error", "Device not connected or initialized!")
            return

        active_segments = [seg for seg, cb in self.segment_checkboxes.items() if cb.isChecked()]
        import mss
        from PyQt6.QtCore import QSize
        with mss.mss() as sct:
            monitors = sct.monitors
            monitor_index = self.monitor_combobox.currentData() or 1
            if monitor_index < len(monitors):
                selected_monitor = monitors[monitor_index]
                selected_screen_size = QSize(selected_monitor["width"], selected_monitor["height"])
            else:
                selected_screen_size = QApplication.primaryScreen().size()

        editor = SegmentEditor(self.device, active_segments=active_segments, screen_size=selected_screen_size)
        editor.show()

    def showSegments(self):
        import os
        if not os.path.exists('segments.json'):
            QMessageBox.information(
                self,
                "No Segments Found",
                "No segments have been saved. Please create segments using the Segment Editor before attempting to view them."
            )
            return
        with open('segments.json', 'r') as f:
            active_segments = json.load(f)
        monitor_index = self.monitor_combobox.currentData() or 1
        dialog = SegmentDisplayDialog(active_segments=active_segments, overlay_opacity=self.advanced_overlay_opacity, monitor_index=monitor_index)
        dialog.exec()

    def updateActiveSegments(self, value):
        self.active_segments = value
        # Update any UI element reflecting active segments if needed.
        self.inactive_segments_set = False




        ### Device and Detection Alerts ###

    def showDeviceOfflineDialog(self, message):
        QMessageBox.critical(self, "Device Offline", message)

    def handle_device_error(self, error):
        if self.sync_running:
            self.stopSyncing()
            QTimer.singleShot(0, lambda: QMessageBox.critical(
                self,
                "Device Error",
                f"ERROR: {error}\nCheck Device Information."
            ))

    def toggleLetterboxDetection(self, state):
        enabled = (state == Qt.CheckState.Checked.value)
        try:
            time_bindings.set_letterbox_detection(enabled)
            #print("Letterbox detection", "enabled" if enabled else "disabled")     # DEBUG
        except Exception as e:
            print("Error toggling letterbox detection:", e)
        self.save_settings()

    def toggleColorBoost(self, state):
        if state == Qt.CheckState.Checked.value:
            self.color_boost_spinbox.setEnabled(True)
        else:
            self.color_boost_spinbox.setEnabled(False)
        self.save_settings()



        ### Brightness and Color Adjustments ###
        
    def applyUniformBrightness(self, command, brightness):
        command['value'] = brightness
        return command

    def toggleSetBrightness(self, state):
        if state == Qt.CheckState.Checked.value:
            self.brightness_slider.setEnabled(True)
        else:
            self.brightness_slider.setEnabled(False)
        self.save_settings()

    def updateBrightnessValue(self, value):
        self.brightness_value_label.setText(f"{round(value / 10)} %")
        self.save_settings()





        ########################
        #   AUTOMATIC SETUP    #
        ########################

    def run_automatic_setup(self):
        # Load saved credentials from self.settings if any.
        saved_credentials = {
            "api_key": self.settings.get("api_key", ""),
            "api_secret": self.settings.get("api_secret", ""),
            "api_region": self.settings.get("api_region", ""),
        }
        dialog = WizardInputDialog(self, saved_credentials)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User canceled

        inputs = dialog.get_inputs()
        if not inputs["api_key"] or not inputs["api_secret"] or not inputs["api_region"]:
            QMessageBox.warning(self, "Input Error", "All fields are required.")
            return

        # Update settings if the user chose to save credentials.
        if inputs["save_credentials"]:
            self.settings["api_key"] = inputs["api_key"]
            self.settings["api_secret"] = inputs["api_secret"]
            self.settings["api_region"] = inputs["api_region"]
            self.save_settings()
        else:
            self.settings.pop("api_key", None)
            self.settings.pop("api_secret", None)
            self.settings.pop("api_region", None)
            self.save_settings()

        try:
            # **Delete old JSON files before running the wizard** to ensure device info is up-to-date.
            json_files = ["devices.json", "snapshot.json", "tinytuya.json", "tuya-raw.json"]
            for file in json_files:
                if os.path.exists(file):
                    os.remove(file)
                    print(f"Deleted old {file}")

            if getattr(sys, "frozen", False):
                wizard_exe = resource_path("tinytuya_wizard.exe")
                if not os.path.exists(wizard_exe):
                    raise FileNotFoundError(f"Wizard executable not found at {wizard_exe}")
                cmd = [wizard_exe, "wizard", "-nocolor"]
            else:  # Running as a Python script
                cmd = [sys.executable, "-m", "tinytuya", "wizard", "-nocolor"]

            #print(f"Launching: {cmd}")  # DEBUG

            # Prepare input responses
            responses = (
                f"{inputs['api_key']}\n"
                f"{inputs['api_secret']}\n"
                "scan\n"
                f"{inputs['api_region']}\n"
                "y\n"  # Download DP Name mappings? (Y/n)
                "y\n"  # Poll local devices? (Y/n)
            )

            # Launch the wizard and send input
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            output, error = proc.communicate(input=responses, timeout=120)  # Send responses here

            #print(f"Wizard Error:\n{error}")  # DEBUG

            if error:
                raise Exception(f"Wizard encountered an error: {error}")

            # Ensure the new devices.json file was created
            devices_json_file = "devices.json"
            if not os.path.exists(devices_json_file):
                raise Exception("devices.json not found. Cannot retrieve device info.\n\n"
                                "Check Tuya API Credentials.")

            with open(devices_json_file, "r") as f:
                device_list = json.load(f)

            if not device_list or not isinstance(device_list, list):
                raise Exception("Device JSON is not a valid list.")

            # Handle multiple devices
            if len(device_list) > 1:
                selection_dialog = DeviceSelectionDialog(device_list, self)
                if selection_dialog.exec() == QDialog.DialogCode.Accepted:
                    selected_device = selection_dialog.get_selected_device()
                else:
                    QMessageBox.information(self, "Automatic Setup", "Device selection was canceled.")
                    return
            else:
                selected_device = device_list[0]

            # Check DPS 61 (paint_colour_data) in device data
            dps61_valid = False
            device_id = selected_device.get("id")

            with open(devices_json_file, "r") as f:
                devices_data = json.load(f)  # Ensure this is a LIST of devices

            # Locate the correct device in the list
            dev_info = next((dev for dev in devices_data if dev.get("id") == device_id), None)

            if dev_info:
                # Look for the DPS information under either "dps" or "mapping".
                dps = dev_info.get("dps") or dev_info.get("mapping", {})
                dps61 = dps.get("61", {})

                # Check that DPS "61" has the expected structure.
                if (
                    isinstance(dps61, dict) and
                    dps61.get("code") == "paint_colour_data" and
                    dps61.get("type") == "Raw" and
                    isinstance(dps61.get("values"), dict) and
                    dps61["values"].get("maxlen") == 128
                ):
                    dps61_valid = True

            if not dps61_valid:
                QMessageBox.warning(
                    self,
                    "Automatic Setup Warning",
                    "The device's DPS does not include a properly formatted '61' entry.\n\n"
                    "Expected format:\n"
                    "{\n"
                    '  "code": "paint_colour_data",\n'
                    '  "type": "Raw",\n'
                    '  "values": { "maxlen": 128 }\n'
                    "}\n\n"
                    "Without this, the program may not work correctly."
                )

            # Update the UI fields
            self.device_id_lineedit.setText(selected_device.get("id", "DeviceID"))
            self.device_ip_lineedit.setText(selected_device.get("ip", "DeviceIP"))
            self.device_key_lineedit.setText(selected_device.get("key", "SecretKey"))
            self.device_version_lineedit.setText(selected_device.get("version", "3.5"))

            QMessageBox.information(self, "Automatic Setup", "Device info retrieved and populated successfully.")

        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "Automatic Setup Error", "The wizard timed out. Please try again.")
        except Exception as e:
            QMessageBox.warning(self, "Automatic Setup Error", f"Error running automatic setup:\n{e}")

    def show_setup_instructions(self):
        """Show a detailed setup guide in a scrollable window."""
        dialog = SetupInstructionsDialog(self)
        dialog.exec()



        ########################
        #    THEME SETTINGS    #
        ########################

    def change_theme(self, index):
        """
        Called when the theme selection is changed.
        Index 0 corresponds to Light Theme and 1 corresponds to Dark Theme.
        """
        if index == 0:
            self.apply_light_theme()
        else:
            self.apply_dark_theme()
        self.save_settings()

    # Light theme StyleSheet

    def apply_light_theme(self):
        """
        Apply a light theme.
        """
        light_stylesheet = """
        /* General Light Theme */
        QWidget {
            background-color: #FFFFFF; /* Light background */
            color: #333333;            /* Dark text */
            font-family: 'Segoe UI', sans-serif;
            border: none;
            selection-background-color: rgba(255, 72, 0, 0.81);
            selection-color: #333333;
        }

        /* ---------------------- */
        /*   Tab Widget Styling   */
        /* ---------------------- */
        QTabWidget::pane {
            border: 1px solid #CCCCCC;
            background-color: #FFFFFF;
        }
        QTabBar {
            background: #FFFFFF;
            border-bottom: 1px solid #CCCCCC;
        }
        QTabBar::tab {
            background: #EEEEEE;
            border: 1px solid #CCCCCC;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 5px 10px;
            margin: 0px;
            color: #333333;
        }
        QTabBar::tab:selected, QTabBar::tab:hover {
            background: #DDDDDD;
            color: black;
            border: 1px solid #AAAAAA;
        }
        QTabBar::tab:!selected {
            margin-top: 2px;
        }

        /* ---------------------- */
        /*      Button Styling    */
        /* ---------------------- */
        QPushButton {
            border-radius: 5px;
            padding: 3px 10px;
            background-color: #FFFFFF;
            color: #333333;
            border: 1px solid #CCCCCC;
        }
        QPushButton:hover {
            background-color: #F0F0F0;
        }
        QPushButton:disabled {
            background-color: #E0E0E0;
            color: #AAAAAA;
            border: 1px solid #CCCCCC;
        }

        /* ---------------------- */
        /*      Label Styling     */
        /* ---------------------- */
        QLabel {
            font-size: 12px;
            color: #333333;
        }

        /* ---------------------- */
        /*     Slider Styling     */
        /* ---------------------- */
        QSlider {
            background-color: #F0F0F0;
            border-radius: 5px;
        }
        QSlider::handle:horizontal {
            background-color: #ff4800;
            border-radius: 5px;
            width: 25px;
            height: 20px;
        }
        QSlider::groove:horizontal {
            background-color: #CCCCCC;
            height: 12px;
            border-radius: 5px;
        }
        QSlider::handle:disabled:horizontal {
            background-color: rgba(170, 170, 170, 0.5);
        }

        /* ---------------------- */
        /*    ComboBox Styling    */
        /* ---------------------- */
        QComboBox {
            border-radius: 5px;
            border: 1px solid #CCCCCC;
            padding: 5px;
            background-color: #FFFFFF;
            color: #333333;
        }
        QComboBox:hover {
            border: 1px solid #AAAAAA;
        }
        QComboBox:disabled {
            background-color:rgba(238, 238, 238, 0.8);
            color:rgba(136, 136, 136, 0.8);
            border: 1px solid #CCCCCC;
        }
        /* -------------------------- */
        /*  ComboBox Dropdown Styling */
        /* -------------------------- */
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
        }
        QComboBox QAbstractItemView::item {
            color: #333333;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: rgba(255, 72, 0, 0.51);
            color: #333333;
            border: none;
        }

        /* ---------------------- */
        /*   Checkbox Styling     */
        /* ---------------------- */
        QCheckBox {
            font-size: 14px;
            color: #333333;
            padding-left: 0px;
        }
        QCheckBox::indicator {
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: #FFFFFF;
            border: 2px solid #CCCCCC;
        }
        QCheckBox::indicator:checked {
            background-color: #ff4800;
            border: 2px solid #ff4800;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #b33200;
        }
        QCheckBox::indicator:unchecked:hover {
            background-color: #E0E0E0;
        }
        QCheckBox:disabled {
            color: #888888;
        }

        /* ---------------------- */
        /*  List Widget Styling   */
        /* ---------------------- */
        QListWidget {
            background-color: #FFFFFF;
            color: #333333;
            font-size: 14px;
            border: 1px solid #CCCCCC;
        }
        QListWidget::item {
            padding: 5px;
        }
        QListWidget::item:selected {
            background-color: #D0E7FF;
            color: #333333;
        }

        /* ---------------------- */
        /*   Scrollbar Styling    */
        /* ---------------------- */
        QScrollBar:vertical, QScrollBar:horizontal {
            border: none;
            background-color: #F0F0F0;
            width: 12px;
            height: 12px;
            margin: 0px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
            background-color: #ff4800;
            border-radius: 5px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
            background-color: #b33200;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            background: none;
        }
        QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical,
        QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
            background: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }

        /* ---------------------- */
        /*  Disabled SpinBoxes    */
        /* ---------------------- */
        QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color:rgba(238, 238, 238, 0.8);
            color:rgba(136, 136, 136, 0.8);
            border: 1px solid #CCCCCC;
        }
        /* ---------------------- */
        /*     SpinBoxes          */
        /* ---------------------- */
        QSpinBox, QDoubleSpinBox {
            background-color: #FFFFFF;
            color: #333333;
            font-size: 16px;
            border: 1px solid #CCCCCC;
        }


        /* ---------------------- */
        /*     LineEdits          */
        /* ---------------------- */
        QLineEdit {
            background-color: #FFFFFF;
            color: #333333;
            font-size: 14px;
            border: 1px solid #CCCCCC;
            border-radius: 5px;
            padding: 3px;
        }

        /* ---------------------- */
        /*     Group Box          */
        /* ---------------------- */
        QGroupBox {
            border: 1px solid #CCCCCC;
            margin-top: 15px;
            border-radius: 15px;
            padding: 3px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            padding: 0 0px;
        }

        /* ---------------------- */
        /*    Tooltip Styling     */
        /* ---------------------- */
        QToolTip {
            background-color:rgba(255, 255, 224, 0.8);
            color: #333333;
            border: 1px solid #CCCCCC;
            padding: 5px;
            border-radius: 5px;
        }

        /* ---------------------- */
        /*    Focus Effects       */
        /* ---------------------- */
        QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {
            border: 1px solid #000000;
        }
        """
        self.setStyleSheet(light_stylesheet)


    # Dark theme StyleSheet

    def apply_dark_theme(self):
        """
        Apply a dark theme.
        """
        dark_stylesheet = """
        /* General Dark Theme */
        QWidget {
            background-color: #2E2E2E; /* Dark background */
            color: #E0E0E0;          /* Light text for better readability */
            font-family: 'Segoe UI', sans-serif;
            border: none;
            selection-background-color: rgba(255, 72, 0, 0.81);
            selection-color: #E0E0E0;
        }

        /* ---------------------- */
        /*   Tab Widget Styling   */
        /* ---------------------- */
        QTabWidget::pane {
            border: 1px solid #444444;
            background-color: #2E2E2E;
        }
        QTabBar {
            background: #2E2E2E;
            border-bottom: 1px solid #444444;
        }
        QTabBar::tab {
            background: #444444;
            border: 1px solid #444444;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 5px 10px;
            margin: 0px;
            color: #E0E0E0;
        }
        QTabBar::tab:selected, QTabBar::tab:hover {
            background: #555555;
            color: white;
            border: 1px solid #777777;
        }
        QTabBar::tab:!selected {
            margin-top: 2px;
        }

        /* ---------------------- */
        /*      Button Styling    */
        /* ---------------------- */
        QPushButton {
            border-radius: 5px;
            padding: 3px 10px;
            background-color: #444444;
            color: white;
            border: 1px solid #666666;
        }
        QPushButton:hover {
            background-color: #555555;
        }
        QPushButton:disabled {
            background-color: #555555;
            color: #888888;
            border: 1px solid #666666;
        }

        /* ---------------------- */
        /*      Label Styling     */
        /* ---------------------- */
        QLabel {
            font-size: 12px;
            color: #DDDDDD;
        }

        /* ---------------------- */
        /*     Slider Styling     */
        /* ---------------------- */
        QSlider {
            background-color: #444444;
            border-radius: 5px;
        }
        QSlider::handle:horizontal {
            background-color: #ff4800;
            border-radius: 5px;
            width: 24px;
            height: 12px;
        }
        QSlider::groove:horizontal {
            background-color: #777777;
            height: 12px;
            border-radius: 5px;
        }
        QSlider::handle:disabled:horizontal {
            background-color: #888888;
        }

        /* ---------------------- */
        /*    ComboBox Styling    */
        /* ---------------------- */
        QComboBox {
            border-radius: 5px;
            border: 1px solid #666666;
            padding: 5px;
            background-color: #444444;
            color: white;
        }
        QComboBox:hover {
            border: 1px solid #888888;
        }
        QComboBox:disabled {
            background-color: #555555;
            color: #888888;
            border: 1px solid #666666;
        }
        /* -------------------------- */
        /*  ComboBox Dropdown Styling */
        /* -------------------------- */
        QComboBox QAbstractItemView {
            background-color: #444444;
            border: 1px solid #666666;
        }

        QComboBox QAbstractItemView::item {
            color: white;
        }

        /* Style the highlighted item */
        QComboBox QAbstractItemView::item:selected {
            background-color:rgba(255, 72, 0, 0.51); 
            color: white;
            border: none;
        }

        /* ---------------------- */
        /*   Checkbox Styling     */
        /* ---------------------- */
        QCheckBox {
            font-size: 14px;
            color: #DDDDDD;
            padding-left: 0px;
        }
        QCheckBox::indicator {
            width: 10px;
            height: 10px;
            border-radius: 5px;
            background-color: #444444;
            border: 2px solid #666666;
        }
        QCheckBox::indicator:checked {
            background-color: #ff4800;
            border: 2px solid #ff4800;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #b33200
        }
        QCheckBox::indicator:unchecked:hover {
            background-color: #888888
        }
        QCheckBox:disabled {
            color: #888888;
        }

        /* ---------------------- */
        /*  List Widget Styling   */
        /* ---------------------- */
        QListWidget {
            background-color: #333333;
            color: white;
            font-size: 14px;
            border: 1px solid #666666;
        }
        QListWidget::item {
            padding: 5px;
        }
        QListWidget::item:selected {
            background-color: #ff4800;
            color: white;
        }

        /* ---------------------- */
        /*   Scrollbar Styling    */
        /* ---------------------- */
        QScrollBar:vertical, QScrollBar:horizontal {
            border: none;
            background-color: #666666; /* Dark background */
            width: 12px;
            height: 12px;
            margin: 0px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
            background-color: #ff4800;
            border-radius: 5px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
            background-color: #b33200;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            background: none;
        }
        QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical,
        QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
            background: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }

        /* ---------------------- */
        /*  Disabled SpinBoxes    */
        /* ---------------------- */
        QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color: #555555;
            color: #888888;
            border: 1px solid #666666;
        }
        /* ---------------------- */
        /*     SpinBoxes          */
        /* ---------------------- */
        QSpinBox, QDoubleSpinBox {
        background-color: #444444;
        color: #DDDDDD;
        font-size: 16px;
        border: 1px solid #666666;
        }

        /* ---------------------- */
        /*     LineEdits          */
        /* ---------------------- */
        QLineEdit {
        background-color: #444444;
        color: #DDDDDD;
        font-size: 14px;
        border: 1px solid #666666;
        border-radius: 5px;
        padding: 3px;
        }
        /* ---------------------- */
        /*     Group Box          */
        /* ---------------------- */
        QGroupBox {
            border: 1px solid #666666;
            margin-top: 15px;
            border-radius: 15px;
            padding: 3px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            padding: 0 0px;
        }
        /* ---------------------- */
        /*    Tooltip Styling     */
        /* ---------------------- */
        QToolTip {
            background-color: #444444;
            color: #E0E0E0;
            border: 1px solid #777777;
            padding: 5px;
            border-radius: 5px;
        }
        /* ---------------------- */
        /*    Focus Effects       */
        /* ---------------------- */
        QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {
            border: 1px solid #DDDDDD;
        }
        """
        self.setStyleSheet(dark_stylesheet)






        ########################
        #    START SYNCING     #
        ########################

    def startSyncing(self):
        # Check if the segments.json file exists and is not empty.
        segments_file = "segments.json"
        if not os.path.exists(segments_file):
            QMessageBox.warning(self, "No Segments Selected",
                                "No segments file found. Please save segments using the 'Edit Segments' button before syncing.")
            return
        try:
            with open(segments_file, "r") as f:
                segments_data = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Segments Error",
                                "Error reading segments file. Please check segments.json.")
            return
        if not segments_data:
            QMessageBox.warning(self, "No Segments Selected",
                                "The segments file is empty. Please select segments before syncing.")
            return

        global DEVICEID, DEVICEIP, DEVICEKEY, DEVICEVERS
        # Update globals from the UI fields.
        DEVICEID = self.device_id_lineedit.text().strip() or self.device_default["device_id"]
        DEVICEIP = self.device_ip_lineedit.text().strip() or self.device_default["device_ip"]
        DEVICEKEY = self.device_key_lineedit.text().strip() or self.device_default["device_key"]
        DEVICEVERS = self.device_version_lineedit.text().strip() or self.device_default["device_version"]

        # Check if any required device info is missing or still default.
        if not DEVICEID or not DEVICEIP or not DEVICEKEY or not DEVICEVERS or \
        DEVICEID == self.device_default["device_id"] or \
        DEVICEIP == self.device_default["device_ip"] or \
        DEVICEKEY == self.device_default["device_key"]:
            QMessageBox.warning(self, "Missing Device Information",
                                "Please fill in all required device information fields before syncing.")
            return

        try:
            # Reconnect using the updated globals.
            self.device = tinytuya.OutletDevice(DEVICEID, DEVICEIP, DEVICEKEY)
            self.device.set_version(float(DEVICEVERS))
            self.device.set_socketPersistent(True)
        except Exception as e:
            QMessageBox.warning(self, "Device Connection Error",
                                f"Error connecting to the device: {e}")
            return

        # Reconnect device and initialize screen capture, etc.
        self.reconnect_device()
        self.sendBlackToInactiveSegments()
        self.sync_running = True
        self.syncIndicator.setPixmap(
            QPixmap(resource_path("icons/green_icon.png")).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        time_bindings.initScreenCapture()

        # Create the worker thread and connect its errorOccurred signal to the error handler.
        self.worker = Worker(self.autoSetColors, self.device, self.reconnect_device)
        self.worker.errorOccurred.connect(self.handle_device_error)
        self.worker.start()



        ########################
        #     STOP SYNCING     #
        ########################

    def stopSyncing(self):
        """Stop the syncing process by stopping the worker thread."""
        if self.sync_running and self.worker is not None:
            self.sync_running = False
            self.syncIndicator.setPixmap(
                QPixmap(resource_path("icons/grey_icon.png")).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            # Tell the worker to stop and wait for it to finish.
            self.worker.stop()      # This sets self._running = False in the worker.
            self.commands = {}
            self.worker.wait()      # Wait until the worker thread finishes.
            #print("Syncing stopped.")      # DEBUG




        ########################
        #   SEND AND RECEIVE   #
        ########################

    def reconnect_device(self):
        try:
            self.device = tinytuya.OutletDevice(DEVICEID, DEVICEIP, DEVICEKEY)
            self.device.set_version(float(DEVICEVERS))
            self.device.set_socketPersistent(True)
            print("Reconnected to the device successfully.")
        except Exception as e:
            if "905" in str(e) or "901" in str(e):
                raise Exception("Device Error (" + ("905" if "905" in str(e) else "901") + ") during reconnect: " + str(e))
            else:
                print(f"Failed to reconnect: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                self.reconnect_device()

    # Turn "off" inactive segments
    def sendBlackToInactiveSegments(self):
        inactive_segments = [seg for seg, cb in self.segment_checkboxes.items() if not cb.isChecked()]
        black_commands = {}
        black_codes = {
            1: "AAIAFAEAAAAAAACBFA==",
            2: "AAIAFAEAAAAAAACBEw==",
            3: "AAIAFAEAAAAAAACBEg==",
            4: "AAIAFAEAAAAAAACBEQ==",
            5: "AAIAFAEAAAAAAACBEA==",
            6: "AAIAFAEAAAAAAACBDw==",
            7: "AAIAFAEAAAAAAACBDg==",
            8: "AAIAFAEAAAAAAACBDQ==",
            9: "AAIAFAEAAAAAAACBDA==",
            10: "AAIAFAEAAAAAAACBCw==",
            11: "AAIAFAEAAAAAAACBCg==",
            12: "AAIAFAEAAAAAAACBCQ==",
            13: "AAIAFAEAAAAAAACBCA==",
            14: "AAIAFAEAAAAAAACBBw==",
            15: "AAIAFAEAAAAAAACBBg==",
            16: "AAIAFAEAAAAAAACBBQ==",
            17: "AAIAFAEAAAAAAACBBA==",
            18: "AAIAFAEAAAAAAACBAw==",
            19: "AAIAFAEAAAAAAACBAg==",
            20: "AAIAFAEAAAAAAACBAQ=="
        }

        for seg in inactive_segments:
            key = f"61_{seg}"
            if self.prev_colors.get(seg) != black_codes[seg]:
                black_commands[key] = black_codes[seg]

        if black_commands:
            payload = self.device.generate_payload(tinytuya.CONTROL, black_commands)
            #print(f"Generated Payload for black commands: {payload}")      # DEBUG
            self.device._send_receive(payload)
            #print(f"Control Data Command Sent for inactive segments: {black_commands}")    # DEBUG
            for seg in inactive_segments:
                if seg in black_codes:
                    self.prev_colors[seg] = black_codes[seg]
        #else:      # DEBUG
            #print("All inactive segments are already black. No command sent.")     # DEBUG

    def send_and_verify(self, sorted_commands):
        retries = self.advanced_retries
        max_sleep_interval = self.advanced_max_sleep_interval
        back_off_timer = self.advanced_back_off_timer
        command_count = 0

        for attempt in range(retries):
            try:
                payload = self.device.generate_payload(tinytuya.CONTROL, sorted_commands)
                self.device._send_receive(payload)

                ping_output = subprocess.run(
                    ["ping", "-n", "1", DEVICEIP],
                    text=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                ).stdout

                # Check for error 901:
                if "Unable to Connect" in ping_output or "901" in ping_output:
                    msg = "Unable to Connect (901). Please check your network connection."
                    self.deviceOffline.emit(msg)
                    self.stopSyncing()
                    raise Exception(msg)

                # Check for error 905:
                if "Destination host unreachable" in ping_output:
                    msg = ("The device is unreachable. Please check if your device is still connected to the network. "
                        "It may have been overloaded and gone offline; a reset (unplug) may be required.")
                    self.deviceOffline.emit(msg)
                    self.stopSyncing()
                    raise Exception(msg)

                if "Lost = 1" in ping_output:
                    time_remaining = self.advanced_reconnect_delay
                    while time_remaining > 0:
                        time.sleep(1)
                        time_remaining -= 1
                    self.reconnect_device()
                    continue

                # Use advanced max_ping_time as fallback:
                max_ping_time = self.advanced_max_ping_time
                for line in ping_output.splitlines():
                    if "time=" in line:
                        time_ms = int(line.split("time=")[-1].split("ms")[0].strip())
                        max_ping_time = max(max_ping_time, time_ms)

                if command_count < 5:
                    self.sleep_interval = max_ping_time / 1000.0 + self.advanced_extra_sleep_initial
                else:
                    self.sleep_interval = (max_ping_time / 1000.0) + self.advanced_extra_sleep_later

                command_count = (command_count + 1) % 20

                last_heartbeat_time = time.time()
                start_loop_time = time.time()
                while True:
                    current_time = time.time()
                    elapsed_time = current_time - start_loop_time
                    time_remaining = self.sleep_interval - elapsed_time
                    if time_remaining <= 0:
                        break
                    if current_time - last_heartbeat_time >= max_sleep_interval:
                        try:
                            self.device.heartbeat(nowait=True)
                        except Exception as e:
                            self.reconnect_device()
                        last_heartbeat_time = current_time
                    time.sleep(0.1)

                status = self.device.status()
                if status:
                    return True

            except Exception as e:
                # If the error message contains "901" or "905", let it propagate.
                if "901" in str(e) or "905" in str(e):
                    raise e
                else:
                    self.reconnect_device()
            back_off_timer *= 1.5

        return False



    def autoSetColors(self):
        self.last_command_time = time.time()
        self.last_no_color_change_time = time.time()
        last_pause_time = None

        # Ensure self.commands is a dict.
        if isinstance(self.commands, str):
            try:
                self.commands = json.loads(self.commands)
            except Exception:
                self.commands = {}

        if self.set_brightness_checkbox.isChecked():
            uniform_brightness = self.brightness_slider.value()
            if not isinstance(self.commands, dict):
                self.commands = {}
            for segment, command in self.commands.items():
                self.commands[segment] = self.applyUniformBrightness(command, uniform_brightness)

        while self.sync_running:
            current_time = time.time()
            command_elapsed_time = current_time - self.last_command_time
            no_color_change_elapsed_time = current_time - self.last_no_color_change_time
            elapsed_time = current_time - last_pause_time if last_pause_time else None

            if no_color_change_elapsed_time >= self.advanced_no_color_change_threshold:
                if elapsed_time is None or elapsed_time >= self.advanced_no_color_change_threshold:
                    time_remaining = self.advanced_pause_duration
                    while time_remaining > 0 and self.sync_running:
                        time.sleep(1)
                        time_remaining -= 1
                    last_pause_time = current_time

            if not self.sync_running:
                break  # Exit if stop was requested

            if command_elapsed_time >= self.advanced_command_elapsed_threshold:
                try:
                    self.device.heartbeat(nowait=True)
                    self.last_command_time = current_time
                except Exception as e:
                    self.reconnect_device()

            result = call_cpp_processor()
            commands_result = result.get("commands", {})
            # Convert to dict if needed.
            if isinstance(commands_result, str):
                try:
                    commands_result = json.loads(commands_result)
                except Exception:
                    commands_result = {}
            self.commands = commands_result
            if not isinstance(self.commands, dict):
                try:
                    self.commands = json.loads(self.commands)
                except Exception:
                    self.commands = {}

            # Process the commands. sendAllCommands will filter out commands that haven't changed.
            self.sendAllCommands()

            # Now check for device errors.
            try:
                status = self.device.status()
                if isinstance(status, dict):
                    err = str(status.get("Err", ""))
                    if "905" in err or "901" in err or "914" in err:
                        msg = f"Device Error ({err})"
                        if "901" in err:
                            msg += " Check Network Connection."
                        elif "905" in err:
                            msg += " Check Device Info."
                        elif "914" in err:
                            msg += " Check Device Key or Version."
                        self.deviceOffline.emit(msg)
                        self.stopSyncing()
                        raise Exception(msg)
                # Let any exceptions from status() propagate.
            except Exception as ex:
                raise ex

            time.sleep(self.sleep_interval)

    def sendAllCommands(self):
        if not isinstance(self.commands, dict):
            self.commands = {}
        active_segment_numbers = [seg for seg, cb in self.segment_checkboxes.items() if cb.isChecked()]
        new_commands = {}
        for k, v in self.commands.items():
            seg = int(k.split('_')[1])
            if seg in active_segment_numbers:
                # Create a canonical version of the command for comparison.
                new_val = json.dumps(v, sort_keys=True)
                old_val = self.prev_colors.get(seg)
                if old_val != new_val:
                    new_commands[k] = v
        self.commands = new_commands
        if not self.commands:
            self.last_no_color_change_time = time.time()
            return
        sorted_commands = {
            k: self.commands[k] for k in sorted(self.commands.keys(), key=lambda x: int(x.split('_')[1]))
        }
        if self.send_and_verify(sorted_commands):
            # Update prev_colors with the canonical version.
            for k, v in sorted_commands.items():
                seg = int(k.split('_')[1])
                self.prev_colors[seg] = json.dumps(v, sort_keys=True)
            self.last_command_time = time.time()






        ########################
        #    RESET SETTINGS    #
        ########################

    def reset_basic_defaults(self):
        # Ask the user for confirmation
        reply = QMessageBox.question(
            self,
            "Reset Basic Settings",
            "Are you sure you want to reset basic settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # Default is No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return  # User chose not to reset

        # Reset basic settings to defaults:
        self.set_brightness_checkbox.setChecked(False)
        self.brightness_slider.setValue(500)
        self.set_color_boost_checkbox.setChecked(False)
        self.color_boost_spinbox.setValue(1.0)
        self.component_threshold_spinbox.setValue(250)
        self.manhattan_threshold_spinbox.setValue(150.0)
        self.letterbox_checkbox.setChecked(True)

        # Reset active segments (check all segments):
        for segment, checkbox in self.segment_checkboxes.items():
            checkbox.setChecked(True)

        # Save the new settings so that they persist.
        self.save_settings()
        #print("Basic settings have been reset to defaults.")       # DEBUG


    def reset_advanced_defaults(self):
        # Show a confirmation dialog
        reply = QMessageBox.question(
            self,
            "Reset Advanced Settings",
            "Are you sure you want to reset all advanced settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        # If the user selects 'No', do nothing
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Restore all advanced settings from the defaults dictionary.
        self.advanced_retries = self.advanced_defaults["retries"]
        self.advanced_max_sleep_interval = self.advanced_defaults["max_sleep_interval"]
        self.advanced_back_off_timer = self.advanced_defaults["back_off_timer"]
        self.advanced_reconnect_delay = self.advanced_defaults["reconnect_delay"]
        self.advanced_extra_sleep_initial = self.advanced_defaults["extra_sleep_initial"]
        self.advanced_extra_sleep_later = self.advanced_defaults["extra_sleep_later"]
        self.advanced_no_color_change_threshold = self.advanced_defaults["no_color_change_threshold"]
        self.advanced_pause_duration = self.advanced_defaults["pause_duration"]
        self.advanced_command_elapsed_threshold = self.advanced_defaults["command_elapsed_threshold"]
        self.advanced_max_ping_time = self.advanced_defaults["max_ping_time"]
        self.advanced_overlay_opacity = self.advanced_defaults["overlay_opacity"]

        # Update the spin boxes to reflect these default values.
        self.retries_spinbox.setValue(self.advanced_retries)
        self.max_sleep_spinbox.setValue(self.advanced_max_sleep_interval)
        self.back_off_spinbox.setValue(self.advanced_back_off_timer)
        self.reconnect_delay_spinbox.setValue(self.advanced_reconnect_delay)
        self.extra_sleep_initial_spinbox.setValue(self.advanced_extra_sleep_initial)
        self.extra_sleep_later_spinbox.setValue(self.advanced_extra_sleep_later)
        self.no_color_change_spinbox.setValue(self.advanced_no_color_change_threshold)
        self.pause_duration_spinbox.setValue(self.advanced_pause_duration)
        self.command_elapsed_spinbox.setValue(self.advanced_command_elapsed_threshold)
        self.max_ping_time_spinbox.setValue(self.advanced_max_ping_time)
        self.overlay_opacity_spinbox.setValue(self.advanced_overlay_opacity)
        self.threshold_value_spinbox.setValue(self.advanced_defaults["threshold_value"])

        self.save_settings()
        #print("Advanced settings have been reset to defaults.")        # DEBUG



        ########################
        #    SAVE SETTINGS     #
        ########################

    def set_advanced_setting(self, key, value):
        if key == 'retries':
            self.advanced_retries = value
        elif key == 'max_sleep_interval':
            self.advanced_max_sleep_interval = value
        elif key == 'back_off_timer':
            self.advanced_back_off_timer = value
        elif key == 'reconnect_delay':
            self.advanced_reconnect_delay = value
        elif key == 'extra_sleep_initial':
            self.advanced_extra_sleep_initial = value
        elif key == 'extra_sleep_later':
            self.advanced_extra_sleep_later = value
        elif key == 'no_color_change_threshold':
            self.advanced_no_color_change_threshold = value
        elif key == 'pause_duration':
            self.advanced_pause_duration = value
        elif key == 'command_elapsed_threshold':
            self.advanced_command_elapsed_threshold = value
        elif key == 'max_ping_time':
            self.advanced_max_ping_time = value
        elif key == 'overlay_opacity':
            self.advanced_overlay_opacity = value
        self.save_settings()

    def save_device_setup(self):
        global DEVICEID, DEVICEIP, DEVICEKEY, DEVICEVERS
        # Read the device info from the QLineEdit fields.
        # If a field is blank, fall back to the default.
        DEVICEID = self.device_id_lineedit.text().strip() or self.device_default["device_id"]
        DEVICEIP = self.device_ip_lineedit.text().strip() or self.device_default["device_ip"]
        DEVICEKEY = self.device_key_lineedit.text().strip() or self.device_default["device_key"]
        DEVICEVERS = self.device_version_lineedit.text().strip() or self.device_default["device_version"]
        #print("Device details updated:")       # DEBUG
        #print(f"  DEVICEID: {DEVICEID}")       # DEBUG
        #print(f"  DEVICEIP: {DEVICEIP}")       # DEBUG
        ##print(f"  DEVICEKEY: {DEVICEKEY}")    # DEBUG
        #print(f"  DEVICEVERS: {DEVICEVERS}")   # DEBUG
        self.save_settings()  # Save all settings.
        self.reconnect_device()

    def save_settings(self):
        settings = {
            "selected_monitor_index": self.monitor_combobox.currentData(),
            "set_uniform_brightness": self.set_brightness_checkbox.isChecked(),
            "uniform_brightness": self.brightness_slider.value(),
            "set_color_boost": self.set_color_boost_checkbox.isChecked(),
            "color_boost_factor": self.color_boost_spinbox.value(),
            "component_threshold": self.component_threshold_spinbox.value(),
            "manhattan_threshold": self.manhattan_threshold_spinbox.value(),
            "enable_letterbox_detection": self.letterbox_checkbox.isChecked(),
            # Advanced settings:
            "retries": self.advanced_retries,
            "max_sleep_interval": self.advanced_max_sleep_interval,
            "back_off_timer": self.advanced_back_off_timer,
            "reconnect_delay": self.advanced_reconnect_delay,
            "extra_sleep_initial": self.advanced_extra_sleep_initial,
            "extra_sleep_later": self.advanced_extra_sleep_later,
            "no_color_change_threshold": self.advanced_no_color_change_threshold,
            "pause_duration": self.advanced_pause_duration,
            "command_elapsed_threshold": self.advanced_command_elapsed_threshold,
            "max_ping_time": self.advanced_max_ping_time,
            "overlay_opacity": self.advanced_overlay_opacity,
            "threshold_value": self.threshold_value_spinbox.value(),

            # Device Setup details:
            "device_id": self.device_id_lineedit.text(),
            "device_ip": self.device_ip_lineedit.text(),
            "device_key": self.device_key_lineedit.text(),
            "device_version": self.device_version_lineedit.text(),
        }

        # Add API credentials from self.settings if available.
        settings["api_key"] = self.settings.get("api_key", "")
        settings["api_secret"] = self.settings.get("api_secret", "")
        settings["api_region"] = self.settings.get("api_region", "")

        # Theme and Tabs
        settings["theme_index"] = self.theme_combobox.currentIndex()
        settings["last_tab_index"] = self.tab_widget.currentIndex()
        try:
            with open("settings.json", "w") as file:
                json.dump(settings, file, indent=4)
            #print("Settings saved successfully:", settings)        # DEBUG
            self.settings = settings
        except Exception as e:
            print(f"Error saving settings: {e}")



        ########################
        #    LOAD SETTINGS     #
        ########################

    def load_settings(self):
        try:
            with open("settings.json", "r") as file:
                settings = json.load(file)
        except Exception as e:
            #print(f"Error loading settings: {e}")      # DEBUG
            settings = {}

        # Save loaded settings in self.settings for later use.
        self.settings = settings

        # Load basic settings.
        self.set_brightness_checkbox.setChecked(settings.get("set_uniform_brightness", False))
        self.brightness_slider.setValue(settings.get("uniform_brightness", 500))
        self.set_color_boost_checkbox.setChecked(settings.get("set_color_boost", False))
        self.color_boost_spinbox.setValue(settings.get("color_boost_factor", 1.0))
        self.component_threshold_spinbox.setValue(settings.get("component_threshold", 250))
        self.manhattan_threshold_spinbox.setValue(settings.get("manhattan_threshold", 150.0))
        self.letterbox_checkbox.setChecked(settings.get("enable_letterbox_detection", True))

        # Load advanced settings.
        self.advanced_retries = settings.get("retries", self.advanced_defaults["retries"])
        self.advanced_max_sleep_interval = settings.get("max_sleep_interval", self.advanced_defaults["max_sleep_interval"])
        self.advanced_back_off_timer = settings.get("back_off_timer", self.advanced_defaults["back_off_timer"])
        self.advanced_reconnect_delay = settings.get("reconnect_delay", self.advanced_defaults["reconnect_delay"])
        self.advanced_extra_sleep_initial = settings.get("extra_sleep_initial", self.advanced_defaults["extra_sleep_initial"])
        self.advanced_extra_sleep_later = settings.get("extra_sleep_later", self.advanced_defaults["extra_sleep_later"])
        self.advanced_no_color_change_threshold = settings.get("no_color_change_threshold", self.advanced_defaults["no_color_change_threshold"])
        self.advanced_pause_duration = settings.get("pause_duration", self.advanced_defaults["pause_duration"])
        self.advanced_command_elapsed_threshold = settings.get("command_elapsed_threshold", self.advanced_defaults["command_elapsed_threshold"])
        self.advanced_max_ping_time = settings.get("max_ping_time", self.advanced_defaults["max_ping_time"])
        self.advanced_overlay_opacity = settings.get("overlay_opacity", self.advanced_defaults["overlay_opacity"])

        self.retries_spinbox.setValue(self.advanced_retries)
        self.max_sleep_spinbox.setValue(self.advanced_max_sleep_interval)
        self.back_off_spinbox.setValue(self.advanced_back_off_timer)
        self.reconnect_delay_spinbox.setValue(self.advanced_reconnect_delay)
        self.extra_sleep_initial_spinbox.setValue(self.advanced_extra_sleep_initial)
        self.extra_sleep_later_spinbox.setValue(self.advanced_extra_sleep_later)
        self.no_color_change_spinbox.setValue(self.advanced_no_color_change_threshold)
        self.pause_duration_spinbox.setValue(self.advanced_pause_duration)
        self.command_elapsed_spinbox.setValue(self.advanced_command_elapsed_threshold)
        self.max_ping_time_spinbox.setValue(self.advanced_max_ping_time)
        self.overlay_opacity_spinbox.setValue(self.advanced_overlay_opacity)
        self.threshold_value_spinbox.setValue(settings.get("threshold_value", 10))
        theme_index = settings.get("theme_index", 0)
        self.theme_combobox.setCurrentIndex(theme_index)
        self.change_theme(theme_index)
        # Set the last active tab otherwise, default to Device Setup (index 0)
        last_tab_index = settings.get("last_tab_index", 0)
        self.tab_widget.setCurrentIndex(last_tab_index)
        # Load Device Setup details.
        self.device_id_lineedit.setText(settings.get("device_id", self.device_default["device_id"]))
        self.device_ip_lineedit.setText(settings.get("device_ip", self.device_default["device_ip"]))
        self.device_key_lineedit.setText(settings.get("device_key", self.device_default["device_key"]))
        self.device_version_lineedit.setText(settings.get("device_version", self.device_default["device_version"]))

        # Load selected monitor index
        saved_monitor_index = settings.get("selected_monitor_index", 1)
        index_in_combo = self.monitor_combobox.findData(saved_monitor_index)
        if index_in_combo != -1:
            self.monitor_combobox.setCurrentIndex(index_in_combo)

        #print("Loaded API credentials:",       # DEBUG
#            settings.get("api_key", ""),       # DEBUG
#            settings.get("api_secret", ""),    # DEBUG
#            settings.get("api_region", ""))    # DEBUG

        # immediately save settings so the file reflects any defaults.
        self.save_settings()

    def load_active_segments(self):
        active_segments = set()
        try:
            with open('segments.json', 'r') as f:
                segments_data = json.load(f)
            active_segments = {int(seg_key) for seg_key in segments_data.keys()}
        except Exception as e:
            #print(f"Could not load segments.json, using default settings. Error: {e}")     # DEBUG
            active_segments = set(range(1, self.total_segments + 1))
        return active_segments




if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Create a splash screen with an image 
    splash_pix = QPixmap(resource_path("icons/splash.png"))
    splash = QSplashScreen(splash_pix)
    font = QFont("Arial", 8)
    splash.setFont(font)
    splash.show()
    app.processEvents()

    # Set up tinytuya debugging to use the logging module
    # Attach the custom splash handler to the tinytuya logger.
    tinytuya_logger = logging.getLogger("tinytuya")
    tinytuya_logger.setLevel(logging.DEBUG)
    tinytuya_logger.addHandler(SplashScreenHandler(splash))
    
    # Enable debug output in tinytuya
    tinytuya.set_debug(toggle=True, color=False)
    # Create the main window (this will run the tinytuya initialization)
    color_picker = ColorPicker()
    time.sleep(1.5)
    # Update splash message before showing the GUI
    splash.showMessage("Done.", 
                         Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, 
                         Qt.GlobalColor.white)
    app.processEvents()
    time.sleep(0.5)
    color_picker.show()
    splash.finish(color_picker)

    sys.exit(app.exec())
