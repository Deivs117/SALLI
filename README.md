# **SALLI: Salamander Autonomous Locomotion on Land Infrastructure**

SALLI is an open-source, low-cost, and modular mechatronic platform designed to study bio-inspired terrestrial locomotion. Drawing inspiration from the sprawling gait of the salamander, this project integrates custom 3D-printed mechanical linkages, dedicated modular printed circuit boards (PCBs), lightweight embedded ESP-IDF firmware, and high-level Python control algorithms.

## **👁️ Project Vision & Philosophy**

Traditional robotics platforms often suffer from high manufacturing costs, complex monolithic assemblies, and poor reparability. SALLI was conceived under a different paradigm:

* **True Modularity:** Every physical segment—whether a spinal oscillator, a locomotor leg, or a sensory head—uses a standardized mechanical and electrical connection interface. Segments can be chain-linked dynamically to increase or decrease the robot's degrees of freedom (DoF).  
* **Low Cost & Accessibility:** Designed to be accessible to students, researchers, and hobbyists. The structural parts are optimized for standard FDM 3D printing, and the electronics rely on budget-friendly, high-performance ESP32-C3 microcontrollers and standard micro servos.  
* **Easy Maintenance & Repair:** Field repairs can be executed swiftly. Damage to a single segment does not compromise the whole robot; the offending module can be disconnected and swapped out in minutes.

## **🏗️ System Architecture**

The project is structurally divided into four cohesive domains:

graph TD  
    A\[Control Codes \- Python PC\] \<--\>|UDP over Wi-Fi| B\[Firmware \- ESP-IDF Master AP\]  
    B \<--\>|UDP Multicast / Serial Bus| C\[Firmware \- ESP-IDF Slave Node\]  
    B \--\>|PWM Signals| D\[Custom PCBs / Power Rails\]  
    C \--\>|PWM Signals| D  
    D \--\>|Actuation| E\[CAD 3D \- Physical Modules\]

1. **CAD\_3D/ (Mechanical Architecture):** Multi-segment structure utilizing bio-mimetic joint limits and sprawling kinematics.  
2. **PCBs/ (Electrical Architecture):** Modular bus system delivering isolated power lines (to prevent servo-induced voltage brownouts) and standardized signal traces.  
3. **Firmware/ (Embedded Systems):** High-efficiency ESP-IDF C-code implementing an Access Point control loop and UDP-based communication over ESP32-C3 chips.  
4. **ControlCodes/ (High-Level Control & Autonomy):** Python orchestrator supporting manual teleoperation, automatic parameter identification, and servo calibration.

## **📂 Repository Directory Tree**

SALLI/  
├── .gitignore                   \# Global file and directory exclusions  
├── README.md                    \# Root-level project documentation (This file)  
│  
├── CAD\_3D/                      \# Mechanical assemblies and components  
│   ├── Cabeza V3/               \# Sensory head module  
│   ├── Cola/                    \# Stabilizing tail segment  
│   ├── Ensamble Total/          \# Master digital design assembly  
│   ├── Módulo de Patas V3/      \# Sprawling leg kinematics module  
│   ├── Oscilatorio V4/          \# Daisy-chainable spinal segments  
│   └── Patines/                 \# Passive ground contact slide-pads  
│  
├── ControlCodes/                \# High-level Python control ecosystem  
│   ├── Calibration.py           \# Multi-servo offset calibration utility  
│   ├── SALLI.py                 \# Core autonomy and CPG state engine  
│   └── Teleoperation.py         \# Human-in-the-loop manual controller  
│  
├── Firmware/                    \# Low-level ESP-IDF software  
│   ├── Acces Point Sally/       \# Master AP, computational control, and state processor  
│   └── WIFI\_Movement/           \# Slave node receiver executing raw joint positions  
│  
└── PCBs/                        \# Electrical schematic and board layouts  
    ├── Camera/                  \# Visual feedback capture module  
    ├── HeadModule/              \# Central micro-controller carrier PCB  
    ├── Legs\_Module/             \# High-current servo driver PCB  
    └── Oscilatory/              \# Passive signal-passthrough spine PCB

## **🧬 Biological Locomotion Model**

SALLI's movement is mathematically governed by a **Central Pattern Generator (CPG)** model. This system represents networks of coupled neural oscillators that generate rhythmic patterns without sensory feedback.

The phase relation between the body segments (![][image1]) and limbs (![][image2]) is modeled using coupled differential equations:

![][image3]Where:

