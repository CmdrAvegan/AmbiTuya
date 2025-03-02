#include <opencv2/opencv.hpp>
#include <iostream>
#include <vector>
#include <json/json.h>
#include <sstream>
#include <iomanip>
#define NOMINMAX
#include <windows.h>
#undef min
#include <algorithm>
#include <fstream>
#include <cmath>
#include <map>
#include <mutex>
#include <thread>
#include <future>
#include <rapidjson/document.h>
#include <rapidjson/writer.h>
#include <rapidjson/stringbuffer.h>
#include <queue>
#include <condition_variable>
#include <opencv2/imgproc.hpp>
//#define DEBUG  // Uncomment this for debugging, comment it for release

std::map<int, std::tuple<int, int, int>> prev_colors;
cv::Vec3b computeDominantColor(const cv::Mat& roi);
std::string convertToBase64(const std::vector<uint8_t>& data);
std::string buildCommand(int segment, const cv::Vec3b& color);
cv::Mat captureScreen();
bool set_uniform_brightness = false;
int uniform_brightness = 500;  // Default value
std::mutex color_mutex;
bool set_color_boost = false;
double color_boost_factor = 1.0;  // 1.0 means no boost, >1.0 increases saturation
static cv::Mat prevFrame;
int component_threshold = 250;          // Sensitivity for individual color components
double manhattan_threshold = 150.0;     // Sensitivity for the Manhattan color distance
bool enable_letterbox_detection = true;
int threshold_value = 10;

namespace {
    // Global (file‑scope) variables for screen capture:
    HWND g_hwnd = nullptr;
    HDC g_hwindowDC = nullptr;
    HDC g_hwindowCompatibleDC = nullptr;
    int g_monitorIndex = 1;  // Default to primary monitor
    int g_monitorX = 0, g_monitorY = 0;  // Capture region offsets
    int g_screenWidth = 0;
    int g_screenHeight = 0;
    HBITMAP g_hbwindow = nullptr;
    bool g_initialized = false;
}
// Setter function to change letterbox detection.
extern "C" void set_letterbox_detection(bool enable) {
    enable_letterbox_detection = enable;
}

void loadMonitorIndexFromSettings() {
    std::ifstream settingsFile("settings.json");
    if (!settingsFile.is_open()) {
        std::cerr << "Failed to open settings.json. Using default monitor." << std::endl;
        return;
    }

    Json::Value root;
    settingsFile >> root;
    settingsFile.close();

    if (root.isMember("selected_monitor_index") && root["selected_monitor_index"].isInt()) {
        g_monitorIndex = root["selected_monitor_index"].asInt();
        std::cout << "Using monitor index: " << g_monitorIndex << std::endl;
    } else {
        std::cerr << "Monitor index not found in settings.json. Using default." << std::endl;
    }
}
BOOL CALLBACK MonitorEnumProc(HMONITOR hMonitor, HDC hdcMonitor, LPRECT lprcMonitor, LPARAM dwData) {
    int* pCount = reinterpret_cast<int*>(dwData);
    (*pCount)++;
    if (*pCount == g_monitorIndex) {
        // Store the monitor's coordinates
        g_monitorX = lprcMonitor->left;
        g_monitorY = lprcMonitor->top;
        g_screenWidth = lprcMonitor->right - lprcMonitor->left;
        g_screenHeight = lprcMonitor->bottom - lprcMonitor->top;
        return FALSE; // Stop enumeration after finding the desired monitor.
    }
    return TRUE;
}

extern "C" void initScreenCapture() {
    if (g_initialized) {
        if (g_hbwindow) {
            DeleteObject(g_hbwindow);
            g_hbwindow = nullptr;
        }
        if (g_hwindowCompatibleDC) {
            DeleteDC(g_hwindowCompatibleDC);
            g_hwindowCompatibleDC = nullptr;
        }
        if (g_hwindowDC && g_hwnd) {
            ReleaseDC(g_hwnd, g_hwindowDC);
            g_hwindowDC = nullptr;
        }
        g_initialized = false;
    }

    loadMonitorIndexFromSettings();  // Read the new monitor index

    // Reset monitor count using a local counter
    int monitorCounter = 0;
    EnumDisplayMonitors(nullptr, nullptr, MonitorEnumProc, reinterpret_cast<LPARAM>(&monitorCounter));

    // Use GetDesktopWindow() to obtain a device context (this works even if capturing a region)
    g_hwnd = GetDesktopWindow();
    g_hwindowDC = GetDC(g_hwnd);
    g_hwindowCompatibleDC = CreateCompatibleDC(g_hwindowDC);

    // If no valid monitor was found, fallback to the primary monitor
    if (g_screenWidth == 0 || g_screenHeight == 0) {
        g_screenWidth = GetDeviceCaps(g_hwindowDC, HORZRES);
        g_screenHeight = GetDeviceCaps(g_hwindowDC, VERTRES);
        g_monitorX = 0;
        g_monitorY = 0;
    }

    g_hbwindow = CreateCompatibleBitmap(g_hwindowDC, g_screenWidth, g_screenHeight);
    if (!g_hbwindow) {
        std::cerr << "Failed to create compatible bitmap!" << std::endl;
        DeleteDC(g_hwindowCompatibleDC);
        ReleaseDC(g_hwnd, g_hwindowDC);
        return;
    }

    g_initialized = true;
}


