import cv2
import pickle
import time
import serial

# --- CẤU HÌNH ---
SERIAL_PORT = 'COM4'   # Đổi đúng cổng COM của bạn
BAUD_RATE = 115200
CONFIDENCE_THRESHOLD = 50 # Ngưỡng (Càng nhỏ càng khó tính, < 50 là an toàn)
TIMEOUT_CAM = 30          # Camera tự tắt sau 30s nếu không mở được cửa

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print(f"✅ Đã kết nối với ESP32. Đang chờ bạn ấn phím 'A'...")
except:
    print("❌ Lỗi kết nối ESP32! Kiểm tra dây cáp.")
    ser = None

# Hàm này chỉ chạy khi được gọi (khi ấn phím A)
def kich_hoat_camera(recognizer, labels, face_cascade):
    print("\n📷 [CAMERA ĐANG BẬT] Đang quét khuôn mặt...")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    
    start_time = time.time()
    mo_cua_thanh_cong = False

    print("--- BẮT ĐẦU SOI DỮ LIỆU ---") # Bắt đầu in log

    while True:
        # 1. Kiểm tra thời gian chờ (để tiết kiệm điện)
        if time.time() - start_time > TIMEOUT_CAM:
            print("⏰ Hết giờ (30s)! Không thấy ai quen -> Tắt Camera.")
            break

        ret, frame = cap.read()
        if not ret: continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            id_, conf = recognizer.predict(roi_gray)
            name = labels.get(id_, "Unknown")
            conf_val = round(conf)

            # --- ĐÂY LÀ PHẦN BẠN MUỐN (IN CHECK LIÊN TỤC) ---
            print(f"👀 Thấy: {name} | Sai số: {conf_val} | Ngưỡng chặn: {CONFIDENCE_THRESHOLD}")
            # -----------------------------------------------

            # 2. Nếu nhận diện ĐÚNG (Sai số thấp hơn ngưỡng)
            if conf < CONFIDENCE_THRESHOLD:
                print(f"\n🔓 ===> MỞ CỬA CHO: {name} <===")
                
                # Gửi lệnh mở cửa xuống ESP32
                if ser: 
                    ser.write(b"OPEN_DOOR\n")
                    print("📤 Đã gửi lệnh 'OPEN_DOOR' xuống ESP32")
                
                # Hiện thông báo lên màn hình 1 chút cho đẹp
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f"MO KHOA: {name}", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
                cv2.imshow('Face ID Check', frame)
                
                cv2.waitKey(2000) # Hiện hình 2 giây để bạn kịp nhìn thấy chữ "ĐÃ MỞ"
                
                mo_cua_thanh_cong = True
                break # Thoát vòng for

            else:
                # Vẽ màu đỏ nếu sai (hoặc chưa đủ độ tin cậy)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                cv2.putText(frame, f"Unknown ({conf_val})", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

        # Nếu đã mở cửa thành công thì thoát vòng lặp Camera
        if mo_cua_thanh_cong:
            print("✅ Đã mở cửa xong -> TẮT CAMERA NGAY LẬP TỨC.")
            break 

        cv2.imshow('Face ID Check', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Tắt Camera và giải phóng bộ nhớ
    cap.release()
    cv2.destroyAllWindows()
    print("💤 Camera đã tắt. Hệ thống quay lại chế độ ngủ chờ phím 'A'.")

# --- CHƯƠNG TRÌNH CHÍNH (LUÔN LẮNG NGHE) ---
def main():
    # Load dữ liệu AI
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    try:
        recognizer.read("trainner.yml")
        with open("labels.pickle", 'rb') as f:
            og_labels = pickle.load(f)
            labels = {v: k for k, v in og_labels.items()}
    except:
        print("LỖI: Chưa có file trainner.yml! Hãy chạy file train trước.")
        return

    face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

    while True:
        # Python ngồi im nghe ESP32
        if ser and ser.in_waiting > 0:
            try:
                line = ser.readline().decode('utf-8').strip()
                
                # Khi bạn ấn 'A', ESP32 gửi dòng này
                if "START_RECOGNITION" in line:
                    print(f"\n🔔 TING TING! Nhận lệnh từ phím A -> BẬT CAMERA!")
                    kich_hoat_camera(recognizer, labels, face_cascade)
                
                # In ra các tin nhắn khác từ ESP32 (ví dụ "DA MO KHOA"...)
                elif line:
                    print(f"[ESP32 báo]: {line}")
            except:
                pass
        
        time.sleep(0.05) # Nghỉ nhẹ để đỡ tốn CPU

if __name__ == "__main__":
    main()