* ![][image4] represents the instantaneous phase of the ![][image1]\-th oscillator.  
* ![][image5] is the intrinsic frequency of the segment.  
* ![][image6] dictates the coupling strength between neighboring segments.  
* ![][image7] is the target phase bias defining traveling waves for swimming or crawling.

This math is processed in real-time between the ControlCodes layer and the Firmware layer to ensure fluid, life-like movements.

## **🛠️ Quick Start**

### **1\. Requirements & Tools**

* **CAD:** Autodesk Fusion 360, SolidWorks, or FreeCAD to view STEP/STL files.  
* **Firmware development:** Espressif ESP-IDF SDK (v5.1 or later recommended).  
* **Control Station:** Python 3.10+ with standard networking libraries.

### **2\. Basic Setup**

To clone the repository and initialize the project:

git clone \[https://github.com/YourUsername/SALLI.git\](https://github.com/YourUsername/SALLI.git)  
cd SALLI

*(Please refer to the READMEs in each subfolder for detailed configuration instructions.)*

## **🎓 Academic Context**

This project was developed at **Universidad Autónoma de Occidente (UAO)**, Cali, Colombia, within the Faculty of Engineering. It serves as an open-source platform to advance research in bio-inspired robotics, kinetic efficiency, and distributed embedded networks.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAqCAYAAAB/YEE7AAAA6UlEQVR4XmNYcfzXf1yYAV1gpEjO3/P6/7Kj3zEllx35/l9eXv5/YEw+puTSI9/+O3qG/Z+y7iamJDomLDlz66P/fpHZ/w1Nbf4vPvgJVdLC1v1/SnHv//i8tv8ZlVMQkpPWXP8/a+vj/8uP/fwfmVb9Pyq9FiFZP2UHWGLOjmf/TS0d/zfPOoDpoMYZe/4rKCj8n7vrJaokyFgDY6v/ikrKmK6t7F0HDhlbZz9wQLTPO4qQ1De2BOvqmH/sf3Jxz//ojDqEpJm1M1jB7O1P/9u7Bf2fvvk+qoNAru1ceALTTlx4VHIESQIAynC9tG3oirUAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAmCAYAAAD9XArwAAAA70lEQVR4XmNYcfzXf2IwA7oALjyqEAUvOfSZsMKO+cf+q6hp/J+4+ip+hbWTtv43sXT8v/TIN/wKsWHyFE7dcOd/cFzR/9DE0v8ztz7CrhDk8O7FZ8BsCzv3//Ly8pgKp6y7+d/ayRcuCFKkZ2iGqRAdgxS6B8TjVwhyG0hh4/Td+BU2zzrwX0ff5P+0jXdxKwRFG8jKxPwOFEUYCmdtffzfwNjqf92U7fgVZlROAbtv0f4P+BX6hKVhhB9coYKCwv+QhBJwAgApCk0qw1AEVphVPf2/qprmf3v34P/Ljn7HUABXiC6AC48qxIuHlUIActjcMUa4bAgAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAlCAYAAABLRGl/AAABlUlEQVR4XmNYcfzXf0owA7oAqXjUgEFpQGx2838FBcX/ZtYu/1XUNDA0oGMUA0KTyv6Xd62G8xPzO/4XNi/C0ITVgOXHfv6Xl5f/v/jgJ7hkRuWU/0GxBRiaMAxYduT7f7/I7P+2zn4okiDNjh6h/xft/4ChEcWAzoUn/yspq4BthEks3Pf+v717MHEGmFk7g50/f89ruETH/GP/FZWUweGArgnDAJBmEAYFIgxr6RiAxSatuY6iYemRb6gGwAJPTUMLRUJH3wQsjuz8uinb/0el16IaMGfHM7BC/6gcuCDMUD1DMxTF2DDD7O1PwYrTyifCBadtvAcWSyrswtCAjhmWHPoMVlwzcQtYAOQiU0vH/9UTNsMVTd98///cXS//+0Vk/V904COqASDCyNzuvwMwypYd/Q5MxgrA5NyEoqh/xaX/jTP2gJM4hgtAROucg+BQ19DS+1/Ztx4cBugKQQkN5DJ0cYzMhAuDEhoowYUlV5BngLWjz/95u16Bo5IsA+bveQPG6OJEG4ALjxowasCoARAMAL5vesCWy1M/AAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAmCAYAAADN0BvRAAABNUlEQVR4XmNYcfzXf0owA7oAqXjUgFEDhpMBycU9/0OTyv6bWDr+X7jvHYqCmVsf/Xfxifq/7Mh3DM1wA0B42sa7/+Xl5TEUmAINxSaOYUBifsd/M2tnFMlF+z+ANUdn1IH5IFcoKChgGgBS6OgR+j84rghFsqBp4X9jc/v/0zffhxvgHZqKaUDdlO1gm3qXnoNLgDQqKCj+X37sJ4oGdAw2ICq9FmzA/D2vwYKggANpLulYAVdY2bceHMgL9r7FNEBTWx9swKIDH/8rq6j+9w5BdSZI05wdz/43ztjzv7J3HaYBIM2KSsr/VdU0/3ctPo3h7MUHP/1fdvT7/8i06v+ztj7GNIAYDLIZ5C10caINcPWL+W/r7IfdC8RgUEq1cvT+3zBtF3kG4MKjBowaMGoAlQwAAPgG0WaVwjKTAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABsAAAAnCAYAAAD+bDODAAACK0lEQVR4XmNYcfzXf3phBnQBWuJRy6iCRy2jCh61jCp4mFu2cN+7/3G5Lf/dA+JRJJcd/f6/dc6h/8uP/QTjgqYF/yt61mIYQiwGW+biE/U/NKnsv5au4f+ZWx/BJRtn7PlvaGrzf86OZ/8nrbn+X1Nb/7+ZtfP/ubteYhhEDGaYtvHe/96l58AcBQUFsKEg9sJ97//buwf/T8zvgCueuv42hmWL9n/AMBSElxz6jCHG0Dh9N1gDKJjk5eXhimA+aZ51AK542ZHv/33C0sA0iN+3/MJ/DS1dDIPn7Xr138LWHRwiKJbBGJW96/7r6JvAJaLSa1EsB+H5e17/75h/DMUAUjDYMpCvguOKwK6GSTh6hIItQ1YMCm5y4wuEwZbN3v70v76x5f/6KTvgEipqGmAM4y/Y+xackGB8UIJKKe4FJyCY2PTN9/97BiX971lyFhy8WC0D4eTinv8OwAQBYoMSgoaWHthnoOQPEjM2twfHEUw9yIcgAzMqp8DFuhafBscnKAqQowTDssUHP4EN1zM0+6+iqv5/xpaHYMtBloKyBMi16JpBlk1YdQVDHBQFzt6RGOJklyCgPAhKVKDgRY9HUBaqm7IdQw/ZloGCb9rGu/+r+jdiyIGCECSHLk62ZSAMyk+glIwsBsqfyAUBMqbIMhgGJaLqCZvBFpd3r0EpCJAxVSwDlaegEsPA2Op/ZtU0DHkYpoplxOJRy6iCRy2jCh61jCp4+FoGADJCkSGU0J0nAAAAAElFTkSuQmCC>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAmCAYAAAAxxTAbAAACPElEQVR4XmNYcfzXf1pjBnQBWuBRS0jCo5aQhPFa0jzrwP/5e15jiJOK8VqSUTnl//JjPzHEScU4LZm19fF/S3sPDHFyME5LQEFFc0vcA+L/FzYvwhAnB2NY0rX49P+ojLr/CgqK/43MbP9PWXeT4niBW7Jg79v/8vLy/xcf/ATmB8cVgQ2vnrAZbCFIHl0zsRhsSTTQ5SALlh75BhacufXR/96l5+CKQKnMPyoH7qPwlAqgxQoYhhW3LQWbgy4OtkRFTeO/krIKXBAU6XN3vYTz08on/nf0CP2/aP8HMD8mq/G/d2gqhmGVfev/W9i5Y4iDLQHZHpJQAhZYduT7f5+wNLgCUFI2MLaiKBEwgIIAZAkoSGCGIifd8q7VYPk5O56D+SDXBsUWoMTRsqPf/1f0rPvv4BHyv3/lZUxLQISWjsF/U0tHsADIMlCkg9iztz8FR3pJxwowH2TwnB3PwGKVvevghoBSIyg+7d2D/zt7R2K3BJaCQBEOCqry7jXgSFTX0P7fNvcIXDEo5YFcDQo+kI9h4jC2prb+/8T8DuyWwDAoYq0dff5PXnsTQyEMg3zQOGMPhjgI6+ib/J+28S6GOEZmhOUPdHEYdvWLAQcbcnCBMMiByCkQGaNYAvI2cv7AhkOTysAWNUzbhSJeM3HL/8bpuzHUgzCKJbn1c/D6Ah2D4hCUh0B1DiiYlxz6jKEGhDGCixQMylug5J1ZOfW/hpYehjwMU2QJsXjUEpLwqCUk4VFLSMLDxxIA2EssQAxFb6cAAAAASUVORK5CYII=>