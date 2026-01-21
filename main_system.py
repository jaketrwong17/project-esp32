import cv2
import serial
import os
import shutil
import pickle
import numpy as np
import requests
import time

# --- CẤU HÌNH ---
SERIAL_PORT = 'COM3'  # Sửa đúng cổng COM của bạn
ESP32_URL = "http://192.168.4.1/face_toggle"
FACE_DATA_DIR = "images"
XML_PATH = "haarcascade_frontalface_default.xml"

if not os.path.exists(FACE_DATA_DIR): os.makedirs(FACE_DATA_DIR)

try:
    ser = serial.Serial(SERIAL_PORT, 115200, timeout=1)
    time.sleep(2)
except Exception as e:
    print(f"KHÔNG THỂ KẾT NỐI CỔNG {SERIAL_PORT}: {e}")

def sync_list():
    folders = [f for f in os.listdir(FACE_DATA_DIR) if os.path.isdir(os.path.join(FACE_DATA_DIR, f))]
    ser.write(f"LIST:{','.join(folders)}\n".encode())

def train_system():
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    detector = cv2.CascadeClassifier(XML_PATH)
    label_ids, y_labels, x_train = {}, [], []
    current_id = 0

    for root, dirs, files in os.walk(FACE_DATA_DIR):
        for file in files:
            if file.lower().endswith(("jpg", "png")):
                path = os.path.join(root, file)
                label = os.path.basename(root).lower()
                if label not in label_ids:
                    label_ids[label] = current_id
                    current_id += 1
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                faces = detector.detectMultiScale(img, 1.1, 5)
                for (x,y,w,h) in faces:
                    x_train.append(img[y:y+h, x:x+w])
                    y_labels.append(label_ids[label])

    # Sửa lỗi Empty training data was given
    if len(x_train) > 0:
        with open("labels.pickle", 'wb') as f: pickle.dump(label_ids, f)
        recognizer.train(x_train, np.array(y_labels))
        recognizer.save("trainner.yml")
        print("Huấn luyện thành công.")
    else:
        if os.path.exists("trainner.yml"): os.remove("trainner.yml")
        print("Thư mục ảnh trống, không có dữ liệu để huấn luyện.")
    sync_list()

def capture_face(name):
    cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier(XML_PATH)
    path = os.path.join(FACE_DATA_DIR, name)
    if not os.path.exists(path): os.makedirs(path)
    count = 0
    print(f"Bắt đầu lấy mẫu cho {name}...")
    while count < 50:
        ret, img = cam.read()
        if not ret: continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            count += 1
            cv2.imwrite(os.path.join(path, f"{count}.jpg"), gray[y:y+h, x:x+w])
            cv2.rectangle(img, (x,y), (x+w, y+h), (255,0,0), 2)
        cv2.imshow("Lay mau mat...", img)
        if cv2.waitKey(1) == ord('q'): break
    cam.release()
    cv2.destroyAllWindows()
    train_system()

def run_recognition():
    if not os.path.exists("trainner.yml"): 
        print("Chưa có dữ liệu khuôn mặt! Hãy thêm mặt trước.")
        return
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read("trainner.yml")
    with open("labels.pickle", 'rb') as f: labels = {v: k for k, v in pickle.load(f).items()}
    cap, detector = cv2.VideoCapture(0), cv2.CascadeClassifier(XML_PATH)
    start = time.time()
    while time.time() - start < 15:
        ret, frame = cap.read()
        if not ret: continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)
        for (x,y,w,h) in faces:
            id_, conf = recognizer.predict(gray[y:y+h, x:x+w])
            if conf <= 75:
                print(f"Mở cửa cho: {labels[id_]}")
                try: requests.post(ESP32_URL, timeout=1)
                except: pass
                cap.release(); cv2.destroyAllWindows(); return
        cv2.imshow("Nhan dien...", frame)
        if cv2.waitKey(1) == ord('q'): break
    cap.release()
    cv2.destroyAllWindows()

print("Hệ thống Python khởi động thành công!")
sync_list()
while True:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line == "START_RECOGNITION": run_recognition()
        elif line.startswith("LEARNFACE:"): capture_face(line.split(":")[1])
        elif line.startswith("DELETE_FACE:"):
            target = line.split(":")[1]
            shutil.rmtree(os.path.join(FACE_DATA_DIR, target), ignore_errors=True)
            print(f"Đã xóa khuôn mặt {target}")
            train_system()
    time.sleep(0.1)