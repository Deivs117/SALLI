# **SALLI: ESP-IDF Embedded Firmware**

This directory contains the optimized, low-level C firmware developed specifically for the **ESP32-C3 Mini** microcontroller utilizing Espressif's native **ESP-IDF (IoT Development Framework)**.

To ensure optimal execution times, task scheduling, and real-time networking, the firmware is written without the bulky overhead of the Arduino framework, leaning heavily on native **FreeRTOS** APIs.

## **💾 Firmware Subsystems**

The firmware is split into two specialized codebase architectures depending on the micro-controller's deployment location:

### **1\. Acces Point Sally (Master Controller)**

This node acts as the primary computational gateway of the robot. Located in the Head Module, it manages top-level control.

* **Network Role:** Configures the ESP32-C3 chip as a local **Wi-Fi Access Point (AP)**.  
* **Computational Load:** Houses the central state machines, parses incoming target vectors from the Python base station, and coordinates the gait angles.  
* **Joint Routing:** Drives local head/neck servos and packages raw target angles for downstream modules.

### **2\. WIFI\_Movement (Actuator Node)**

This lightweight node is flashed onto the secondary ESP32-C3 processors integrated into deep segments (like the legs or rear spine segments).

* **Network Role:** Configures the module to run in **Wi-Fi Station (STA) Mode**, connecting to the Acces Point Sally local network.  
* **Low-Latency UDP Socket:** Opens a non-blocking listening socket. It consumes serialized target vectors sent from the master node.  
* **Hardware Interfacing:** Decodes incoming angle arrays into accurate duty cycles for high-resolution PWM outputs via the ESP32 **LEDC (LED Controller)** peripheral.

## **🔄 Dynamic State Machine**

The master controller manages transitions using a lightweight Real-Time Operating System (RTOS) task schedule:

       \+-----------------------+  
       |       BOOT / INIT     |  
       \+-----------------------+  
                   |  
                   v  
       \+-----------------------+  
       |   WAITING\_FOR\_CONN    |\<-----------+  
       \+-----------------------+            | (Client  
                   |                        | Disconnected)  
                   | (Client Connected)     |  
                   v                        |  
       \+-----------------------+            |  
       |     ACTIVE\_STREAM     |------------+  
       \+-----------------------+  
         /         |         \\  
        v          v          v  
   \[CALIBRATE\]  \[TELEOP\]  \[AUTONOMOUS\]

## **🔌 Communication Protocol Technical Specifications**

To sustain a control cycle rate of at least ![][image1] without data congestion, the firmware uses low-overhead UDP structures instead of TCP.

### **Data Packet Structure (UDP Payload)**

The typical message contains a small header followed by float values mapping directly to servo positions:

\+----------------------+--------------------+---------------------+  
| uint16\_t Packet ID   | uint8\_t State ID   | float32\_t Angles\[\]  |  
| 2 Bytes              | 1 Byte             | N \* 4 Bytes         |  
\+----------------------+--------------------+---------------------+

## **🔨 Compiling and Flashing with ESP-IDF**

### **Prerequisites**

1. Install ESP-IDF (Version 5.1 or later is highly recommended).  
2. Set up your environment variables (e.g., source the setup script: export.sh or setup.bat).

### **Build & Flash Steps**

Navigate to either the Acces Point Sally or WIFI\_Movement directory, then execute:

\# Set target chip to ESP32-C3  
idf.py set-target esp32c3

\# Open configuration menu (useful for changing Wi-Fi SSID/Password)  
idf.py menuconfig

\# Build project binaries  
idf.py build

\# Flash binaries and open the serial monitor to view real-time logs  
idf.py \-p \[PORT\] flash monitor

*(Replace \[PORT\] with your specific COM port, such as COM3 on Windows or /dev/ttyUSB0 on Linux).*

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAZCAYAAABzVH1EAAACgUlEQVR4Xu1WPUhbURSO1EKLYmkxBEOS+xKylHYoBIQWdHLQQTvo4N5FaNe2dOzQoUuhjmIpHTpZunUpGUod3QQRBAdFO+iQKYOKtt+Xd088ObkhCYhL3weHd893/u7JPfflpVIJEiToikwmM5TL5e4Z+kY+n88argHwD4vF4rjlQygUCvtWoihaog3PTWujcD82T09A8Kxz7i/kA9YLeD6D1CBV6wvuO+QI8gcb+Q2JrI8G/FYgn3x+CtcztCH0o7eLbY06+Fs2T09QjYiclsvlEeM2CH4V8kIIFJyGfoHTvK0dQ5DclifA12lLp9PD1tYXfCOHPA3Ig0qlctP6cJxcfEr3hctms6PQtxAzpX1DuM5G9iyvAfu3QDGeEvlqt7m+9kbwHAvNKPj1UDH4fmEs4zRv0W8j0GdcfH/aBC+aSR3fhNwRjhZ1rJ9AanpkXLzZTo3U4VvRvAVju4lpZBlSE51vSeqo8zk0+g34Ruqa88m3lX4ljfh72CLgz2xu5uWmVXyVPmjICdcTEHTAQJn9q2rE8gTjbW7oL5H7kV/P044ary6jAoDTqS0iG3d+9vH8YYulLi/7BorcVXwbfK6eGxGgmZ+04RlRR53XWL43bjFUkUHFNU5ENoj1O+/XvNQsDP0X5CvUAeFDUDXa4Do3MuDjzoVgLTajnZqAcQ//ExOGY4Jj0WXT8JtTPo8hJ5jbjHCd0G8jvAvY8A74aqlUuqN8T3inRW8BjuoNHHZFd/Fb6xwyr/3YLJMrP17A5q8VAi8z8i9KI37d+FPF+qm/7BfetkQ9FY+sfLrwNTzGxoDnwpkyrUCit3Ba7tgxwE8XX2Ql8BmTIEGCBAn+L/wD5z4Q56/hM44AAAAASUVORK5CYII=>