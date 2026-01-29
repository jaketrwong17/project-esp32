import cv2
import os
import numpy as np
import pickle
import serial
import time
from PIL import Image

# --- CẤU HÌNH ---
SERIAL_PORT = 'COM4'   # Đổi thành cổng COM của bạn nếu khác
BAUD_RATE = 115200
FACE_DATA_DIR = "images" 

# --- HÀM 1: CHỤP ẢNH (Sẽ được gọi khi ESP32 ra lệnh) ---
def capture_faces(name):
    # Tạo thư mục lưu ảnh
    path = os.path.join(FACE_DATA_DIR, name)
    if not os.path.exists(path):
        os.makedirs(path)

    # Bật Camera (Thêm CAP_DSHOW cho Windows)
    print(f"\n[CAMERA] Đang khởi động để chụp cho: {name}...")
    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW) 
    detector = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    
    count = 0
    max_photos = 50 # Số ảnh cần chụp

    print(f"[HƯỚNG DẪN] Hãy nhìn vào Camera và xoay nhẹ các góc mặt...")
    
    while True:
        ret, img = cam.read()
        if not ret: continue

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            count += 1
            # Lưu ảnh
            cv2.imwrite(f"{path}/{count}.jpg", gray[y:y+h, x:x+w])
            # Vẽ khung
            cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.imshow('Dang chup anh...', img)

        # Thoát khi đủ ảnh
        if count >= max_photos:
            print(f"[XONG] Đã chụp đủ {count} ảnh.")
            break
        # Hoặc bấm 'q' để thoát sớm
        if cv2.waitKey(100) & 0xFF == ord('q'):
            break

    cam.release()
    cv2.destroyAllWindows()
    
    # Chụp xong thì Train luôn
    train_faces()

# --- HÀM 2: HUẤN LUYỆN (Train) ---
def train_faces():
    print("\n[TRAIN] Đang huấn luyện lại dữ liệu khuôn mặt...")
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

                pil_image = Image.open(path).convert("L") # Chuyển sang ảnh xám
                image_array = np.array(pil_image, "uint8")
                
                faces = detector.detectMultiScale(image_array)
                for (x,y,w,h) in faces:
                    roi = image_array[y:y+h, x:x+w]
                    x_train.append(roi)
                    y_labels.append(id_)

    with open("labels.pickle", 'wb') as f:
        pickle.dump(label_ids, f)

    recognizer.train(x_train, np.array(y_labels))
    recognizer.save("trainner.yml")
    print("[THÀNH CÔNG] Đã cập nhật file trainner.yml! Hệ thống đã biết người mới.")

# --- CHƯƠNG TRÌNH CHÍNH (LẮNG NGHE ESP32) ---
print(f"--- ĐANG CHỜ LỆNH TỪ ESP32 (CỔNG {SERIAL_PORT}) ---")
print("Bây giờ bạn hãy dùng điện thoại ấn 'THÊM MẶT' để kích hoạt Camera.")

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    
    while True:
        if ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()
                print(f"[DEBUG] ESP32 gửi: {line}")
                
                # Nếu nhận được lệnh LEARNFACE
                if "LEARNFACE" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        name_user = parts[1] # Lấy tên (ví dụ: admin)
                        print(f"\n---> NHẬN LỆNH THÊM MẶT CHO: {name_user}")
                        
                        # Tạm đóng cổng Serial để Camera chạy mượt hơn (tránh xung đột)
                        ser.close() 
                        
                        capture_faces(name_user) # GỌI HÀM CHỤP ẢNH
                        
                        # Mở lại cổng Serial để nghe lệnh tiếp theo
                        ser.open()
                        print("\n--- ĐANG CHỜ LỆNH TIẾP THEO ---")
                    
            except Exception as e:
                print(f"Lỗi xử lý: {e}")
        
        time.sleep(0.1)

except Exception as e:
    print(f"LỖI KẾT NỐI: {e}")
    print("Hãy tắt các cửa sổ Python khác hoặc tắt Arduino IDE rồi thử lại.")