extern "C" void switchMonitorCapture() {
    // Free existing resources if initialized
    if (g_initialized) {
        if (g_hbwindow) {
            DeleteObject(g_hbwindow);
            g_hbwindow = nullptr;
        }
        if (g_hwindowCompatibleDC) {
            DeleteDC(g_hwindowCompatibleDC);
            g_hwindowCompatibleDC = nullptr;
        }
        if (g_hwindowDC && g_hwnd) {
            ReleaseDC(g_hwnd, g_hwindowDC);
            g_hwindowDC = nullptr;
        }
        g_initialized = false;
    }
    // Reinitialize capture resources (this will read the current monitor index from settings)
    initScreenCapture();
}

// Initialize the map with default RGB values
void initializePrevColors(int numSegments) {
    for (int i = 1; i <= numSegments; ++i) {
        prev_colors[i] = std::make_tuple(0, 0, 0); // Default to black
    }
}

// Compute the average pixel difference (motion intensity) between current and previous segment
double computeMotionIntensity(const cv::Mat& currSegment, const cv::Mat& prevSegment) {
    if (currSegment.empty() || prevSegment.empty() ||
        currSegment.size() != prevSegment.size()) {
        return 0.0;
    }
    cv::Mat diff;
    cv::absdiff(currSegment, prevSegment, diff);
    cv::Mat gray;
    cv::cvtColor(diff, gray, cv::COLOR_BGR2GRAY);
    // Average difference gives a measure of motion
    return cv::mean(gray)[0];
}

// Compute edge intensity using Canny edge detection.
// Returns a scaled measure of the edge density.
double computeEdgeIntensity(const cv::Mat& segment) {
    if (segment.empty()) {
        return 0.0;
    }
    cv::Mat gray, edges;
    cv::cvtColor(segment, gray, cv::COLOR_BGR2GRAY);
    cv::Canny(gray, edges, 50, 150);
    double edgeCount = cv::countNonZero(edges);
    double totalPixels = segment.rows * segment.cols;
    // Scale edge density to a value roughly in the 0-255 range
    return (totalPixels > 0) ? (edgeCount / totalPixels) * 255.0 : 0.0;
}

// Adjust the dominant color based on motion and edge intensities.
// boost brightness if there is motion and saturation if edges are strong.
cv::Vec3b adjustColorWithMotionAndEdges(const cv::Vec3b& color, double motionIntensity, double edgeIntensity) {
    // Convert BGR to HSV
    cv::Mat bgrPixel(1, 1, CV_8UC3, color);
    cv::Mat hsvPixel;
    cv::cvtColor(bgrPixel, hsvPixel, cv::COLOR_BGR2HSV);
    cv::Vec3b hsvColor = hsvPixel.at<cv::Vec3b>(0, 0);

    // Determine boost factors.
    double brightnessBoost = 1.0 + std::min(0.5, motionIntensity / 50.0); // boost up to 50%
    double saturationBoost = 1.0 + std::min(0.1, edgeIntensity / 50.0);    // boost up to 10%

    // Disable saturation boost if color boost option is enabled.
    if (set_color_boost) {
        saturationBoost = 1.0;
    }

    int newV = std::min(255, static_cast<int>(hsvColor[2] * brightnessBoost));
    int newS = std::min(255, static_cast<int>(hsvColor[1] * saturationBoost));
    hsvColor[2] = static_cast<uchar>(newV);
    hsvColor[1] = static_cast<uchar>(newS);
    hsvPixel.at<cv::Vec3b>(0, 0) = hsvColor;

    cv::Mat adjustedBGR;
    cv::cvtColor(hsvPixel, adjustedBGR, cv::COLOR_HSV2BGR);
    return adjustedBGR.at<cv::Vec3b>(0, 0);
}


// Set Brightness of the color based on the uniform brightness value (Could be improved)

