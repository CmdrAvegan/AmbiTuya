#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <sstream>
#include <iostream>
#include "time.cpp"  // Include existing C++ code

namespace py = pybind11;

// Function to capture the C++ output and return it as a Python string
std::string process_screen() {
    std::ostringstream buffer;
    std::streambuf* oldCoutStreamBuf = std::cout.rdbuf();
    std::cout.rdbuf(buffer.rdbuf());  // Redirect std::cout to buffer

    int result = main();  // Call the original main function

    std::cout.rdbuf(oldCoutStreamBuf);  // Restore the original std::cout

    if (result != 0) {
        throw std::runtime_error("C++ process encountered an error.");
    }

    return buffer.str();
}

PYBIND11_MODULE(time_bindings, m) {
    m.def("process_screen", &process_screen, "Process screen and return JSON output");
    m.def("set_letterbox_detection", &set_letterbox_detection, "Set letterbox detection flag");
    m.def("initScreenCapture", &initScreenCapture, "Initialize screen capture resources");
    m.def("switchMonitorCapture", &switchMonitorCapture, "Switch screen capture to the newly selected monitor");
}


