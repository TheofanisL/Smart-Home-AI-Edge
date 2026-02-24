import argparse
import sys
import time
import cv2
import RPi.GPIO as GPIO
from tflite_support.task import core
from tflite_support.task import processor
from tflite_support.task import vision
import utils
import threading
import pygame
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from flask import Flask, render_template, request, Response
import os
import json
import requests

app = Flask(__name__)

# Define a global variable to store LED configuration
current_led_configuration = '1'
config_lock = threading.Lock()
servo_allowed = False
servo_rotation_duration = 90  # degrees

# Initialize pygame
pygame.init()
pygame.display.set_mode((200, 200))


Settings = {
   1 : {'name' : 'Car Light 1', 'state' : False},
   2 : {'name' : 'Car Light 2', 'state' : False},
   3 : {'name' : 'Person Light', 'state' : False},
   4 : {'name' : 'Door', 'state' : False},
   }
   
TimeSettings = {
   1 : {'name' : 'Light On Time', 'key': 'lightontime', 'value' : "20:30"},
   2 : {'name' : 'Light Off Time', 'key': 'lightofftime', 'value' : "19:15"}
   }
   

def SlackAlert(Message):
    Success = False
    SlackURL = os.environ.get('SLACK_WEBHOOK_URL')
    Content = {"text": "*ALERT: * " + Message}
    try:
        Response = requests.post(SlackURL, json.dumps(Content), timeout = 1)
        if Response.status_code == 200:
            Success = True
        else:
            Success = False
    except:
        Success = False
    return Success


def gen():
    i = 0
    while True:
        images = get_all_images()
        image_name = images[i]
        im = open('images/' + image_name, 'rb').read()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + im + b'\r\n')
        i += 1
        if i >= len(images):
            i = 0
        time.sleep(2)


def get_all_images():
    image_folder = 'images'
    images = [img for img in os.listdir(image_folder)
              if img.endswith(".jpg") or
              img.endswith(".jpeg") or
              img.endswith("png")]
    if len(images) > 1:
        images.remove("No-image-found.jpg")
    #print(images)
    return images


@app.route('/slideshow')
def slideshow():
    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/')
def index():
    templateData = {'Settings' : Settings,
                    'TimeSettings' : TimeSettings
                    }
    return render_template('main.html', **templateData)

@app.route("/<changePin>/<action>")
def action(changePin, action):
   changePin = int(changePin)
   deviceName = Settings[changePin]['name']
   # If the action part of the URL is "on," execute the code indented below:
   if action == "on":
      Settings[changePin]["state"] = True
      # Save the status message to be passed into the template:
      message = "Turned " + deviceName + " on."
   if action == "off":
      Settings[changePin]["state"] = False
      message = "Turned " + deviceName + " off."
   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'Settings' : Settings,
      'TimeSettings': TimeSettings
   }
   print(Settings, flush = True)
   return render_template('mainRedirect.html', **templateData)

@app.route("/set", methods = ["GET"])
def set():
    args = request.args.to_dict()
    if "lightontime" in args.keys():
        TimeSettings[1]["value"] = args["lightontime"]
    elif "lightofftime" in args.keys():
        TimeSettings[2]["value"] = args["lightofftime"]
    print(args, flush = True)
    print(TimeSettings, flush = True)
    templateData = {
      'Settings' : Settings,
      'TimeSettings': TimeSettings
    }
    return render_template('mainRedirect.html', **templateData)

def start_flask_app():
    app.run(host='0.0.0.0')

# Function to monitor key presses and update LED configuration
def update_led_configuration_on_keypress():
    global current_led_configuration
    while True:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_KP1:
                    current_led_configuration = '1'
                    Settings[1]['state'] = True
                    print(Settings)
                    print("Car light 1 will light up!")
                elif event.key == pygame.K_KP2:
                    current_led_configuration = '2'
                    print("Car light 2 will light up!")
                elif event.key == pygame.K_KP3:  # For '1,2'
                    current_led_configuration = '1,2'
                    print("Car light 1 and 2 will light up!")
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    GPIO.cleanup()
                    sys.exit()
                else:
                    pass  # Handle other keys if needed
            time.sleep(0.01)  # Sleep briefly to avoid continuous checking

def setup_led(pin):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)