cv::Vec3b applyProportionalBrightness(const cv::Vec3b& color, int uniformBrightness) {
    // Convert BGR to HSV
    cv::Mat bgrMat(1, 1, CV_8UC3); // Create a 1x1 matrix
    bgrMat.at<cv::Vec3b>(0, 0) = color; // Set the pixel to the input color
    cv::Mat hsvMat;
    cv::cvtColor(bgrMat, hsvMat, cv::COLOR_BGR2HSV);

    // Extract HSV components
    cv::Vec3b hsv = hsvMat.at<cv::Vec3b>(0, 0);
    int h = hsv[0]; // Hue
    int s = hsv[1]; // Saturation
    int v = hsv[2]; // Brightness (Value)

    // Avoid over-brightening very dark colors
    const int minBrightnessThreshold = 30; // Adjust threshold as needed
    if (v < minBrightnessThreshold) {
        return color; // Skip adjustment for very dark colors
    }

    // Scale brightness proportionally
    double scale = static_cast<double>(uniformBrightness) / 255.0;
    v = static_cast<int>(v * scale);
    v = (std::min)(v, 255); // Clamp to the maximum value using (std::min)

    // Update HSV with the scaled brightness
    hsv[2] = v;
    hsvMat.at<cv::Vec3b>(0, 0) = hsv;

    // Convert back to BGR
    cv::Mat resultMat;
    cv::cvtColor(hsvMat, resultMat, cv::COLOR_HSV2BGR);
    cv::Vec3b resultColor = resultMat.at<cv::Vec3b>(0, 0);

    return resultColor;
}

// Loads the previous colors from a file and initializes to default values if the file is not found.

void loadPrevColors(const std::string& filename) {
    std::ifstream file(filename);
    if (file.is_open()) {
        int segment, r, g, b;
        std::string line;
        while (std::getline(file, line)) {
            std::istringstream iss(line);
            if (iss >> segment >> r >> g >> b) {
                prev_colors[segment] = std::make_tuple(r, g, b);
                #ifdef DEBUG
                std::cerr << "Loaded segment " << segment << " with color ("
                          << r << ", " << g << ", " << b << ")\n";
                #endif
            }
        }
        file.close();
    } else {
        #ifdef DEBUG
        std::cerr << "Could not open file " << filename << ". Initializing to defaults.\n";
        #endif
        initializePrevColors(20); // Default to 20 segments; adjust as needed
    }
}


// Save the previous colors to a file for the next iteration.

void savePrevColors(const std::string& filename) {
    std::ofstream file(filename, std::ios::trunc); 
    if (file.is_open()) {
        for (const auto& [segment, color] : prev_colors) {
            file << segment << " "
                 << std::get<0>(color) << " "
                 << std::get<1>(color) << " "
                 << std::get<2>(color) << "\n";
        }
        file.close();
    } else {
        #ifdef DEBUG
        std::cerr << "Could not open file " << filename << " for writing.\n";
        #endif
    }
}

// Function to calculate RGB color difference with proper logging
double rgb_difference(const cv::Vec3b& color1, const cv::Vec3b& color2) {
    double diff = std::abs(color1[0] - color2[0]) +
                  std::abs(color1[1] - color2[1]) +
                  std::abs(color1[2] - color2[2]);
    #ifdef DEBUG
    std::cerr << "Comparing colors:\n"
              << "  Color1: [" << (int)color1[0] << ", " << (int)color1[1] << ", " << (int)color1[2] << "]\n"
              << "  Color2: [" << (int)color2[0] << ", " << (int)color2[1] << ", " << (int)color2[2] << "]\n"
              << "  Difference: " << diff << "\n";
    #endif
    return diff;
}

// Set a threshold to filter out small changes
const double COLOR_CHANGE_THRESHOLD = 150.0; // Adjust this value based on visual significance

