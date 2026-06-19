# **SALLI: Python High-Level Control Codes**

This directory contains the Python-based control system for SALLI. These scripts run on an external computer or base station, acting as the centralized brain for telemetry monitoring, operational gait styling, manual teleoperation, and joint calibration.

## **🐍 Software Architecture**

The Python stack communicates with SALLI's primary access point via a fast, non-blocking **UDP network socket**. This ensures minimal lag during real-time closed-loop control.

  \+--------------------------------------------------------+  
  |                   Python Base Station                  |  
  |  \[SALLI.py\] \<----\> \[Teleoperation.py\] / \[Calibration\]  |  
  \+--------------------------------------------------------+  
                             ^  
                             | (Real-time UDP Broadcast)  
                             v  
  \+--------------------------------------------------------+  
  |              SALLI Robot Wi-Fi Gateway                 |  
  |             ESP32-C3 Master Access Point               |  
  \+--------------------------------------------------------+

### **1\. SALLI.py (Core Library)**

This is the master library containing the kinematic definitions, the gait generator, and the communication handlers.

* **Locomotion Generator:** Generates discrete trajectories based on bio-inspired spatial traveling waves.  
* **Network Controller:** Creates the socket connections, manages target IPs, and packages floating-point joint angles into lightweight, compressed binary streams to keep latencies below ![][image1].

### **2\. Teleoperation.py (Human-in-the-Loop)**

An interactive script allowing users to drive the robot in real-time.

* **Keyboard/Gamepad Mapping:** Translates joystick axes or keys into speed, steering bias, and wave frequency inputs.  
* **Dynamic Gait Switching:** Supports instantaneous transitions between land-crawling states and standing/idle postures.

### **3\. Calibration.py (Servo Alignment Utility)**

Because SALLI is designed as a low-cost educational robot, it uses budget micro-servos. Due to manufacturing tolerances, two servos receiving the same PWM pulse will not align at identical physical angles.

* **Angle Trimming:** Allows manual calibration of "zero offsets" for each individual joint.  
* **Mechanical Safety:** Prevents servos from rotating past physical mechanical stops, protecting the 3D-printed brackets and gears from burning out.  
* **Export Configuration:** Generates offset vectors that are saved into the robot's non-volatile memory or loaded before running the main gait routines.

## **⚙️ Mathematical Model: Sprawling Gait Synthesis**

The leg coordination module in SALLI.py coordinates physical limbs by enforcing a lateral bending relationship. The control loop maps the leg phase ![][image2] with a phase offset relative to the local spinal phase:

![][image3]By tuning the steering offset variable (![][image4]), SALLI curves its body while walking:

![][image5]Where:

* ![][image6] represents the joint's oscillation amplitude.  
* ![][image7] is the driving angular frequency.  
* ![][image8] is the wave-number (spatial phase lag between segments).  
* ![][image4] is the steering bias (![][image9] to turn right, ![][image10] to turn left).

## **🚀 How to Run**

### **Prerequisite Libraries**

Install the necessary python dependencies before executing:

pip install pygame numpy socket-client

### **Running Calibration (First Step)**

Before walking, verify that all joints align perpendicularly when zeroed:

python Calibration.py

This utility will output calibration offsets which should be verified and entered into your master configuration file.

### **Manual Teleoperation**

Launch the teleoperation interface to control the robot over Wi-Fi:

python Teleoperation.py \--ip 192.168.4.1 \--port 3333