def setup_servo(pin):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    servo = GPIO.PWM(pin, 50)  # Set PWM frequency to 50Hz
    servo.start(0)  # Start servo at 0 degrees
    return servo

def rotate_servo(servo, angle, servo_pin):
    duty = angle / 18 + 2
    GPIO.output(servo_pin, True)
    servo.ChangeDutyCycle(duty)
    time.sleep(1)
    GPIO.output(servo_pin, False)
    servo.ChangeDutyCycle(0)

def update_servo_configuration():
    global servo_allowed
    while True:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_o:
                    servo_allowed = True
                    print("Servo rotation is allowed!")
                elif event.key == pygame.K_l:
                    servo_allowed = False
                    print("Servo rotation is not allowed!")
            time.sleep(0.01)

# Function to authenticate and upload files to Google Drive
def upload_to_drive_async(file_path, folder_id='1DyGNMEuZ6Kv04DjOzcutEU0BsG81119a'):
    def upload_func():
        try:
            gauth = GoogleAuth()
            gauth.LoadCredentialsFile("mycreds.txt")

            if gauth.credentials is None:
                gauth.LocalWebserverAuth()
            elif gauth.access_token_expired:
                gauth.Refresh()
            else:
                gauth.Authorize()

            gauth.SaveCredentialsFile("mycreds.txt")

            drive = GoogleDrive(gauth)
            file = drive.CreateFile({'title': file_path.split('/')[-1], 'parents': [{'id': folder_id}]})
            file.SetContentFile(file_path)
            file.Upload()
            print(f'File {file_path} uploaded to Google Drive folder {folder_id}')
        except Exception as e:
            print(f'Error uploading file to Google Drive: {e}')
           
   
    upload_thread = threading.Thread(target=upload_func)
    upload_thread.start()
           
