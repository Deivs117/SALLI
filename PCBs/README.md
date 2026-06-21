
# SALLI: Custom Electronic PCBs

This directory contains the electrical designs for SALLI's custom printed circuit boards. The electronic system is engineered to solve a common pitfall in amateur robotics: messy, unreliable wiring harnesses that introduce high resistance, noise, and power failures.

---

## Electrical Architecture Overview

SALLI uses a decentralized, modular electrical bus system. Power is distributed along the spine via a ruggedized internal backbone, preventing major voltage drops from affecting the master microcontroller.

```mermaid
flowchart TD
    %% Definición de Bloques Principales
    Battery["Main Battery Pack<br>(2S LiPo / 7.4V)"]
    RegServo["Servo Regulators<br>(5V - 6V)"]
    RegLogic["Logic Regulators<br>(3.3V)"]
    
    %% Representación del Bus Centralizado
    subgraph Bus ["SALLI Power & Communication Bus"]
        direction LR
        Lines["Power Rails & Signal Traces"]
    end

    %% Módulos de Destino (PCBs)
    Head["HeadModule<br>(Master Processing)"]
    Osc["Oscilatory<br>(Spine Segment)"]
    Legs["Legs_Module<br>(High-Current Driver)"]

    %% Conexiones e Interconexión Eléctrica
    Battery ==>|Raw VCC| RegServo
    Battery -->|Raw VCC| RegLogic
    
    RegServo ==>|High-Current Servo VCC| Lines
    RegLogic -->|Isolated Clean 3.3V| Lines

    Lines ==> Head
    Lines ==> Osc
    Lines ==> Legs

    %% Estilos de Ingeniería Avanzada (Sin Emojis)
    style Battery fill:#1a1a1a,stroke:#bf616a,stroke-width:2px,color:#fff
    style RegServo fill:#2d2d2d,stroke:#d08770,stroke-width:1px,color:#fff
    style RegLogic fill:#2d2d2d,stroke:#ebcb8b,stroke-width:1px,color:#fff
    style Bus fill:#232831,stroke:#81a1c1,stroke-width:2px,color:#fff
    style Lines fill:#3b4252,stroke:#88c0d0,stroke-width:1px,color:#fff
    style Head fill:#1a1a1a,stroke:#4c566a,stroke-width:1px,color:#fff
    style Osc fill:#1a1a1a,stroke:#4c566a,stroke-width:1px,color:#fff
    style Legs fill:#1a1a1a,stroke:#4c566a,stroke-width:1px,color:#fff
    
    %% Definición de grosores de línea para diferenciar potencia de lógica
    linkStyle 0 stroke:#bf616a,stroke-width:3px;
    linkStyle 1 stroke:#ebcb8b,stroke-width:1px;
    linkStyle 2 stroke:#d08770,stroke-width:3px;
    linkStyle 3 stroke:#ebcb8b,stroke-width:1px;
```

---

## Board Subsystems & Responsibilities

The electrical system is divided into four main board profiles:

### 1. `HeadModule` (Master Processing PCB)

The central board of the robot, acting as SALLI's head controller.

* **MCU Support:** Integrates the footprint for the **ESP32-C3 Mini** board.
* **Power Filtering:** Features heavy ceramic and electrolytic capacitor banks to filter out high-frequency noise induced by servo inductive kickbacks.
* **Sensor Hub:** Routes dedicated pins for IMUs (Inertial Measurement Units for tilt and balance detection) and external range sensors.

### 2. `Oscilatory` (Spine Segment PCB)

These are passive/semi-active distribution boards designed to be chain-linked together.

* **The SALLI Bus:** Passes power (VCC and GND) and communication channels downstream to consecutive modules.
* **Servo Tap:** Provides local, filtered power connectors for the local spinal deflection servo, keeping cabling lengths under $20\text{ mm}$.

### 3. `Legs_Module` (High-Current Driver Board)

Because the limbs support the entire weight of the robot and drive forward crawling forces, they demand significant active currents.

* **High-Current Traces:** Features wide copper traces capable of handling sustained currents of up to $3\text{ A}$ during crawling cycles.
* **Independent Power Regulation:** Standardizes opto-couplers or isolation resistors to prevent sudden physical motor stalls from corrupting the main microcontroller's logical operations.

### 4. `Camera` (Vision Expansion Board)

An optional expansion PCB tailored to hold camera modules (such as ESP32-CAM or specialized small SPI cameras) to enable visual-spatial telemetry.

---

## Design Guidelines

* **Trace Width Selection:** * Power paths ($VCC\_SERVO$, $GND$) are set to a minimum of `1.5 mm` width to minimize resistance and prevent thermal stress under heavy load.
* Logic lines ($TX$, $RX$, $PWM$) are kept at standard `0.254 mm` traces.


* **Decoupling Strategy:** Each module places a `100uF` electrolytic capacitor directly in parallel with the local servo power terminal, supplemented by a standard `0.1uF` ceramic capacitor close to the logic rails to handle high-frequency voltage ripples.
* **Standardized Pin Headers:** Connectors use standard, highly accessible, polarized headers (like JST-XH or XT30/XT60 for power entry) to ensure mistake-proof assembly by students.