# **SALLI: Custom Electronic PCBs**

This directory contains the electrical designs for SALLI's custom printed circuit boards. The electronic system is engineered to solve a common pitfall in amateur robotics: messy, unreliable wiring harnesses that introduce high resistance, noise, and power failures.

## **🔌 Electrical Architecture Overview**

SALLI uses a decentralized, modular electrical bus system. Power is distributed along the spine via a ruggedized internal backbone, preventing major voltage drops from affecting the master microcontroller.

                 \+---------------------------------+  
                 |       Main Battery Pack         |  
                 |      (e.g., 2S LiPo / 7.4V)     |  
                 \+---------------------------------+  
                        |                   |  
                        v                   v  
             \+-----------------+     \+-----------------+  
             | Servo Regulators|     | Logic Regulators|  
             |   (5V \- 6V)     |     |     (3.3V)      |  
             \+-----------------+     \+-----------------+  
                        |                   |  
                        v                   v  
              \=====================================  
                  SALLI Power & Communication Bus  
              \=====================================  
                 |               |               |  
                 v               v               v  
           \[HeadModule\]     \[Oscilatory\]   \[Legs\_Module\]

## **🛠️ Board Subsystems & Responsibilities**

The electrical system is divided into four main board profiles:

### **1\. HeadModule (Master Processing PCB)**

The central board of the robot, acting as SALLI's head controller.

* **MCU Support:** Integrates the footprint for the **ESP32-C3 Mini** board.  
* **Power Filtering:** Features heavy ceramic and electrolytic capacitor banks to filter out high-frequency noise induced by servo inductive kickbacks.  
* **Sensor Hub:** Routes dedicated pins for IMUs (Inertial Measurement Units for tilt and balance detection) and external range sensors.

### **2\. Oscilatory (Spine Segment PCB)**

These are passive/semi-active distribution boards designed to be chain-linked together.

* **The SALLI Bus:** Passes power (VCC and GND) and communication channels downstream to consecutive modules.  
* **Servo Tap:** Provides local, filtered power connectors for the local spinal deflection servo, keeping cabling lengths under ![][image1].

### **3\. Legs\_Module (High-Current Driver Board)**

Because the limbs support the entire weight of the robot and drive forward crawling forces, they demand significant active currents.

* **High-Current Traces:** Features wide copper traces capable of handling sustained currents of up to ![][image2] during crawling cycles.  
* **Independent Power Regulation:** Standardizes opto-couplers or isolation resistors to prevent sudden physical motor stalls from corrupting the main microcontroller's logical operations.

### **4\. Camera (Vision Expansion Board)**

An optional expansion PCB tailored to hold camera modules (such as ESP32-CAM or specialized small SPI cameras) to enable visual-spatial telemetry.

## **📐 Electrical Design Guidelines**

* **Trace Width Selection:** \* Power paths (![][image3], ![][image4]) are set to a minimum of 1.5 mm width to minimize resistance and prevent thermal stress under heavy load.  
  * Logic lines (![][image5], ![][image6], ![][image7]) are kept at standard 0.254 mm traces.  
