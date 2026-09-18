# Hand Gesture Music Player - DUAL HAND MODE (Minimalist UI)
# pip install opencv-python mediapipe pygame

import cv2
import pygame
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import urllib.request
import os

# ==================== DOWNLOAD MODEL ====================

MODEL_PATH = "hand_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

if not os.path.exists(MODEL_PATH):
    print(f"[INFO] Downloading hand landmarker model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print(f"[INFO] Model downloaded: {MODEL_PATH}")

# ==================== SETUP ====================

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=2,
    min_hand_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
detector = vision.HandLandmarker.create_from_options(options)

# Hand landmark indices
THUMB_TIP, THUMB_IP, THUMB_MCP = 4, 3, 2
INDEX_TIP, INDEX_PIP = 8, 6
MIDDLE_TIP, MIDDLE_PIP = 12, 10
RING_TIP, RING_PIP = 16, 14
PINKY_TIP, PINKY_PIP = 20, 18
WRIST = 0

# Initialize Pygame Mixer
pygame.mixer.init()
MUSIC_FILE = "music.mp3"
try:
    pygame.mixer.music.load(MUSIC_FILE)
    print(f"[INFO] Loaded: {MUSIC_FILE}")
except pygame.error as e:
    print(f"[ERROR] Could not load '{MUSIC_FILE}': {e}")

# Initialize Webcam
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

is_playing = False


# ==================== GESTURE DETECTION ====================

def is_finger_extended(landmarks, tip_idx, pip_idx):
    return landmarks[tip_idx].y < landmarks[pip_idx].y


def is_thumb_extended(landmarks):
    thumb_tip = landmarks[THUMB_TIP]
    thumb_mcp = landmarks[THUMB_MCP]
    thumb_ip = landmarks[THUMB_IP]
    return abs(thumb_tip.x - thumb_mcp.x) > abs(thumb_ip.x - thumb_mcp.x)


def detect_trigger_gesture(landmarks):
    return (is_thumb_extended(landmarks) and
            is_finger_extended(landmarks, INDEX_TIP, INDEX_PIP) and
            is_finger_extended(landmarks, MIDDLE_TIP, MIDDLE_PIP) and
            not is_finger_extended(landmarks, RING_TIP, RING_PIP) and
            not is_finger_extended(landmarks, PINKY_TIP, PINKY_PIP))


def draw_landmarks(image, landmarks, width, height, color):
    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
        (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
        (0, 17), (17, 18), (18, 19), (19, 20), (5, 9), (9, 13), (13, 17)
    ]
    points = [(int(lm.x * width), int(lm.y * height)) for lm in landmarks]
    for p in points:
        cv2.circle(image, p, 3, color, -1)
    for s, e in connections:
        cv2.line(image, points[s], points[e], color, 1)


# ==================== MAIN LOOP ====================

print("[INFO] Dual Hand Gesture Music Player")
print("[INFO] Press 'q' to quit")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
    
    frame = cv2.flip(frame, 1)
    height, width = frame.shape[:2]
    
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    results = detector.detect(mp_image)
    
    num_hands = len(results.hand_landmarks) if results.hand_landmarks else 0
    both_hands_gesture = False
    status = "Waiting"
    
    if num_hands == 2:
        gesture_results = []
        for hand_landmarks in results.hand_landmarks:
            gesture_ok = detect_trigger_gesture(hand_landmarks)
            gesture_results.append(gesture_ok)
            color = (0, 200, 0) if gesture_ok else (0, 200, 200)
            draw_landmarks(frame, hand_landmarks, width, height, color)
        
        if all(gesture_results):
            both_hands_gesture = True
            status = "Playing"
        else:
            status = "Gesture?"
    
    elif num_hands == 1:
        hand_landmarks = results.hand_landmarks[0]
        gesture_ok = detect_trigger_gesture(hand_landmarks)
        color = (0, 200, 0) if gesture_ok else (0, 200, 200)
        draw_landmarks(frame, hand_landmarks, width, height, color)
        status = "1 Hand"
    
    # ==================== MUSIC CONTROL ====================
    
    if both_hands_gesture:
        if not is_playing:
            try:
                pygame.mixer.music.play()
                is_playing = True
            except:
                pass
    else:
        if is_playing:
            pygame.mixer.music.stop()
            pygame.mixer.music.rewind()
            is_playing = False
    
    # ==================== MINIMALIST UI ====================
    
    # Small status text in top-left corner
    cv2.putText(frame, f"{status} | Hands: {num_hands}/2", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    
    # Resize to 1000x700 (10:7 aspect ratio)
    display_frame = cv2.resize(frame, (1000, 700))
    cv2.imshow("Gesture Player", display_frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ==================== CLEANUP ====================

pygame.mixer.music.stop()
pygame.mixer.quit()
cap.release()
cv2.destroyAllWindows()
detector.close()
