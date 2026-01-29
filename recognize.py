import cv2
import pickle
import time
import serial # Thư viện để giao tiếp với ESP32 qua dây cáp

# --- CẤU HÌNH ---
# Hãy đổi 'COM3' thành cổng COM thực tế của bạn (xem trong Device Manager)
SERIAL_PORT = 'COM4' 
BAUD_RATE = 115200

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Đã kết nối với ESP32 qua cổng {SERIAL_PORT}")
    time.sleep(2) # Chờ 2s để ESP32 khởi động
except Exception as e:
    print(f"LỖI: Không thể kết nối cổng {SERIAL_PORT}. Hãy kiểm tra dây cáp!")
    print(f"Chi tiết lỗi: {e}")
    ser = None

def face_recognition():
    # Load dữ liệu đã train
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    try:
        recognizer.read("trainner.yml")
        with open("labels.pickle", 'rb') as f:
            og_labels = pickle.load(f)
            labels = {v: k for k, v in og_labels.items()}
    except:
        print("LỖI: Chưa có dữ liệu khuôn mặt. Hãy chạy auto_train.py trước!")
        return

    # Tải bộ phát hiện khuôn mặt
    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
    
    # Mở Camera (Thêm cv2.CAP_DSHOW để chạy mượt hơn trên Windows)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    last_action_time = 0
    COOLDOWN_TIME = 5 # Thời gian nghỉ giữa 2 lần mở cửa

    print("Hệ thống nhận diện đang chạy... Nhấn 'q' để thoát.")

    while True:
        ret, frame = cap.read()
        if not ret: continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            id_, conf = recognizer.predict(roi_gray)

            # --- SỬA LỖI QUAN TRỌNG Ở ĐÂY ---
            # Chỉ mở nếu độ sai số < 50 (Càng thấp càng chính xác)
            # Nếu để 80, nó sẽ nhận diện nhầm người lạ thành người quen
            if conf < 65: 
                name = labels[id_]
                color = (0, 255, 0) # Xanh lá (Đúng)
                
                # Hiển thị độ tin cậy ra màn hình để bạn theo dõi (100 - conf)
                confidence_text = f"{round(100 - conf)}%"

                # Kiểm tra thời gian chờ để tránh spam lệnh mở cửa
                if time.time() - last_action_time > COOLDOWN_TIME:
                    print(f"CHÍNH XÁC! Chào {name} (Độ tin cậy: {confidence_text}). Đang gửi lệnh mở cửa...")
                    
                    if ser is not None:
                        # Gửi lệnh OPEN_DOOR qua dây cáp cho ESP32
                        ser.write(b"OPEN_DOOR\n") 
                    else:
                        print("Lỗi: Không có kết nối Serial để gửi lệnh.")
                        
                    last_action_time = time.time() # Reset đồng hồ
            
            else:
                # Nếu sai số > 50 -> Coi là NGƯỜI LẠ (Unknown)
                name = "Unknown"
                color = (0, 0, 255) # Đỏ (Sai)
                confidence_text = f"Sai so: {round(conf)}"

            # Vẽ khung và tên lên màn hình
            cv2.putText(frame, f"{name}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(frame, confidence_text, (x, y+h+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)

        cv2.imshow('Face Recognition System', frame)
        
        # Nhấn 'q' để thoát
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if ser: ser.close()

if __name__ == "__main__":
    face_recognition()