// Function to check for significant color changes with logging (This prevents sending unnecessary commands)
bool is_significant_change(int segment, const cv::Vec3b& new_color) {
    auto it = prev_colors.find(segment);
    if (it == prev_colors.end()) {
        #ifdef DEBUG
        std::cerr << "No previous color found for segment " << segment
                  << ". Considering it a significant change.\n";
        #endif
        return true;
    }

    auto [prev_r, prev_g, prev_b] = it->second;
    double diff = rgb_difference(new_color, cv::Vec3b(prev_r, prev_g, prev_b));
    if (diff > COLOR_CHANGE_THRESHOLD) {
        return true;
    }
    return false;
}
bool is_significant_change(int segment, const cv::Vec3b& new_color) {
    auto it = prev_colors.find(segment);
    if (it == prev_colors.end()) {
        #ifdef DEBUG
        std::cerr << "No previous color found for segment " << segment
                  << ". Considering it a significant change.\n";
        #endif
        return true;
    }

    auto [prev_r, prev_g, prev_b] = it->second;
    int red_diff = std::abs(prev_r - new_color[2]);
    int green_diff = std::abs(prev_g - new_color[1]);
    int blue_diff = std::abs(prev_b - new_color[0]);

    double manhattan_diff = red_diff + green_diff + blue_diff;

    #ifdef DEBUG
    std::cerr << "Segment " << segment << " Previous Color: (" 
              << prev_r << ", " << prev_g << ", " << prev_b << ")\n"
              << "New Color: (" 
              << (int)new_color[2] << ", " 
              << (int)new_color[1] << ", " 
              << (int)new_color[0] << ")\n"
              << "Diff: Red=" << red_diff
              << ", Green=" << green_diff
              << ", Blue=" << blue_diff
              << ", Manhattan=" << manhattan_diff << "\n";
    #endif

    if (manhattan_diff > manhattan_threshold ||
        red_diff > component_threshold ||
        green_diff > component_threshold ||
        blue_diff > component_threshold) {
        return true;
    }
    return false;
}
// Load settings from a JSON file saved using the Python script.
void loadSettings() {
    std::ifstream file("settings.json");
    if (!file.is_open()) {
        std::cerr << "Error: Unable to open settings.json. Using default settings.\n";
        return;
    }

    Json::Value settings;
    file >> settings;

    if (settings.isMember("set_uniform_brightness")) {
        set_uniform_brightness = settings["set_uniform_brightness"].asBool();
    }
    if (settings.isMember("uniform_brightness")) {
        uniform_brightness = settings["uniform_brightness"].asInt();
    }
    if (settings.isMember("set_color_boost")) {
        set_color_boost = settings["set_color_boost"].asBool();
    }
    if (settings.isMember("color_boost_factor")) {
        color_boost_factor = settings["color_boost_factor"].asDouble();
    }
    if (settings.isMember("component_threshold")) {
        component_threshold = settings["component_threshold"].asInt();
    }
    if (settings.isMember("manhattan_threshold")) {
        manhattan_threshold = settings["manhattan_threshold"].asDouble();
    }
    if (settings.isMember("threshold_value")) {
        threshold_value = settings["threshold_value"].asInt(); 
    }
    #ifdef DEBUG
    std::cerr << "Settings loaded:\n"
              << "  set_uniform_brightness: " << set_uniform_brightness << "\n"
              << "  uniform_brightness: " << uniform_brightness << "\n"
              << "  set_color_boost: " << set_color_boost << "\n"
              << "  color_boost_factor: " << color_boost_factor << "\n"
              << "  component_threshold: " << component_threshold << "\n"
              << "  manhattan_threshold: " << manhattan_threshold << "\n"
              << "  letterbox_threshold_value: " << threshold_value << "\n";
    #endif

}
// Load segment data from a JSON file saved using the Python script.
std::map<int, cv::Rect> loadSegmentData(const std::string& filename) {
    std::map<int, cv::Rect> segmentMap;
    std::ifstream file(filename);
    if (!file.is_open()) {
        #ifdef DEBUG
        std::cerr << "Error: Unable to open " << filename << "\n";
        #endif
        return segmentMap; // Return empty map
    }

    Json::Value root;
    file >> root;

    for (const auto& key : root.getMemberNames()) {
        int segment = std::stoi(key);
        int x = root[key]["x"].asInt();
        int y = root[key]["y"].asInt();
        int width = root[key]["width"].asInt();
        int height = root[key]["height"].asInt();
        segmentMap[segment] = cv::Rect(x, y, width, height);
        #ifdef DEBUG
        std::cerr << "Loaded segment " << segment
                  << " with dimensions (x: " << x << ", y: " << y
                  << ", width: " << width << ", height: " << height << ")\n";
        #endif
    }

    return segmentMap;
}

