import cv2
import os
import numpy as np
import pickle
import serial
import time

# --- CẤU HÌNH ---
SERIAL_PORT = 'COM3'  # Thay đổi thành cổng COM của ESP32 (ví dụ: /dev/ttyUSB0 trên Mac/Linux)
BAUD_RATE = 115200
FACE_DATA_DIR = "images" # Thư mục lưu ảnh mặt

def capture_faces(name):
    cam = cv2.VideoCapture(0)
    detector = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    
    # Tạo thư mục cho người mới nếu chưa có
    path = os.path.join(FACE_DATA_DIR, name)
    if not os.path.exists(path):
        os.makedirs(path)

    print(f"Bắt đầu lấy mẫu khuôn mặt cho: {name}. Hãy nhìn vào camera!")
    count = 0
    while True:
        ret, img = cam.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            count += 1
            # Lưu ảnh vào thư mục riêng của người đó
            file_path = os.path.join(path, f"{count}.jpg")
            cv2.imwrite(file_path, gray[y:y+h, x:x+w])
            cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.imshow('Capturing Faces', img)

        if cv2.waitKey(1) & 0xFF == ord('q') or count >= 50:
            break
            
    cam.release()
    cv2.destroyAllWindows()
    print(f"Đã xong! Đã lưu {count} ảnh cho {name}.")
    train_faces() # Tự động train sau khi chụp

def train_faces():
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    detector = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
    
    current_id = 0
    label_ids = {}
    y_labels = []
    x_train = []

    for root, dirs, files in os.walk(FACE_DATA_DIR):
        for file in files:
            if file.endswith("png") or file.endswith("jpg"):
                path = os.path.join(root, file)
                label = os.path.basename(root).replace(" ", "-").lower()
                
                if not label in label_ids:
                    label_ids[label] = current_id
                    current_id += 1
                id_ = label_ids[label]

                pil_image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                image_array = np.array(pil_image, "uint8")
                faces = detector.detectMultiScale(image_array, scaleFactor=1.1, minNeighbors=5)

                for (x,y,w,h) in faces:
                    roi = image_array[y:y+h, x:x+w]
                    x_train.append(roi)
                    y_labels.append(id_)

    with open("labels.pickle", 'wb') as f:
        pickle.dump(label_ids, f)

    recognizer.train(x_train, np.array(y_labels))
    recognizer.save("trainner.yml")
    print("Hệ thống đã cập nhật dữ liệu khuôn mặt mới thành công!")

# --- CHƯƠNG TRÌNH CHÍNH ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Đang kết nối tới ESP32 trên cổng {SERIAL_PORT}...")
    time.sleep(2)
    
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8').strip()
            if line.startswith("LEARNFACE:"):
                name = line.split(":")[1]
                capture_faces(name)
                print("Đã sẵn sàng nhận diện tiếp!")
except Exception as e:
    print(f"Lỗi: {e}. Kiểm tra cổng COM hoặc dây cáp USB.")