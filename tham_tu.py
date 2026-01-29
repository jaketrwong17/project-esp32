import serial
import time

# --- CẤU HÌNH ---
SERIAL_PORT = 'COM4'  # Đảm bảo đúng cổng COM của bạn
BAUD_RATE = 115200

print(f"--- ĐANG THEO DÕI LOG TỪ ESP32 (CỔNG {SERIAL_PORT}) ---")
print("Hãy thao tác trên điện thoại (Đổi pass, Thêm mặt...) để xem kết quả bên dưới:\n")

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    
    while True:
        if ser.in_waiting > 0:
            try:
                # Đọc dữ liệu từ ESP32 gửi lên
                line = ser.readline().decode('utf-8').strip()
                if line:
                    print(f"[ESP32 nói]: {line}")
            except:
                pass
        time.sleep(0.01)

except Exception as e:
    print(f"LỖI: Không mở được cổng COM. Hãy tắt Arduino IDE hoặc các file Python khác! \nChi tiết: {e}")