// Removes black bars from the input image.
cv::Mat cropBlackBars(const cv::Mat& image, int threshold_value = 10, int margin = 20) {
    // Convert image to grayscale.
    cv::Mat gray;
    cv::cvtColor(image, gray, cv::COLOR_BGR2GRAY);
    
    int rows = gray.rows;
    int cols = gray.cols;

    // Compute the sum of intensities for each row and each column.
    cv::Mat rowSum, colSum;
    cv::reduce(gray, rowSum, 1, cv::REDUCE_SUM, CV_32S); // One value per row.
    cv::reduce(gray, colSum, 0, cv::REDUCE_SUM, CV_32S); // One value per column.

    // Determine thresholds for a row/column to be considered "black".
    int rowThreshold = threshold_value * cols;
    int colThreshold = threshold_value * rows;

    // Determine candidate boundaries by scanning from the edges inward—but only until the image center.
    int top = 0;
    while (top < rows/2 && rowSum.at<int>(top, 0) <= rowThreshold) {
        top++;
    }

    int bottom = rows - 1;
    while (bottom > rows/2 && rowSum.at<int>(bottom, 0) <= rowThreshold) {
        bottom--;
    }

    int left = 0;
    while (left < cols/2 && colSum.at<int>(0, left) <= colThreshold) {
        left++;
    }

    int right = cols - 1;
    while (right > cols/2 && colSum.at<int>(0, right) <= colThreshold) {
        right--;
    }

    // Compute how much is cropped on each side.
    int topCrop = top;                     // number of rows cropped from the top
    int bottomCrop = rows - 1 - bottom;      // number of rows cropped from the bottom
    int leftCrop = left;                     // number of columns cropped from the left
    int rightCrop = cols - 1 - right;        // number of columns cropped from the right

    // Decide if there is a vertical letterbox.
    bool cropVertical = false;
    if (topCrop > margin && bottomCrop > margin &&
        std::abs(topCrop - bottomCrop) <= margin) {
        cropVertical = true;
    }

    // Decide if there is a horizontal letterbox.
    bool cropHorizontal = false;
    if (leftCrop > margin && rightCrop > margin &&
        std::abs(leftCrop - rightCrop) <= margin) {
        cropHorizontal = true;
    }

    cv::Mat cropped;

    // Only crop if a symmetric letterbox is detected on one axis.
    // Typically, letterboxing appears as either vertical bars (pillarbox) or horizontal bars.
    if (cropVertical && !cropHorizontal) {
        // Crop vertical letterbox while keeping full width.
        cv::Rect roi(0, top, cols, bottom - top + 1);
        #ifdef DEBUG
        std::cerr << "Detected vertical letterbox: topCrop=" << topCrop 
                  << ", bottomCrop=" << bottomCrop << "\n";
        std::cerr << "Cropping to: x=0, y=" << top 
                  << ", width=" << cols << ", height=" << bottom - top + 1 << "\n";
        #endif
        cropped = image(roi);
    } else if (cropHorizontal && !cropVertical) {
        // Crop horizontal letterbox while keeping full height.
        cv::Rect roi(left, 0, right - left + 1, rows);
        #ifdef DEBUG
        std::cerr << "Detected horizontal letterbox: leftCrop=" << leftCrop 
                  << ", rightCrop=" << rightCrop << "\n";
        std::cerr << "Cropping to: x=" << left << ", y=0, width=" << right - left + 1 
                  << ", height=" << rows << "\n";
        #endif
        cropped = image(roi);
    } else {
        // If no clear symmetric letterbox is detected, return the original image.
        #ifdef DEBUG
        std::cerr << "No symmetric letterbox detected; returning original image.\n";
        #endif
        return image;
    }

    // Resize the cropped image back to the original dimensions.
    // This ensures that any segment coordinates (based on the original image size)
    // will fall within the image boundaries.
    cv::Mat resized;
    cv::resize(cropped, resized, cv::Size(cols, rows));
    return resized;
}

// Apply a proportional boost to the saturation channel of the given color.
cv::Vec3b applyColorBoost(const cv::Vec3b& color, double boostFactor) {
    // Create a 1x1 image with the given color
    cv::Mat bgrPixel(1, 1, CV_8UC3, color);
    cv::Mat hsvPixel;
    cv::cvtColor(bgrPixel, hsvPixel, cv::COLOR_BGR2HSV);

    cv::Vec3b hsv = hsvPixel.at<cv::Vec3b>(0, 0);
    // Boost the saturation channel (hsv[1])
    int boostedS = std::min(255, static_cast<int>(hsv[1] * boostFactor));
    hsv[1] = static_cast<uchar>(boostedS);
    hsvPixel.at<cv::Vec3b>(0, 0) = hsv;

    cv::Mat boostedBGR;
    cv::cvtColor(hsvPixel, boostedBGR, cv::COLOR_HSV2BGR);
    return boostedBGR.at<cv::Vec3b>(0, 0);
}


struct SegmentData {
    int segment;
    cv::Vec3b color;
};

// Precompute scaled segment positions and store them in a map
std::map<int, cv::Rect> precomputeScaledSegments(const std::map<int, cv::Rect>& originalSegments, double scaleFactor) {
    std::map<int, cv::Rect> scaledSegments;
    for (const auto& [segment, rect] : originalSegments) {
        scaledSegments[segment] = cv::Rect(
            static_cast<int>(rect.x * scaleFactor),
            static_cast<int>(rect.y * scaleFactor),
            static_cast<int>(rect.width * scaleFactor),
            static_cast<int>(rect.height * scaleFactor)
        );
    }
    return scaledSegments;
}


class ThreadPool {
public:
    ThreadPool(size_t numThreads) {
        for (size_t i = 0; i < numThreads; ++i) {
            workers.emplace_back([this] {
                while (true) {
                    std::function<void()> task;
                    {
                        std::unique_lock<std::mutex> lock(queueMutex);
                        condition.wait(lock, [this] { return stop || !tasks.empty(); });
                        if (stop && tasks.empty()) return;
                        task = std::move(tasks.front());
                        tasks.pop();
                    }
                    task();
                }
            });
        }
    }

    ~ThreadPool() {
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            stop = true;
        }
        condition.notify_all();
        for (std::thread &worker : workers) {
            worker.join();
        }
    }

    void enqueue(std::function<void()> task) {
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            tasks.push(std::move(task));
        }
        condition.notify_one();
    }

private:
    std::vector<std::thread> workers;
    std::queue<std::function<void()>> tasks;
    std::mutex queueMutex;
    std::condition_variable condition;
    bool stop = false;
};