*(Ensure your base station computer is connected to the SALLI-generated local Wi-Fi network before running this script).*

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADMAAAAZCAYAAACclhZ6AAACLklEQVR4Xu1Wvy9DURQmqYQQv5Jqmv54r30v8WOwvGAiJIZulg7+ASOLiMEkMRlMBoMfMTEYzCaDQWKwCBaJihhZMBDq+9p7k+uotoqo5H3JyT3nO+eed7/e++5rTY0PHz6+Ddu2uyRHuK7bLDnP8+okVy2oTSQSQ5Zl7csEEY/HZ5E7gth5+GnYLuInWfenwIKWsLArjHOw4xJistoQT0aj0QZZVxUIBoNNFFJCzAh3JRaLOTJfVShHDGskX5X4ihi8WyGZL4AA5kyh3xrG7VAo1Ah/AXbOGNbDokgkEgV3QUPfTtkEdRvI3cLulb8uaz6gHDHIneKIDSKshf/CBcg6CcxbQd0r7Exz8Les/Lt3AAGWotkziwumnkEymWxBfIj5bXoeb0/kN3X8KcoRg0a2jlG3zIeXOnrqR3jF1JTguPBxs5ac3nX4YVhGnoIfESOBHepD7SNsVeZMqIVnuDjBZU2OkBz8acXRcsfMrP8UxcSgyQQbYhw1OA/cA+uL7c53xBA8dtidfvAnKn9t5guimBhuLRvxg6k5Y2d2EAaM8neoVAye1Qp/2cxDVC9rTK4gSohJgb80OcSrbOw4TofJS1QqhiPnyQ8zuGczfgcku9E8beXPJ4/NDWOaruEtwvPKa1RR+ja70zUFEMCPMAzbY994/h9DO+IBxXHhM/DHyKk15Djl58TAlrQgjC7nygdVBPWeLNJ++0+muoZt+urIhW11bfvw4cOHj3+BN7Khw3MBBS9rAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB0AAAAaCAYAAABLlle3AAACDklEQVR4Xu2WPUvbURTGE0xBacEWiWnIy20Sl04OAcFNxA4d6tBFadwL/QZOnQpFcBEnEZyqo4OKHToILqIfwKkQROpUSkWhLsbfk9wrh1sHMX+dfOBwz3nu+d/nvpx7k1TqEQ+NV6BcLtdxe+K+ewF6L51zZ9hfbDvuTxyI/MD+yK9UKjn8n2rjvMTAdr5B5FexWBxSHETh38W5iQChPgb/jq0QpsUVCoUiosf3JioxBFqIFwJH3BCHvbW5iYGBmxLAzRhuQRzbPGxSk4Nf0SW2ZEyxJtLe7qSR8aJNS3pOoiHe5BiOQqF1BQbLe4EvgdPZem4xcKGwQtwVgiiPwsfAlUqlSbhz/yq1gT8BdxnirpDL5Z5K1F4N4gutzObBbWEHEfcB28PWbb5fyDy2xmLG6vX6E/tdSGphDfnVarXf+VcpyjnGlkOssyX+htgAE57BXzW5vxGboh3Xd/ECQtJ77J/rvLmHcb8Af2qvj59oHm6EdpfWQafxF7FR5TCZqjO18h+y2ewzzTp1wxVh1r18fMAgLxT7I7nA5uibTvlfI1+AzZDna+Nuj4svIr1QrwkzXnTHpKT1c6id0I4EEmpfizF5t4eKTJXMgJ8Md2T8zwh81RtOzgZU2vvX9/xOqNVqg3EVMmgeseeWs6D/JOYSh+s8nVu4PUxmVkUW5yQOnbPOUcXkHuJfxyNuwhWKnInN3geboQAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAZCAYAAADqrKTxAAABFklEQVR4Xu2RsWoCQRCGFQlomcYUd9ze5SpJE7jKzkIEn0HfIZAinWVewELBzj6tRrAxbdLEyhew9w3Ub8zdusydActAfviZ3W9m9vZmS6W/qTAMq7iVuqrzORljJp7n+bL2fb/G/i0Iggdd56pM0dIF7Hv42WVW6alzzWHDi00kmtz/02Vc6xb+JTmXW1HwQbJLTORKURR1iDv8rmutSM5kUsQBHtHcJ+6JL7rWioLXArbBW81PItHIxqz4Ch80P0n+oegRzc8Q8k3ZhDQXSQNea5493iFJkpuMyRo24cCxy61IDkku8BPbijCuOoXvCxtEJL9puGdZieO4zvvc6ZqcTPo+ml+UDAG3Nf9VfOHxqq/866wjDjE7j+13C/8AAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAjsAAABMCAYAAACLbnYLAAAR+UlEQVR4Xu2dDaxlVXXH32Smif2wBQulw8fZ9zHTUrStmmlrpB+SVlPNaDVCghZiTY0tsVgbibaNpLGxJG0t1o6fmUxLxRAJkjTGUrCZ1OmQkKk0gTRQCThhMDgGCBDJQKQEput/9tr37bvuufede9/HvPf8/ZKdd87a++yzv/c6a+9938ICAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwNZmcXHxlSmlvVG+Hpx99tk/EmUrwfLxzaZpPhzlK0Xx2p9tUb5RsTL4VUvzfVG+kbB2lzZbua43e/bs+aEoc7ap7FSG0eNUobRau7vU3FuiH8CWYTAY/LV1vv3m7jB30t2/mvxVMew0yrPnnnvuD0e/1cbes8/f93/WQb8tV6X9yUp2QjKbmM+IcWwFLG/fNPddy+v50W8tsHe9x9rFF7ycH47+8+AD7fUW7yD6rRKaXJ6x6F8TPTYipR1H+Uqx/F/scd8b/WZB9WVxHF3N+jrzzDN/LMrWA1fa7jV3TfSbgx0Wz++be0jlbOPgOTFAwfx2W5jjUxSidcHr8u+s/73cReorJ+3+T0cCAmwlrIHvsYb+jLmHze2M/suhTiJnA8hZ0a8PZ5111o9aGm6K8i7KhFsrVnZ/VLLzzjvvl6ug6rxPzZOf9cDycaXyHeV9sXy9qDxbPH8Y/dYSr+tVUXYsnrcrH1G+mlj8D1oZHY7yjYa1/1eUfhT9VorF+UGP++noNwteX1dF+bxYXBeaezTK14OqTPZFv3mxuG5VnNbeXhL9aqRQWJjLonw9kSXV0nqwltn9d9MGtywCrIhzzjnnXGvkj6Q5lZ2VIuuEOlqUd2HhDmmg6pDpq2RPLZfyE2UbBUvvLfN+1erLMWWL3ElzT0X/tcTfuVrKjuJatcmmC2sDP68yOv/8838i+m0ULI2/Y2l8POUPjpPztou1xCbndyhtUb4CZA25xdyt0WOzkvIHyPNR3kFrRVGZRo8+rNT64hbVsTg8/XdFOcCWwRr4zpQVnVOl7FzRdyC1cPc1YX05TVB2lBeT/Vot2yhY2o7PO6lpclxcXPxF5blvua0W/s7VUHY02b1o9fP66LGayAJo77jd3vXa6LdRsEnvG5a+j6X8ZX3yggsueGkMc6qxdH1J9RXl8yIrsMV3tGvS3ax43zgW5V2oLFWmUd4HWbejbBbUF8wtdsilgH00ygG2DGmKsqOlFpNd5R1ZCsWHd+/e/ePuvcPu/9jk/2junrIsY9fvSdnycM+uXbt+SuHt+kiT99JcYkG2K5wm+5RN4yVubZS71K4vLO+PWGd8o01gL6tlaYKyY+wo6+ea9CzM+8y94O+7Y8HTUfA0t3uY7D0/nXKa318vmdkgfYHJPu952etWljb9dTjzf3nK+4ZO2PX11fOvtLi/4um9Qvm1+4vNa0cJMw17TpsNHvFrWeO68q1yeonn5X7zv8n+7jTZXyrd5m5f6NhgamGuNnePO13LnUyV1c3vR5Sdqmzlp/S8a7n9WxbuTeYOLrOUt93i+ueUJ8WbBnPuvbFn32Jx3KoyiX6nmiYvX71d18n3zsnSGsMth1tnv+N18PWUl2lU57LIqB0cUfwlvMv2qz3Y7Xa73utt+v6qfw/xeEeWPQr2jj8zv8ujXPjekKstzNt0b+/4LYW1+3/3OG80d11ap48sV37fr7Kwvvgb0X9emmydVn6GVme7/oy5z3ZZFVMes+ZSHgcrUHZ8zP26XW7zsej37O+v2N/D9hH1SzE8wJZCA02aoOz45Pht6wynqaOUe/mVvTbeyYfm95QHsHaDsLlLzD3kHUsDr2T7Fc7ur/QBtn2+eteVdRqWI01WdoaY/1f9PTt1msjC/qdd31YPRHb/pIeREvEpcx/x++s8SGt+Nnd3yl9HutZGaZ2ieTp52dnfa+Rn+XiV+b0r5eWJdkIz2f8kV1L01/N80zKT/hAvw+O6Tvlru/NrTBuzlTb3P+zvkmIqxfWZJpx+0kDn8g/IeZq1B+Gg4ijhPN0jyk7Km6VVDqf7BkyFua0OE2nyvoWpg7bF8S1z+3wpqt0PUTZ2Kn99N3mqXdizR+fdU7aWWBncXPKRerTjLiyO37bnTpjC85O6r9qc+vUn5Od1Mqw3u37MZXK3DbICfpG5W+35BxbDiSGFm1RfKVvorohyYfLXy9/cHbJYpaWPnvajw9v/f8X3rRXKq/KY8ubk56L/vPhS5PNNtiRv8zr4I3OPDjr21akslf8o78OkeuhDyvuk7mnyR+XJyp2IYQG2HGmCsjPIX1+fXhi1AmjC/7S5rxaBXV+rDhOXZSTTpBZk7b6E5WSzkHpMEub/bzGNujd3tA7nE6Pk+/yr9BODjCwlGiQPlTiUNw87tEQ1SxtNhxs5XfEYbib2r6ux8uqDPXd84Gv9blU6Zu65NGGZxtMy8gXZZEvHM+Ve6VK4uvxKOZT7gsdXJk0N6p9M+TjtUJEo8U07CZdyWY7svSqkrCC/YBPIr9dyL+/2XU22TvUi5fb9bNjAPobF+d60ZN2b5P5W5a/JQq6vwtWFrJ4W39XlXpNYyvUw0zHglPvtY7XM62/YlxWvwnWEGWmHpW0qLUXmbV/Pj9WXya6SghvlNarHVPUbkfrvb1k1UraKtv0k5cMLY+17HrzMNAbdog8p+7tfFqRSn6W/1pSxY2F0bO1FXTezYu88YO7aINaS8pe60gmwpUgTlJ2UB6TWIlFjssvlV+5Lx42Tt2Rxgkkdik2XbBZSD2XH2F6+fAt6RnmuZWUCiPnWBJvyqa8xZccGiTeWcC4rX3gFDSbDCWSFyo6sQot+WxRPpTcOYC3u1y57FTSZpkrZSXkAnFnZqZStWxaqZTjlPeUymFgf5n9o0qRufg/6u0eW9jzdbdmm/FsvNVqS7Jw4SnlPet8pQnX3sbpNJv9ZBSmLdUAhpaprOUTYM/f5c++WAuVilcdwmVb+aUJbr2Vdys608jP5kQ7ZNXVa3aJz40JVP56edT35o35a0uXvj21ohJSXWr9n+X5D9KtJ2VryhPq+ueuLAmzv+ll75zu7FGJvy3ONAStUdu5sOvbJKe2xjgC2HJNOY6kzdg1wpaNW9xOVnTjhpQ7Fpks2C6mHsuP7Sj6kcObutwHjbX7dNQFoOWcsrpQtDo9ZXD+je4vjZk93OylXX3jPDvLSgpTIoTPZaVW4sfJaDl/OUZq7XOf6v/vFPI7Un5YQTPaAJssqjDaNj00GdXwlHnNfTiGvcl2DfCFNUHZMdrrHeazDryiiN4R9LVImr5ukDEybrE8VKS+raj9Xu3Qrl5aWUcdOqJnsy1Y//xDljvbcDPfVFVeXv8tG2kHK9dSp7Jg7FGVd5ZfCaaqUFYSR33/Sdd2fdK/4upS6iIW7qHEr2nLOwu7tsxwspSdNsYYWmmy1VL4/Gf1q0tJvf2nPlZbntMz96hiupumh7EzKu6X/cJR5/i9aWEZZSRP2rnkelttDB7C5sMb+J+po5b7xCT51KDtpsmVnzZSdlDfI9t6wmJZXdspem6E1Q7jsYXX+ar/DNGXntRb2dZp0mjw5/W7ciJvykl607IwQlR2lv+mYSGp8Y+WkjcXtb+7US0mVX5vHWqZ3SV7upST4AKq9OtrIer+5v6qfKdTxNf6TASlYdvpgz9yodhPlXv56x5ilqvI7EP2mkfKk3lmnNeb/gMff201bqpuEf1wMl68KajMmfz7NOOlY+AOyIpR7aysvM9l/pFwvJYzSO5eys+D9p6u+6ncIhZEyUe59qW7kxwxT7iP3lbKzZ94Q+9FakXyDf1G09O4YZlYsvifqckx+qs6vtQ9q7MCFyql+ZhYGc1p2VN5d40zK+w+fW42yANgwuEm5PfVRJlufRKRwDAcgoUEhdUw6ksmv3JeOuwJlp92wW92vqrLjS1AnFa6Wu+xhDQDFr5RFV1wm/6DJT4/ymuQbl+PEkPKps8/6bTt5zKLseLqejHJh8rsUXz3JVH5tHmuZ57e27OhfT7SbnpcjxNeu9Zs7piWtOpwUqGmnO1L+khxrW41/9cfyE8WyFfxUlrLUTZwAUl5meGS5U04Wx2mpw0I1zcU4etDuc+qyQlX9cLhUWk4zmbt2kqUs5Y+Uq2pZkxWnodUldbQDr/c+yk55fqy+UtVutHfH3vtAU02a5v9Fcw+W+2L9bPIJxVZxt/t/6bI2rAVpyQK26Pd3xjCz4vENf7AxVcqP/b276Vg2Sm4NivI+TGvr09CWgqLk1agulJZJ7Qtg09LkJYoy8arjtZOlljPqcD7QahL9SpHpuuoYOwb5p+jv9A6v0wdvkqzJZlXJPu7XF/rf1gqhaz2vOJPvGdm9e/eZinfQcboooq9XxeFxtgqUuX+qZCNfU+6vpZ52H0PKp1T0nNJzg7nr/LnPeNh9lo631nE01a/cVk5ma/2Pqnp/hAZ4lVv7bzf86P0N9ddryu/9TV1buMNdk58wv9ckt6S5u7xSLEr5a7Ov/JQfHfO9+IwzznjpYOn0m77aLtVzdR51rfh9iU/LKuUdxR0rx5AVrqrTF7z+WpJv9izWiEFewnuo+HfR5Mn4rqZDefT4hj+WuGvXrvPs/tG0VA467fcplVmT/92EliVeqOOoGeQN0zNZg1abWI92/9baemN18AvKk/KR8hLLh1wZOeD1I1nnskvKyo76T1tXHl596tWx3vTequ/8haflHWoz8jP3bg8ri+ew/adscRr7wbnk/bnE3+QTf+Vebn89iarOTHZEdeLP/+9Ch7VyrVB7Ubrscrul4c/jB9qs+Mej8jlcekx5H9uz3j47T6mlvM9qrl+0Hsyn7JQfcdQS4weKUGVg7ma1iTowwFZBX8PfN/e+MjjZ36/FQML89qZ8tPiEO123k3T5StPzldPAG2Xt13iUlYFmkH/TRkecdVT6yUkTf02ztKTR6fS+Ory9450m/57ib/Lx9r9JS78jc9DTEOMZWfby5YcYpnUW5+eqoBpI9T756ZdxX4zLEsmPp5t7bDDlf5FpYOt4V2sFmlD+cof0lR3lei7KFL8mx676cXevlOCudJQ0qlw0YLpc+06+ZfevW8rFOH5CTV/AYyZ+39ipH9o7nnKbe6pM5CkfGZZCcK/SrbJLeZP2sRBNQZYUKUSn9KRJysuDKp/ihhvNp9TjAUv3z7nyMrT2RMzvmOXx71PuP4pX5dPut+qot9ZqGWRyen/5aCiu3sSuyfmJpbdm1O5L+FLnKbf5VlYr+AX/mQOlVScLL4v+a4m/W+lTO10Nq44sfFLyamuWrLjK39OTrCUpl/XY5u4+qE6jbDncut2O3ea+ozHQy/8bC+uobALABscGhY/a4NBpdh5kxanTbzOQsuWn8yh3mvBFvxpMe+8saLIZdCzhCclTtuht2gFdbU9LeFG+niTf19GlvMBsuPL6uLX9V0S/Psyj7PjHzMj+KgCAMZIvtUW5GPjvykT5ZkFpnzQQpmx9WStlR2X6XJTPgk8cR3zJ4L3Rf5AtTo9H+WahfJEv5GWIj0T/dUTvV311LqVBf/S7Q00+4TWXAh63G/RB/VvjVJQDAES0HPJmGzSe1UBlf3f6hlltNNRvcbw5PrBZsEFwkPK+K/2SriwhOzWgprwk+fG1/JpP+Tj/JVHeF99X9t9dFiLfH3Kwz7LoRqXkwfL3tcGU5c71IuXll7nr6wcdq8PLrPy+H+Vrjb3z7nlODgLADyhN3th5e8rWEO3/uT3ux9mkSJn7vCs4ypv+/cPIv5RYI7R/7EEpXNGjLzrePOg4zWPx7p/nK3ijIYVu0t6P9UZtQvUV5dAPHzPWo1+NYO/8g4U5LUkAALA6bIu/br0KbNsoCsIWZFuXcgnTocwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA+vD/83Oh35wbLFUAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAbCAYAAACTHcTmAAABgklEQVR4Xu2UP0vDUBTFU6JQURCRECRJ27RuDgoZXPwAFtFBBAXd/BD9AOIkgpvQRR0EFycXcSq4uXe3Ig6OgoND1d/FF3neCjXpJPTAIe+de97J+5c4zhD9EIbhWKlUOq1UKkVdyw0Cd8rlcsvzvAldy4sCgR+wA2d0MReY5RxhXfgSx/G8rmdGFEVrhD4QuG9mW9eezOBg7ghtCCWU56r2ZAInPkvQurQlzIQ2tC8LRgg4TpJkVDq0lySUmZ9p458h1wfupX05ILOnLcuWwuWlU1rsAYPfMF7wbBqem9Bb7ZUVob9r/QdqtVqE6VlOPSX9RxPa0X60Q3ip9W+wZ4sYnn7Riyb0Vdf6gkFXzOxI6wITai+zwMs25fCq1eqkpX8VMW9TvJFB8ADNTYu+74+j7ZpQuVYbchvgCQfoo3UZu2XlOU4QBNPpgJT234h+XddhG88CZZf2PXc6sCIHg8wQLms9N8w/9lr2s2f5eSFfG0tvSjDPFV0fBK69/0P8M3wCyEBnjAO1UagAAAAASUVORK5CYII=>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAaCAYAAACHD21cAAAA6klEQVR4XmNgGAXDBhgbG7MqKChUoIvDAFAuU15e/ga6OEgiAyjxG10cBoByb4H4v7i4ODe6xG1lZWVZFEEkICcnpw1U81pUVJQHLgi0jQMomIOkDmRQEVCxM5qarchqQIo80ZzACHIWELfCBKSkpESAmk8hqQE7oxyZD3IOyL9AcRuYGFCTB1DsGLI6sEYZGRkVGB+oIBiIDyD5hxnIfwnyJ0wNTGERyDRFRUV9oOR0qDP/A23ZCBID0UB+M1ApI4pGIGCBKQYZAFSoAKR7kMTWoWuAA2lpaWGgAksGJFNBYiCMpGwUDEMAAMYeM81UdfInAAAAAElFTkSuQmCC>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAbCAYAAACqenW9AAAA+ElEQVR4XmNgGLxAS0uLDV0MBcjLyzsB8V8g/q+goJCOLo8BQIpAimVkZKTR5TAAUOFSkGIgkwVdDgMAFf4GYXRxrABkKhA/QBfHAFJSUiIgxXJycuUgPpB9H+iHRiD9EsPDQEU2QIl/QNoFSAcBFSgA2a5Q2yYhq2UBCqwBSu4AqqkAhoYQSFBaWloGKJZqbGzMClcJdcJVqClXgEKMcEl0AHUCKCT2A/F7IH7FgEuDPFr4AtmHYR4FOsscyNdEVgx2AhIfrhjIPgbU4IGsGOTWB0j8rUAcBPQoJ1BhBlwhVBIUvtNhfFlZWROg2C8gfo0SEqNg8AEAvNJCdHF0oxYAAAAASUVORK5CYII=>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAaCAYAAAD1wA/qAAACYElEQVR4Xu2WTWsTURSGU6pSFypFUEo+Jl8QzEKFLEQoxYUILlQQdxHxF7QQQX9BF9KdKEKpiAt3bqWgm7oq6iaLQtdKuylI0YVIbYnPIXfCyeltZqaFYGAeONzMez7mnJs7mWQyKSnDpVgsTmDXnE1Y/6gwHgTBr0Kh8Jl1E/tpA4aJbCS9TGez2bPWdyAkPKbxj1rjuom1tDYMyuXyGe67xyAP5ZpBclzvYHdN6H4IapNYNFoL6Y3WhgGb+oR7P+fjWKhxvY2tqbD9EHC1VCqd1xrFJtG/ik/rPohZx7ZyudxJ60tKPp+/Ta0O/VzSumyo6AOfW5r+xDLO2iC4SZEbbgeWbewguMkVcv5gC9YXF3LfSsPYlNbdt9SRHrXeBwFtrOUKhLZSrVZP29go2ISLDPSB/FdYyfqjkPtGDHJd630QMO/R5LhsWD0JMgi2i61m1HkfRIxBbmm9R61WO+WbMixo9aTITyd1FuIOc+hBcDZ9D1DQfdCPPIjghvnNsZvJRAxD3LuIQfzPCM5nVhPQf2B/rZ4UarzAduWHwPp8SD++Qbied4OUtR46L0jDVq9UKudc0n3riwM7XyN/j/zX1hdF2BO500Z/Lz1prUfQfXN3Go3G8VCTz2iLFHqp9ZiMkbsadB/wvh1NwDFyl+QoaRFtA9vWWg++7i84b2KbJH5n3cKW+Vy3sYOgzh3y1smbs77D4vrZYZ1lXeMeTw/cWALa7szJn8Up+3aPQ71eP0HuN+o8sL6jIP8SqHmP2ovYI+vvI/C8P0YOpp0seN4fIwdn7rLv/ZGSkpLyX/IPoj2lsgxHoPcAAAAASUVORK5CYII=>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAaCAYAAAD1wA/qAAACZElEQVR4Xu2Wv4sTQRTHI1E4EZVTMBxJdvMLghYqpFKuEBHBwh+IhRAL/wBRiKB/wRViJ4IggljYiZ0caKOlXnEpDqyVu0aQ4ywsTo74eWQ2vLybzW6CBAP7gcfufN+bmfcmMzvJ5TIypkulUpnDzjmbs/5ZIR+G4a8gCD7z3MC2bMA0kYUkl8VisXjU+mKhwwMS/6A12m2so7VpUKvVDjPvDoXcljaFlGhvY9dN6G4I6tKxYrQO0iutTQMW9SFzP+V1T6TR3sTWVNhuCDhTrVYLWmOwefQV8Wl9QmTLrmJ3Wq3WPuvUlMvlK8T1yOeU1mVBRR95bkn6E488zxbBbQa56FZg2campVAoHGC8e4zxjclvWn8cxL+WhLEFrbtfqSc5an0IArpYxw0Q2cdGo3HIxqZBDif9f2OrNPPWPwqZN6GQC1ofgoAlj/YVW7f6KJjkJav/nl/0pPWlJUUhl7U+oNlsHvRVGQ1odR8k3iT2rZj1jcvEheBs+w5Q2D/oqQpxRexgVesbF8Z4k1CI/4zgfGI1Af0n9sfqcUgRUoz8OtY3DpKPrxDaS66QmtYj53FJ2Or1ev2Y63TL+pJwB/1x2P/cnrf+JKKcmHvR6O8kJ60NCPs3d09/2+Ud7TkDPUv65o8i6P9T2GLbXs2N9+XaS78XspW0iLaObWptAJN8wXkJ26Djd54/sGXeT9jYSZHFYJ5rMnapVNpv/XG4fLZ53uW5xhiPYheWgK7bc3LzLtjb/V/C+GexFYo5Yn0+pGhyuyG7A7tv/UOEnvtj5qDa+cBzf8wc7LnTvvsjIyMj47/kLxrspVZJGexpAAAAAElFTkSuQmCC>