* **Decoupling Strategy:** Each module places a 100uF electrolytic capacitor directly in parallel with the local servo power terminal, supplemented by a standard 0.1uF ceramic capacitor close to the logic rails to handle high-frequency voltage ripples.  
* **Standardized Pin Headers:** Connectors use standard, highly accessible, polarized headers (like JST-XH or XT30/XT60 for power entry) to ensure mistake-proof assembly by students.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADwAAAAZCAYAAABtnU33AAAChUlEQVR4Xu2WO2hUURCGrxgL8f1Yl+zr7guWgFaLioUSxMLgq9gtVOzsRBuLWGmXKq1aLDYWYiNiI4ikEG0CNiKKELDQwsZCECKskl2/uTuzObncaEyaGzk//Nwz/5k558x5zG4QeHh4/DfI5/N7yuXyONwZ73ORyWS2ViqVQ3F9XaFYLB4Mw7Dv8Djyhrgf+mPYg1/YmJewHPdJPUql0hycNLtWq+3TpLuO2wj2PXjVBHI9KckXCoXNjl/6ocn9SND6NEfE5gbsx/4Gx8wnl8vtxX7PZp0YBq4HWHLuSWF/Un1U7Udiy/tdjIxOXfSZbDa7xdHTDa7mBRZ909Wwv0uCcopqv0pIWGLv6+ZEGxMHxe0YfR383rKhB2hfhLPKlvjIRtN+w015xveUxdIeg3fRn8DPSBulX9p8r+gBidZSbXZVz0uSkuTgV9NCPfFlEp5nwqaru6DvtI730zTizqv2ThYsGs/mrGrDZyMIB0+pr3UmKqTYXfjL1WQNaL1/fmIEXCJwwRYiCNeWsCxEErkd0+bhw0DrhKNNDIODxbmTnly1Wt3haKM6z3XT/gquIP7RSSz5SbIJ1pIw3zMxTeL+qAls7hVoUcLE33D1ZYFzB340mx3dbbuK/jQhYStar5lkl6MvQSoTbjabm3D+QIJ107AnGo3GNm1PyWAyqPXrW38BHwQJf1IMqUsYp1Y4eLNywhFLg6o3LDKWnBQWJ+4I7PIMsqYlIY0JS6HoJ9H1I9mjDDYn71zjZuCC6xNHOPhpmdbx7ojNLcqr1pMawJht0fjeStDa4aAiSyJt+g7Dc6ZJtTeN/muqPYfj8bWsCvV6fTuDXoYdacf7PTw8PDw8PFaM30eWDf8tjdnCAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB8AAAAZCAYAAADJ9/UkAAABt0lEQVR4Xu2UsUoDQRCGLySFgoJNEDHJ5aIYAnaiYidiYRptxMYHsBF9AhULH0CxsrG0EcRCsBBsfYOAlYIoChYWERQ0fpPbC+twyV1K8X4YLjvz/5P5d/fOcRL8axSLxQHXdYey2WyfrsVFoVCYp0fN87xBXWuLUqk0huibeCEaxBzplOZFAd2B9MHIgq6FAvIZ8ZXL5XplLc7NAHXN7QTjWgyItqbroYB4bwRVKyfrhs2Lguu7vu5Km8/nRyDvOWaby+Vyv2nwoagdAf+ZXuM8X0XPTg5rTiQQzoiYbTzWtQ5Iwb+Uo0N7IXoGWdSktuCS7CO6Id6D848LuWDiWn6jrxj3d7Hd02AJwSrxhosVUmnNaYMUmkNr4Azr067dBxChhBPjdRPXcOsMvGzFpunxoPm/AHED0padk2Zm8kk7HwZ4NWI9JB8YyOhaANmyJgkHPUEy+HMGm7DJYYD3SFRC8k+mt6drLRjCZ0gucts551EG3NF5gevfH+lzomstIL7F9Xmw5rs8ZURXNs+GeaWqrv+BkvPetuv0m3b9j470ad4HcrM2x0aa4i7EI55rupggQYI/ix9TznxbEfwadgAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAaCAYAAAAXHBSTAAACvUlEQVR4Xu2WP2gUQRTG9yAWoiiC58H92bf3ByGgWBxaBGwCQkAQkYiCFoKFjZ0QLW1sLYKF2Ag2NikMKkiwSBlSJ1jEgIZUighihAjx/D73zTm8252N2CjsDx679743M29m38xcFJWU/Jv0+/09SZKcj+N4utPpHPSkSrPZ3Ov9/i+oiMhL2A5sAPuiz1nVbmGih/wG8E3Ct+HZQ18nRt9Am/tFMSZ+iWPbNoWg0VlOoNFoNK2Gr5bo5AZWI9VqdT+0xVAM/Jvo5pr1+yBmne3Zn+9ndaDtHWqY5Iyv5YIGl9BgB8+7VnNowlvWT+Afh63BPjOu3W7XMmLeM876faB/y1uUKK0U5rBthRGwCj0NXrGaDyeEVXps/QTaLDUsyhTef+D9ldl7Y4zxfmfhkv5kBYdoNdTr9cNWG4LBz0i6f5bMgTACYt7hC5ywfgJtDX31+Y7nVU3ugdNbrdZJKfhKbK/t7lnN4SblxsoEAU816LbV/gR8oeVYDxCWnia36ek37D6xMIbtsADnrOaQtISZb8dqQ3Tw8OcsgMkyId8nZm9JQWkTxKzCFkOTd/nidcxqQ3YVVADaj9tyEK0ATPay/n7r61kgZksCpRel+9Llm08oCIlOMykXA7sCm7BxoneY7+P+lPRu2UY5nS5Ilvw6JEJlBf2mxoS3SmhSjlCMu5+sn3hJPAvtE8LyZ2xe6XW73SPQV2Cviw40DvycnWHQY1Yj3qZftRqB/0KeFv0+oge1Wm2fFX3cIWH9hH/ZtJ+PVssESZ+SdFNnrUAFqzzDDuOc+4l+6HPW79C+M5P14F6Zk4z7Cb42JjyP5xspuBJG4JGsq/EV9gL2Ab4FTPQo3p/YDrEYovHOeDGP3B1JehmvWz/B5XxcdNI59h12vdfrHbBtd0sFCSTo5JGk/w4u2oCSkpKSkpKSv+Mnjej1agnaxG4AAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB8AAAAaCAYAAABPY4eKAAABkUlEQVR4Xu2UsUrEQBCGEzwrBREMgXDJJukErQIWPoE2Nr6G3YEPIFwrVhbXWd1LXHFY3VkKcmBpc4WI1bWn/3830XWSSNLYmA+GZGf+nd1MZtdxWv4lxph92C1sUNOOkyQxURRNYS+5xXH82O12DyXnlR3D+FqvuwKBJwrw6lq+D5olc9I03YFvAW2W+8IwPBDtu60l9EN7o/0/gGiIRycf+76/JQnnlmwFfGPP87aVb0l9EAR7HLMqYJZl2aatK4Cd7aJcJ8qXyuJj20+gvdM+6CbU53nwvMd4oHUF8t3aYGKfyVDSMxVyK/TsmTez/iVT/h6tqQ2/GDZnBXSsgg70Q24Yc551sBFS8r72/4KLRS9l3lIHGyFJTrW/CmjPpeycxxPy1byNyJuNHa9jZaCzj6Dv4dU1UnrYhdbVgk0mu68FtDNH7gd2u1kfu0njpuP5NdJsOqaRC2ekK8Svlq/n3VEf831kRjqm4VmGPWi/5ODihRuvjA0Rl5ot5LWq4/ZVi/GrjsMWdo6WlpaWP+MTMeSLWePYvOEAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACIAAAAaCAYAAADSbo4CAAAB5UlEQVR4Xu1VPUsDQRBNMIKiYGM8yOXrLpWgggQEC7ERwcJe/AXWCtpY6F8QEQk2tlY2AZEgWvsD0lgESWVjFcHC6Hswp3OTSy5aWdyDIbfvvZ2bndvdpFIJEvwChUJhpVgsPkdFqVRqIPbsHEEGnnM7p1wu71CMylupVGZskhAcx5mQl7Zd181rzfO8dfCf1Wp1VPMB8vn8OF5yQ4/VwL0gHi3fF0i0hgld/B5YDSsc40sQu1YLgGIdepiHYxaNcQ18yXoHggXoRBq5XG5aCtmwmoZ4TvGYRvFHeG5aTywwqcVEXL3muTJwV9A6mo8CPHVZzAM6sWT1oYAEXSaJ4M+kwFWrWcCzJV35sNpQUHugg6hJPJHDyhasvx/YBcnDBaWtHgvselcS1BU9gvEh4hWxqPi+gK8pi2Euz+qxkI3KExPaqBj7TMo9onkL3/en4GvwN/g8PM481tY7EOwEosXOaF6ONAu51LwFPBcshM9yjNmZd8Sy9Q6EdCN0f6gLjqvruVsEaWj78MxqEjfqHOch2pqPhbws9Fmy2ewk+HtdCDpzywIDD8bH0N9+Zn3zwebvOYU9CG5CG5AygQefal4K4X/OHfeAFBiaozuG52urMwL9z0DiTSQ6QWxbLUGCBAn+A74AYvqnYg2f3QwAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD0AAAAZCAYAAACCXybJAAADGElEQVR4Xu1WPWhTURROIIKgIooxNH83P2IQBy1BhSJOOkjRQQQHxU1wcCpIoJMSiptDQYWgg6sK1SGIP9CCYocOLrq1qFBwkA4K7WAh9fv6zqUnN3kvL4KL3A8O797znXPuuX/nvkTCw8Pjv0WlUjlojGlBvkA2IC+l3yoWi8/x/Q35ae3L5fIp4WlLeQq5Tw7219B+pDi2b1hftO8p7m4ul8tbTtlMm61cVhGz7tpYlEqlSypeC/3brk0oMpnMDji9hSy7ieTz+b0SdFTrmRD1GGi71gu3mYirJ6BfYbKuXgM2bch7iXPW5QnmCW5WbL67/EBgNU/DsQOZdDlCAs+l0+mdSveN+lqttkvb1uv1bWLfM2nuGhbxgKt3Ad9FyJjECctpBqfuuNhMufxAIJkGnTl5lyMk8DM0U0r3WfQjypSxzoi+Z9LY4Seurh/gO8e4jAGfxy6PK7kb+hPgL0A6YXlHAo5fZYCeo8rdIceBtF4S28BqH7E6+F+HvIB+3Z00TwmT1Lp+QLxMoVA4z7Ys3pJrA90bnjB830Ha/fIeCAne0To5pp/IIWhJcwR3gBwW5aSokug/xDeF7y9y9jpUq9UC+h+3vMMBuwnWGGkzrzXNsx5Ibtzl0NMZCa6SBO8n85Bx14eAfkoGPSf9UXtfjdx3O2m0myZYkIEwwTWy7TXGsX0WL+T7WjhWeY5fsXxsSBHjBKddLgqwn5BBG9JfUNyCxBzhrlibOIDPomov6UmjPaMWckVzQ8EWMXuP4oI7bCfNRPC9Yjkj9527wMKG471f+0aBvrotE0vZ4qU4LmrXlYwNOC4zuH6O4gCLdMwEx4/v+7zm7H3nF5N+pbko4Hrk9OIbuUKQccis1SPmHtG3rW4o0HnYXSbgd8gER+wHkjjscJOS1GZh01wEWAib+t1Xp+lBovu5vGz+4qlKwuEi5KoEbbCfiJ8gB+Y7yoLVRDepOcaTuF2LEYIknz0T/M7S5042m91Hohg8l6v29WChZJ7QfYCsyzhjjKED/jNI1b/p6glwRyG3XL2Hh4eHh4eHRz/8ATjyDapMh6XZAAAAAElFTkSuQmCC>