// Main function to process the screen capture and compute the dominant color for each segment.
int main() {
    #ifdef DEBUG
    std::cerr << "Starting the C++ process with motion and edge detection...\n";
    #endif
    cv::setUseOptimized(true);
    cv::setNumThreads(std::thread::hardware_concurrency());
    loadSettings();
    const std::string colorFile = "prev_colors.txt";

    loadPrevColors(colorFile);

    cv::Mat image = captureScreen();
    if (image.empty()) {
        #ifdef DEBUG
        std::cerr << "Error: Screen capture failed.\n";
        #endif
        return 1;
    }

    // Use letterbox detection only if enabled
    cv::Mat croppedImage;
    if (enable_letterbox_detection) {
        croppedImage = cropBlackBars(image, threshold_value);
    } else {
        croppedImage = image;
    }

    cv::Mat scaledImage;
    double scaleFactor = 1.0;
    cv::resize(croppedImage, scaledImage, cv::Size(), scaleFactor, scaleFactor, cv::INTER_AREA);

    const std::string segmentFile = "segments.json";
    auto segmentData = loadSegmentData(segmentFile);

    // Precompute scaled segment positions
    auto scaledSegments = precomputeScaledSegments(segmentData, scaleFactor);

    std::vector<SegmentData> segmentResults;  // Collect results
    ThreadPool pool(std::thread::hardware_concurrency());
    std::mutex resultsMutex;

    for (const auto& [segment, scaledRect] : scaledSegments) {
        pool.enqueue([&, segment, scaledRect]() {
            if (scaledRect.x + scaledRect.width > scaledImage.cols || 
                scaledRect.y + scaledRect.height > scaledImage.rows) {
                std::cerr << "Warning: Segment " << segment << " exceeds scaled image bounds. Skipping." << std::endl;
                return;
            }

            cv::Mat segment_image = scaledImage.rowRange(scaledRect.y, scaledRect.y + scaledRect.height)
                                                .colRange(scaledRect.x, scaledRect.x + scaledRect.width);
            if (segment_image.empty()) {
                std::cerr << "Error: Segment image capture failed for segment " << segment << std::endl;
                return;
            }

            // Compute motion intensity if there's a previous frame.
            double motionIntensity = 0.0;
            if (!prevFrame.empty() &&
                scaledRect.x + scaledRect.width <= prevFrame.cols &&
                scaledRect.y + scaledRect.height <= prevFrame.rows) {
                cv::Mat prevSegment = prevFrame.rowRange(scaledRect.y, scaledRect.y + scaledRect.height)
                                                   .colRange(scaledRect.x, scaledRect.x + scaledRect.width);
                motionIntensity = computeMotionIntensity(segment_image, prevSegment);
            }

            // Compute edge intensity from the current segment.
            double edgeIntensity = computeEdgeIntensity(segment_image);

            cv::Vec3b dominantColor = computeDominantColor(segment_image);

            // Apply uniform brightness and color boost as before, if enabled.
            if (set_uniform_brightness) {
                dominantColor = applyProportionalBrightness(dominantColor, uniform_brightness);
            }
            if (set_color_boost) {
                dominantColor = applyColorBoost(dominantColor, color_boost_factor);
            }

            // Adjust the dominant color based on motion and edge detection.
            dominantColor = adjustColorWithMotionAndEdges(dominantColor, motionIntensity, edgeIntensity);

            {
                std::lock_guard<std::mutex> lock(resultsMutex);
                if (is_significant_change(segment, dominantColor)) {
                    segmentResults.push_back({segment, dominantColor});
                    prev_colors[segment] = std::make_tuple(dominantColor[2], dominantColor[1], dominantColor[0]);
                }
            }
        });
    }

    // Wait for all threads to finish (explicit destructor call)
    pool.~ThreadPool();

    // Update the previous frame for the next call
    prevFrame = scaledImage.clone();

    rapidjson::Document output;
    output.SetObject();
    rapidjson::Document::AllocatorType& allocator = output.GetAllocator();

    rapidjson::Value commands(rapidjson::kObjectType);
    rapidjson::Value allSegments(rapidjson::kArrayType);

    for (const auto& data : segmentResults) {
        std::string command = buildCommand(data.segment, data.color);
        commands.AddMember(
            rapidjson::Value(("61_" + std::to_string(data.segment)).c_str(), allocator).Move(),
            rapidjson::Value(command.c_str(), allocator).Move(), 
            allocator
        );

        rapidjson::Value segmentJson(rapidjson::kObjectType);
        segmentJson.AddMember("segment", data.segment, allocator);
        
        rapidjson::Value colorArray(rapidjson::kArrayType);
        colorArray.PushBack(data.color[2], allocator);
        colorArray.PushBack(data.color[1], allocator);
        colorArray.PushBack(data.color[0], allocator);
        segmentJson.AddMember("dominantColor", colorArray, allocator);

        allSegments.PushBack(segmentJson, allocator);
    }

    // Add the "commands" member
    if (commands.ObjectEmpty()) {
        output.AddMember("commands", rapidjson::Value(rapidjson::kObjectType), allocator);
    } else {
        output.AddMember("commands", commands, allocator);
    }

    // Add the "segments" member
    if (allSegments.Empty()) {
        output.AddMember("segments", rapidjson::Value(rapidjson::kArrayType), allocator);
    } else {
        output.AddMember("segments", allSegments, allocator);
    }


    rapidjson::StringBuffer buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(buffer);
    output.Accept(writer);

    std::cout << buffer.GetString() << std::endl;
    #ifdef DEBUG
    std::cerr << "C++ process completed successfully.\n";
    #endif
    savePrevColors(colorFile);

    return 0;
}