def run(model: str, camera_id: int, width: int, height: int, num_threads: int,
        enable_edgetpu: bool, i: int, led_pin_car: int, led_pin_person: int, led_pin_additional: int,
        activate_both_leds: bool, servo, servo_pin, lights_on_time, lights_off_time) -> None:
    global current_led_configuration, servo_allowed, lights_on      
    # Variables to calculate FPS
    counter, fps = 0, 0
    start_time = time.time()

    # Start capturing video input from the camera
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Visualization parameters
    row_size = 20  # pixels
    left_margin = 24  # pixels
    text_color = (0, 0, 255)  # red
    font_size = 1
    font_thickness = 1
    fps_avg_frame_count = 10

    # Initialize the object detection model
    base_options = core.BaseOptions(
        file_name=model, use_coral=enable_edgetpu, num_threads=num_threads)
    detection_options = processor.DetectionOptions(
        max_results=3, score_threshold=0.3, category_name_allowlist=["car", "person"])
    options = vision.ObjectDetectorOptions(
        base_options=base_options, detection_options=detection_options)
    detector = vision.ObjectDetector.create_from_options(options)

    # Initialize a flag to control photo capture
    should_capture_photo = False

    # Time of the last photo capture
    last_capture_time = time.time()

    # Time when car is no longer detected
    last_car_detection_time = None

    # LED activation events
    led_event_car = threading.Event()
    led_event_car.set()  # Initialize as set to keep the LED off during startup

    led_event_person = threading.Event()
    led_event_person.set()  # Initialize as set to keep the LED off during startup

    led_event_additional = threading.Event()
    led_event_additional.set()  # Initialize as set to keep the additional LED off during startup

    # Function to control LED for person detection
    def control_led_person():
        while True:
            led_event_person.wait()
            GPIO.output(led_pin_person, GPIO.HIGH)
            time.sleep(10)
            GPIO.output(led_pin_person, GPIO.LOW)
            led_event_person.clear()

    # Start the LED control thread for person detection
    led_thread_person = threading.Thread(target=control_led_person)
    led_thread_person.daemon = True  # Set as daemon to exit when the main thread exits
    led_thread_person.start()

    # Function to control LED for car detection
    def control_led_car():
        while True:
            led_event_car.wait()
            GPIO.output(led_pin_car, GPIO.HIGH)
            time.sleep(10)
            GPIO.output(led_pin_car, GPIO.LOW)
            led_event_car.clear()

    # Start the LED control thread for car detection
    led_thread_car = threading.Thread(target=control_led_car)
    led_thread_car.daemon = True  # Set as daemon to exit when the main thread exits
    led_thread_car.start()
   
    # Function to control additional LED
    def control_led_additional():
        while True:
            led_event_additional.wait()
            GPIO.output(led_pin_additional, GPIO.HIGH)
            time.sleep(10)
            GPIO.output(led_pin_additional, GPIO.LOW)
            led_event_additional.clear()

    # Start the LED control thread for additional LED
    led_thread_additional = threading.Thread(target=control_led_additional)
    led_thread_additional.daemon = True  # Set as daemon to exit when the main thread exits
    led_thread_additional.start()

    # Event to control the duration the servo stays rotated after a car is detected
    car_not_detected_event = threading.Event()
    car_not_detected_event.set()  # Initialize as set to start with no car detected

    def control_servo_rotation():
        while True:
            if car_not_detected_event.is_set():
                rotate_servo(servo, 0, servo_pin)  # Rotate back to neutral
                time.sleep(10)  # Wait for 10 seconds before next rotation
            else:
                rotate_servo(servo, 90, servo_pin)  # Rotate 90 degrees
                time.sleep(0.1)  # Sleep briefly to reduce CPU usage

    # Start the thread to control servo rotation
    servo_rotation_thread = threading.Thread(target=control_servo_rotation)
    servo_rotation_thread.daemon = True
    servo_rotation_thread.start()
   
    lights_on = False
   
    # Continuously capture images from the camera and run inference
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            sys.exit('ERROR: Unable to read from the webcam. Please verify your webcam settings.')
       
        counter += 1
        # Convert the image from BGR to RGB as required by the TFLite model.
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Create a TensorImage object from the RGB image.
        input_tensor = vision.TensorImage.create_from_array(rgb_image)

        lights_on_time_struct=TimeSettings[1]['value']
        lights_off_time_struct=TimeSettings[2]['value']

        # Run object detection estimation using the model.
        detection_result = detector.detect(input_tensor)
        nowtime = time.strftime("%H:%M", time.localtime())
        nowtime_struct = time.strptime(nowtime, "%H:%M")
        lights_on_time = time.strptime(lights_on_time_struct, "%H:%M")
        lights_off_time = time.strptime(lights_off_time_struct, "%H:%M")
        # Check if the time is right for lights
        if lights_off_time <= nowtime_struct <= lights_on_time:
           lights_on = False
        else:
            lights_on = True

        # Take a photo when a car or person is detected
        if detection_result.detections and detection_result.detections[0].categories:
            for category in detection_result.detections[0].categories:
                if category.category_name in ['car', 'person'] and category.score > 0.3:
                    # Check if 10 seconds have passed since the last capture
                    if time.time() - last_capture_time >= 10:
                        # Generate file name with label, date, and time
                        label = category.category_name
                        current_time = time.strftime("%d-%m-%Y, %H:%M:%S", time.localtime())
                        file_name = f"{label} - {current_time}.jpg"
                        file_path = f'/home/pi/Desktop/New/images/{file_name}'

                        cv2.imwrite(file_path, image)
                        print(f'A photo has been taken: {file_name}')
                        #upload_to_drive_async(file_path)  # Upload to Google Drive folder
                        i += 1  # Increment the image counter
                        last_capture_time = time.time()  # Update the last capture time
                        if label == 'car':
                            SlackAlert("Car Detected\n>*Certainty:* " + str(round(category.score * 100, 1)) + "%\n>*Control:* http://raspberrypi.local:5000")
                            if (Settings[1]['state'] == True) and lights_on:                
                            #if '1' in current_led_configuration and lights_on:
                                led_event_car.set()
                            if (Settings[2]['state'] == True) and lights_on:
                            #if '2' in current_led_configuration and lights_on:
                                led_event_additional.set()
                            #if '1,2' in current_led_configuration and lights_on:
                            #   led_event_car.set()
                            #  led_event_additional.set()
                            if (Settings[4]['state'] == True):
                                car_not_detected_event.clear()
                        elif label == 'person':
                            if (Settings[3]['state'] == True) and lights_on:
                                led_event_person.set()
                           
                        # Update the last car or person detection time
                        if label == 'car':
                            last_car_detection_time = time.time()
                        elif label == 'person':
                            last_person_detection_time = time.time()

        # Check if a car is no longer detected and 10 seconds have passed
        if last_car_detection_time and time.time() - last_car_detection_time >= 10:
            car_not_detected_event.set()

        # Draw keypoints and edges on the input image
        image = utils.visualize(image, detection_result)

        # Calculate the FPS
        if counter % fps_avg_frame_count == 0:
            end_time = time.time()
            fps = fps_avg_frame_count / (end_time - start_time)
            start_time = time.time()

        # Show the FPS
        fps_text = 'FPS = {:.1f}'.format(fps)
        text_location = (left_margin, row_size)
        cv2.putText(image, fps_text, text_location, cv2.FONT_HERSHEY_PLAIN,
                    font_size, text_color, font_thickness)

        # Stop the program if the ESC key is pressed.
        if cv2.waitKey(1) == 27:
            break
        cv2.imshow('object_detector', image)
    cap.release()
    cv2.destroyAllWindows()
    GPIO.cleanup()  # Clean up the GPIO settings

