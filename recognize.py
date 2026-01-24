import cv2
import pickle
import requests
import time

# --- CẤU HÌNH ---
ESP32_IP = "192.168.4.1" # IP mặc định khi ESP32 phát WiFi
ESP32_URL = f"http://{ESP32_IP}/face_toggle"
COOLDOWN_TIME = 5 # 5 giây sau mỗi lần mở mới nhận diện tiếp
CONFIDENCE_THRESHOLD = 80 # NGƯỠNG TIN CẬY: Càng thấp càng chắc chắn. Mặc định: 80


def face_recognition():
    # Load các file dữ liệu
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    try:
        recognizer.read("trainner.yml")
        with open("labels.pickle", 'rb') as f:
            og_labels = pickle.load(f)
            labels = {v: k for k, v in og_labels.items()}
    except:
        print("LỖI: Chưa có dữ liệu khuôn mặt. Hãy chạy auto_train.py trước!")
        return

    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0)
    last_action_time = 0

    print("Hệ thống nhận diện đang chạy... Nhấn 'q' để thoát.")

    while True:
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            id_, conf = recognizer.predict(roi_gray)

            # Độ tin cậy (conf) càng thấp càng chính xác, thường < 80 là ổn
            if conf <= CONFIDENCE_THRESHOLD:
                name = labels[id_]
                color = (0, 255, 0) # Xanh lá nếu đúng
                
                # Kiểm tra thời gian chờ (cooldown)
                if time.time() - last_action_time > COOLDOWN_TIME:
                    print(f"Chào {name}! Đang mở cửa...")
                    try:
                        requests.post(ESP32_URL, timeout=2)
                        last_action_time = time.time()
                    except:
                        print("Không kết nối được tới ESP32!")
            else:
                name = "Unknown"
                color = (0, 0, 255) # Đỏ nếu lạ

            cv2.putText(frame, f"{name} ({int(conf)})", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

        cv2.imshow('Face Recognition System', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    face_recognition()