// Capture the screen using the Windows GDI API.
cv::Mat captureScreen() {
    if (!g_initialized) {
        initScreenCapture();
        if (!g_initialized) return cv::Mat();
    }

    SelectObject(g_hwindowCompatibleDC, g_hbwindow);

    // Capture only the selected monitor's area
    if (!BitBlt(g_hwindowCompatibleDC, 0, 0, g_screenWidth, g_screenHeight, 
                g_hwindowDC, g_monitorX, g_monitorY, SRCCOPY)) {
        return cv::Mat();
    }

    BITMAPINFOHEADER bi;
    memset(&bi, 0, sizeof(BITMAPINFOHEADER));
    bi.biSize = sizeof(BITMAPINFOHEADER);
    bi.biWidth = g_screenWidth;
    bi.biHeight = -g_screenHeight; // Top-down bitmap
    bi.biPlanes = 1;
    bi.biBitCount = 32;
    bi.biCompression = BI_RGB;

    cv::Mat bgraImage(g_screenHeight, g_screenWidth, CV_8UC4);
    if (!GetDIBits(g_hwindowCompatibleDC, g_hbwindow, 0, g_screenHeight, bgraImage.data,
                   (BITMAPINFO*)&bi, DIB_RGB_COLORS)) {
        return cv::Mat();
    }

    cv::Mat bgrImage;
    cv::cvtColor(bgraImage, bgrImage, cv::COLOR_BGRA2RGB);
    return bgrImage;
}

// Compute the dominant color in the given region of interest (ROI).

cv::Vec3b computeDominantColor(const cv::Mat& roi) {
    if (roi.empty()) {
        #ifdef DEBUG
        std::cerr << "Error: ROI is empty." << std::endl;
        #endif
        return cv::Vec3b(0, 0, 0); // Return default color
    }

    // Convert image to HSV
    cv::Mat hsv;
    cv::cvtColor(roi, hsv, cv::COLOR_BGR2HSV);

    // Extract the Hue channel
    std::vector<cv::Mat> hsvChannels;
    cv::split(hsv, hsvChannels);  // Split into H, S, V
    cv::Mat hueChannel = hsvChannels[0];  // Only use Hue

    // Compute histogram for the Hue channel
    int histSize = 180; // Hue values range from 0 to 179
    float range[] = {0, 180};
    const float* histRange = {range};
    cv::Mat hist;
    cv::calcHist(&hueChannel, 1, 0, cv::Mat(), hist, 1, &histSize, &histRange, true, false);

    // Find the most frequent Hue value
    double maxVal = 0;
    cv::Point maxIdx;
    cv::minMaxLoc(hist, 0, &maxVal, 0, &maxIdx);

    // Create a mask for pixels with the dominant Hue
    cv::Mat mask;
    cv::inRange(hsvChannels[0], maxIdx.y, maxIdx.y + 1, mask);

    // Compute the mean color in the masked region
    cv::Scalar meanColor = cv::mean(roi, mask);
    return cv::Vec3b(meanColor[0], meanColor[1], meanColor[2]);
}



