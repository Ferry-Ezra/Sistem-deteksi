import os
import cv2
import numpy as np
from ultralytics import YOLO
import torch

print("Torch CUDA Available:", torch.cuda.is_available())
print("Device Count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("Device Name:", torch.cuda.get_device_name(0))

model_path = os.path.join('model', 'best.pt')
print("Model path exists:", os.path.exists(model_path))

try:
    yolo_model = YOLO(model_path)
    print("YOLO Loaded successfully")
except Exception as e:
    print("Failed to load YOLO:", e)
    exit(1)

# Create a blank image
img = np.zeros((320, 320, 3), dtype=np.uint8)

print("\n--- Running with device=0 ---")
try:
    results = yolo_model.predict(img, device=0, half=False, verbose=True)
    print("GPU inference success! Device of output boxes:", results[0].boxes.xyxy.device)
except Exception as e:
    print("GPU inference FAILED:", e)

print("\n--- Running with device='cuda' ---")
try:
    results = yolo_model.predict(img, device='cuda', half=False, verbose=True)
    print("CUDA inference success! Device of output boxes:", results[0].boxes.xyxy.device)
except Exception as e:
    print("CUDA inference FAILED:", e)
