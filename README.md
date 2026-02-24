<img width="1471" height="1028" alt="RPi 3" src="https://github.com/user-attachments/assets/578a75f7-1258-4bdc-ab1f-cbcf0938a1b9" />

**Technical System Analysis**
The system acts as a central hub that processes visual data in real time and reacts via hardware and cloud services.

**Artificial Intelligence & Computer Vision**
Model: Using EfficientDet-Lite0 in a TensorFlow Lite environment for high processing speed on Raspberry Pi 3.

Object Detection: The system is configured to specifically recognize the "person" and "car" classes with a confidence threshold of 0.3.

Edge Processing: Processing is done locally, ensuring low latency and privacy protection.

**Web Interface & Cloud Integration**
Flask Web Server: An interactive dashboard that allows:

Manual control of LEDs and Servo (door).

Scheduling of automatic lighting.

Live slideshow of recorded events.

Notifications: Instantly send notifications to Slack Channel with information about the detection certainty rate and a link for remote control.

Cloud Backup: Automatic upload of photos to Google Drive via PyDrive API.

**Hardware Control (IoT)**

Multithreading: Use of multiple threads (threading) to simultaneously execute AI, Flask server and GPIO control.

Actuators:

Servo Motor: Access control (door) with PWM.

LED Indicators: Different channels for human or car detection.

Inputs: Support for keyboard control (Pygame events) for quick settings.