// Convert a vector of bytes to a Base64 string required for device commands.
std::string convertToBase64(const std::vector<uint8_t>& data) {
    static const char* base64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string result;
    int val = 0;
    int valb = -6;
    for (uint8_t c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            result.push_back(base64_chars[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) result.push_back(base64_chars[((val << 8) >> (valb + 8)) & 0x3F]);
    while (result.size() % 4) result.push_back('=');
    return result;
}

// Build the command payload for a given segment and color.
std::string buildCommand(int segment, const cv::Vec3b& color) {
    #ifdef DEBUG
    std::cerr << "Building command for segment: " << segment << std::endl;    // Un-comment for debugging
    #endif
    // Convert BGR to RGB
    cv::Vec3b rgbColor = cv::Vec3b(color[2], color[1], color[0]);

    // Convert color components to integers
    int b = static_cast<int>(color[0]);
    int g = static_cast<int>(color[1]);
    int r = static_cast<int>(color[2]);

    int rr = static_cast<int>(rgbColor[0]);
    int gg = static_cast<int>(rgbColor[1]);
    int bb = static_cast<int>(rgbColor[2]);

    // Debug: Output BGR and RGB colors in decimal format
    #ifdef DEBUG
    std::cerr << "BGR Color: [" << b << ", " << g << ", " << r << "]\n";
    std::cerr << "RGB Color: [" << rr << ", " << gg << ", " << bb << "]\n";
    #endif
    // Convert color to HSV
    cv::Mat rgb(1, 1, CV_8UC3, cv::Scalar(bb, gg, rr));
    cv::Mat hsv;
    cv::cvtColor(rgb, hsv, cv::COLOR_RGB2HSV);
    cv::Vec3b hsvColor = hsv.at<cv::Vec3b>(0, 0);

    // Convert HSV components to integers
    int hue = static_cast<int>(hsvColor[0]);
    int sat = static_cast<int>(hsvColor[1]);
    int val = static_cast<int>(hsvColor[2]);

    // Debug: Output HSV color
    #ifdef DEBUG
    std::cerr << "HSV Color (raw): [" << hue << ", " << sat << ", " << val << "]\n";
    #endif
    // Convert HSV values to the appropriate range
    hue = static_cast<int>(hue * 2); // Convert hue to 0-360 range
    sat = static_cast<int>(sat / 255.0 * 1000); // Convert saturation to 0-1000 range
    val = static_cast<int>(val / 255.0 * 1000); // Convert value to 0-1000 range

    // Ensure values are within the expected range for the device
    hue = std::min<int>(std::max<int>(hue, 0), 360);
    sat = std::min<int>(std::max<int>(sat, 0), 1000);
    val = std::min<int>(std::max<int>(val, 0), 1000);


    // Debug: Output HSV values after range conversion 
    #ifdef DEBUG
    std::cerr << "HSV Color (converted): [" << hue << ", " << sat << ", " << val << "]\n";
    #endif
    // Exclude near black colors from high brightness
    const int nearBlackThreshold = 50;  // Adjust as needed (0-255 scale for RGB)
    if ((r < nearBlackThreshold && g < nearBlackThreshold && b < nearBlackThreshold) ||
        val < static_cast<int>(nearBlackThreshold * 1000.0 / 255)) {
        val = (val < 100) ? val : 100;  // Cap brightness to a low value for near black
    } else if (set_uniform_brightness) {
        val = uniform_brightness;  // Apply uniform brightness for non-black colors
    }



    // Construct HSV Hex value
    std::stringstream ss;
    ss << std::hex << std::setw(4) << std::setfill('0') << hue
       << std::setw(4) << std::setfill('0') << sat
       << std::setw(4) << std::setfill('0') << val;
    std::string hsvHex = ss.str();
    #ifdef DEBUG
    std::cerr << "HSV Hex: " << hsvHex << std::endl;  // Un-comment for debugging
    #endif
    // Original payloads for individual segments (20-1, top-down)
    std::vector<std::vector<uint8_t>> original_payloads = {
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x14},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x13},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x12},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x11},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x10},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x0f},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x0e},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x0d},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x0c},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x0b},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x0a},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x09},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x08},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x07},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x06},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x05},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x04},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x03},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x02},
        {0x00, 0x02, 0x00, 0x14, 0x01, 0x00, 0x00, 0x03, 0xe8, 0x03, 0xe8, 0x81, 0x01},
    };

    std::vector<uint8_t> byte_array = original_payloads[segment - 1];
    std::vector<uint8_t> hsv_bytes;

    // Convert HSV Hex to byte array
    for (size_t i = 0; i < hsvHex.length(); i += 2) {
        std::string byteString = hsvHex.substr(i, 2);
        uint8_t byte = static_cast<uint8_t>(strtol(byteString.c_str(), nullptr, 16));
        hsv_bytes.push_back(byte);
    }

    // Insert HSV values into the payload at the correct position
    for (size_t i = 0; i < hsv_bytes.size(); ++i) {
        byte_array[5 + i] = hsv_bytes[i];
    }

    std::string encoded_data = convertToBase64(byte_array);

    // Debug information  
    #ifdef DEBUG
    std::cerr << "Segment " << segment << ":\n";
    std::cerr << "  BGR Color: [" << b << ", " << g << ", " << r << "]\n";
    std::cerr << "  RGB Color: [" << rr << ", " << gg << ", " << bb << "]\n";
    std::cerr << "  HSV Color (converted): [" << hue << ", " << sat << ", " << val << "]\n";
    std::cerr << "  HSV Hex: " << hsvHex << "\n";
    std::cerr << "  Byte Array: ";
    #endif
    for (uint8_t byte : byte_array) {
        #ifdef DEBUG
        std::cerr << std::hex << std::setw(2) << std::setfill('0') << (int)byte << " ";
        #endif
    }
    #ifdef DEBUG
    std::cerr << "\n  Encoded Data: " << encoded_data << "\n";
    #endif
    return encoded_data;
}