def main():
    pygame.init()
    pygame.event.set_grab(True)  # Grab the mouse and keyboard input
   
    # Start the update_led_configuration_on_keypress() in a separate thread
    led_keypress_thread = threading.Thread(target=update_led_configuration_on_keypress)
    led_keypress_thread.daemon = True  # Set as daemon to exit when the main thread exits
    led_keypress_thread.start()
   
    servo_keypress_thread = threading.Thread(target=update_servo_configuration)
    servo_keypress_thread.daemon = True
    servo_keypress_thread.start()
   
    # Setup and initialize servo
    servo_pin = 2  # GPIO pin 2
    servo = setup_servo(servo_pin)
   
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--model',
        help='Path of the object detection model.',
        required=False,
        default='efficientdet_lite0.tflite')
    parser.add_argument(
        '--cameraId', help='Id of camera.', required=False, type=int, default=0)
    parser.add_argument(
        '--frameWidth',
        help='Width of the frame to capture from the camera.',
        required=False, type=int, default=640)
    parser.add_argument(
        '--frameHeight',
        help='Height of the frame to capture from the camera.',
        required=False, type=int, default=480)
    parser.add_argument(
        '--numThreads',
        help='Number of CPU threads to run the model.',
        required=False, type=int, default=4)
    parser.add_argument(
        '--enableEdgeTPU',
        help='Whether to run the model on EdgeTPU.',
        action='store_true', required=False, default=False)
    parser.add_argument(
        '--i', help='Number of the image.', required=False, type=int, default=0)
    parser.add_argument(
        '--ledPinCar',
        help='GPIO pin number connected to the LED for car detection.',
        required=False, type=int, default=17)  # Default to GPIO pin 17
    parser.add_argument(
        '--ledPinPerson',
        help='GPIO pin number connected to the LED for person detection.',
        required=False, type=int, default=27)  # Default to GPIO pin 27
    parser.add_argument(
        '--ledPinAdditional',
        help='GPIO pin number connected to the additional LED for car detection.',
        required=False, type=int, default=22)  # Default to GPIO pin 22
    parser.add_argument(
        '--activateBothLEDs',
        help='Activate both LEDs when a car is detected.',
        action='store_true', required=False, default=False)
    # New arguments for setting the time range
    parser.add_argument(
        '--lightsOnTime',
        help='Time when the LEDs are allowed to turn on.',
        required=False, type=str, default='9:00')
    parser.add_argument(
        '--lightsOffTime',
        help='Time when the LEDs are not allowed to turn on.',
        required=False, type=str, default='06:00')

    args = parser.parse_args()

    # Parse the time strings to datetime objects
    lights_on_time = time.strptime(args.lightsOnTime, '%H:%M')
    lights_off_time = time.strptime(args.lightsOffTime, '%H:%M')

    setup_led(args.ledPinCar)  # Setup the LED for car detection
    setup_led(args.ledPinPerson)  # Setup the LED for person detection
    setup_led(args.ledPinAdditional)  # Setup the additional LED for car detection

    run(args.model, int(args.cameraId), args.frameWidth, args.frameHeight,
        int(args.numThreads), bool(args.enableEdgeTPU), int(args.i),
        args.ledPinCar, args.ledPinPerson, args.ledPinAdditional, args.activateBothLEDs, servo, servo_pin, lights_on_time, lights_off_time)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=start_flask_app)
    flask_thread.start()
    main()