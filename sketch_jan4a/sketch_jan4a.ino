#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <ESP32Servo.h>
#include <LiquidCrystal_I2C.h>
#include <Keypad.h>
#include <Password.h>
#include <SPI.h>
#include <MFRC522.h>
#include <Preferences.h>

// --- CẤU HÌNH CHÂN ---
#define SS_PIN 4
#define RST_PIN 5  
#define BUZZER_PIN 23
#define SERVO_PIN 13 

// --- CẤU HÌNH KEYPAD ---
const byte ROWS = 4; 
const byte COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {14, 27, 26, 25}; 
byte colPins[COLS] = {33, 32, 18, 19};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// KHỞI TẠO ĐỐI TƯỢNG
Servo servo;
AsyncWebServer server(80);
AsyncWebSocket ws("/ws"); 
Preferences preferences;
LiquidCrystal_I2C lcd(0x27, 16, 2);
MFRC522 rfid(SS_PIN, RST_PIN);
Password password = Password("1234"); 

// BIẾN TOÀN CỤC
String currentPassString = "1234"; 
const int MAX_CARDS = 10; 
byte cardList[MAX_CARDS][4];
int cardCount = 0;
bool isLearningMode = false;
String faceNames = ""; 
bool doorLocked = true;
unsigned long openStartTime = 0;
const unsigned long AUTO_CLOSE_DELAY = 20000; // 20 giây tự đóng
bool timerActive = false;
int lastRemainingSec = -1;

// KHAI BÁO HÀM
void sendData();
void controlDoor(bool lock, String method);
void displayWelcomeMessage();
void deleteCard(int index);
void updatePassword(String newPass);
void updateTimerDisplay(int remaining);

// --- GIAO DIỆN WEB ---
void handleRoot(AsyncWebServerRequest *request) {
  String html = R"rawliteral(
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font-family: sans-serif; background: #1a1a2e; color: white; text-align: center; }
  .container { max-width: 450px; margin: auto; background: #16213e; padding: 20px; border-radius: 15px; }
  .timer-box { font-size: 48px; color: #e94560; background: #0f3460; padding: 10px; border-radius: 10px; margin: 10px 0; }
  .item-row { background: #0f3460; margin: 8px 0; padding: 12px; display: flex; justify-content: space-between; border-radius: 8px; align-items: center; }
  .btn { padding: 10px; cursor: pointer; border: none; border-radius: 5px; color: white; font-weight: bold; }
  .btn-unlock { background: #27ae60; width: 100%; font-size: 18px; }
  .btn-del { background: #c0392b; font-size: 12px; }
  .inp-pass { padding: 10px; width: 60%; border-radius: 5px; border: none; }
</style>
<script>
  var gateway = `ws://${window.location.hostname}/ws`;
  var websocket;
  window.onload = () => { 
    websocket = new WebSocket(gateway);
    websocket.onmessage = (e) => {
      var data = JSON.parse(e.data);
      document.getElementById('timer').innerText = data.remaining + "s";
      document.getElementById('doorStatus').innerText = data.locked ? "ĐANG KHÓA" : "ĐANG MỞ";
      
      let fHtml = "";
      if(data.faceNames) {
        data.faceNames.split(",").forEach((name) => {
          if(name) fHtml += `<div class="item-row"><span>Mặt: ${name}</span><button class="btn btn-del" onclick="delFace('${name}')">XÓA</button></div>`;
        });
      }
      document.getElementById('faceList').innerHTML = fHtml;

      let cHtml = "";
      for(let i=0; i<data.cardCnt; i++) {
        cHtml += `<div class="item-row"><span>Thẻ RFID #${i+1}</span><button class="btn btn-del" onclick="delCard(${i})">XÓA</button></div>`;
      }
      document.getElementById('cardList').innerHTML = cHtml;
    };
  };
  function send(m) { websocket.send(m); }
  function delFace(name) { if(confirm("Xóa mặt " + name + "?")) send("delface_" + name); }
  function delCard(idx) { if(confirm("Xóa thẻ?")) send("del_" + idx); }
  function learnFace() { let name = prompt("Tên người mới:"); if(name) send("learnface_" + name); }
  
  function changePass() {
    let p = document.getElementById("newPassInput").value;
    if(p.length === 4 && !isNaN(p)) {
      if(confirm("Đổi mật khẩu thành: " + p + "?")) {
        send("changepass_" + p);
        document.getElementById("newPassInput").value = "";
      }
    } else {
      alert("Mật khẩu phải là 4 chữ số!");
    }
  }
</script></head>
<body>
  <div class="container">
    <h2 id="doorStatus">KET NOI...</h2>
    <div class="timer-box" id="timer">20s</div>
    <button class="btn btn-unlock" onclick="send('toggle')">DONG/MO CUA</button>
    
    <div style="margin-top:20px; background:#0f3460; padding:10px; border-radius:10px">
      <h3>DOI MAT KHAU KEYPAD</h3>
      <input type="number" id="newPassInput" class="inp-pass" placeholder="Nhập 4 số mới">
      <button class="btn" style="background:#8e44ad; width:30%" onclick="changePass()">LƯU</button>
    </div>

    <div style="margin-top:10px">
      <button class="btn" style="background:#f39c12" onclick="send('learn')">THEM THE RFID</button>
      <button class="btn" style="background:#3498db" onclick="learnFace()">THEM MAT</button>
    </div>
    <hr><h3>DANH SACH MAT</h3><div id="faceList"></div>
    <hr><h3>DANH SACH THE</h3><div id="cardList"></div>
  </div>
</body></html>)rawliteral";
  request->send(200, "text/html", html);
}

// --- SETUP ---
void setup() {
  Serial.begin(115200);
  
  // Nạp thẻ nhớ Flash
  preferences.begin("my-app", false);
  cardCount = preferences.getInt("count", 0);
  for (int i = 0; i < cardCount; i++) {
    String key = "c" + String(i);
    preferences.getBytes(key.c_str(), cardList[i], 4);
  }
  if(preferences.isKey("sys_pass")) {
    currentPassString = preferences.getString("sys_pass");
  }
  password.set((char*)currentPassString.c_str()); 
  Serial.println("Mat khau: " + currentPassString);

  // WiFi AP
  WiFi.softAP("ESP32_CuaThongMinh", "12345678");
  Serial.print("IP Address: ");
  Serial.println(WiFi.softAPIP());
  
  // Cài đặt Servo
  servo.setPeriodHertz(50); 
  servo.attach(SERVO_PIN, 500, 2400); 
  servo.write(110); // Góc khóa ban đầu
  
  // Khởi động thiết bị ngoại vi
  lcd.init(); lcd.backlight();
  pinMode(BUZZER_PIN, OUTPUT);
  SPI.begin(15, 35, 2, 4); // SCK, MISO, MOSI, SS (Sửa lại nếu chân khác)
  rfid.PCD_Init();
  
  // Cài đặt Server & WebSocket
  server.on("/", HTTP_GET, handleRoot);

  ws.onEvent([](AsyncWebSocket *s, AsyncWebSocketClient *c, AwsEventType t, void *arg, uint8_t *data, size_t len){
    if (t == WS_EVT_CONNECT) sendData();
    if (t == WS_EVT_DATA) {
      data[len] = 0; String msg = (char*)data;
      if (msg == "toggle") { doorLocked = !doorLocked; controlDoor(doorLocked, "web"); }
      else if (msg == "learn") { isLearningMode = true; lcd.clear(); lcd.print("QUET THE MOI..."); }
      else if (msg.startsWith("learnface_")) Serial.println("LEARNFACE:" + msg.substring(10));
      else if (msg.startsWith("delface_")) Serial.println("DELETE_FACE:" + msg.substring(8));
      else if (msg.startsWith("del_")) deleteCard(msg.substring(4).toInt());
      else if (msg.startsWith("changepass_")) updatePassword(msg.substring(11));
    }
  });

  server.addHandler(&ws);

  // --- QUAN TRỌNG: NHẬN TÍN HIỆU TỪ PYTHON ---
  server.on("/face_toggle", HTTP_POST, [](AsyncWebServerRequest *request){
      doorLocked = false;             // Chuyển trạng thái mở
      controlDoor(doorLocked, "FACE ID"); // Kích hoạt Servo & LCD
      request->send(200, "text/plain", "OK"); // Phản hồi cho Python
      Serial.println("DA NHAN LENH MO CUA TU PYTHON");
  });
  // -------------------------------------------

  server.begin();
  displayWelcomeMessage();
}

// --- LOOP ---
void loop() {
  // Timer tự đóng cửa
  if (timerActive && !doorLocked) {
      unsigned long elapsed = millis() - openStartTime;
      if (elapsed >= AUTO_CLOSE_DELAY) {
          doorLocked = true; timerActive = false; 
          controlDoor(true, "auto");
      } else {
          int remaining = (AUTO_CLOSE_DELAY - elapsed) / 1000;
          if (remaining != lastRemainingSec) {
              lastRemainingSec = remaining;
              sendData(); updateTimerDisplay(remaining);
          }
      }
  }

  // Xử lý Keypad
  char key = keypad.getKey();
  if (key != NO_KEY) {
    digitalWrite(BUZZER_PIN, HIGH); delay(50); digitalWrite(BUZZER_PIN, LOW); 
    
    if (key == 'A') { // Bắt đầu nhận diện
       Serial.println("START_RECOGNITION"); 
       lcd.clear(); lcd.print("DANG QUET MAT...");
    } 
    else if (key == 'C') { // Reset mật khẩu đang nhập
       password.reset(); displayWelcomeMessage(); 
    }
    else { // Nhập mật khẩu
       static int len = 0; 
       if (len == 0) lcd.clear();
       password.append(key); lcd.print("*"); len++;
       if (len == 4) { 
          if (password.evaluate()) { 
             doorLocked = !doorLocked; controlDoor(doorLocked, "keypad"); 
          } else {
             lcd.clear(); lcd.print("SAI MAT KHAU!");
             digitalWrite(BUZZER_PIN, HIGH); delay(500); digitalWrite(BUZZER_PIN, LOW);
             delay(1000); displayWelcomeMessage();
          }
          password.reset(); len = 0; 
       }
    }
  }

  // Xử lý RFID
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    byte currUID[4]; for (byte i = 0; i < 4; i++) currUID[i] = rfid.uid.uidByte[i];
    if (isLearningMode) {
      if(cardCount < MAX_CARDS) {
        memcpy(cardList[cardCount], currUID, 4);
        preferences.putBytes(("c" + String(cardCount)).c_str(), cardList[cardCount], 4);
        cardCount++; preferences.putInt("count", cardCount);
        lcd.clear(); lcd.print("DA THEM THE!"); digitalWrite(BUZZER_PIN, HIGH); delay(500); digitalWrite(BUZZER_PIN, LOW);
      }
      isLearningMode = false; delay(1000); displayWelcomeMessage();
    } else {
      bool f = false; for (int i = 0; i < cardCount; i++) if (memcmp(currUID, cardList[i], 4) == 0) f = true;
      if (f) { doorLocked = !doorLocked; controlDoor(doorLocked, "RFID"); }
      else { lcd.clear(); lcd.print("SAI THE!"); digitalWrite(BUZZER_PIN, HIGH); delay(500); digitalWrite(BUZZER_PIN, LOW); delay(1000); displayWelcomeMessage(); }
    }
    rfid.PICC_HaltA(); rfid.PCD_StopCrypto1();
  }

  // Xử lý lệnh từ Serial (Python gửi tên khuôn mặt đã lưu)
  if (Serial.available() > 0) { 
    String in = Serial.readStringUntil('\n'); 
    in.trim(); // Cắt bỏ khoảng trắng thừa (Rất quan trọng)

    // 1. Lệnh cập nhật danh sách tên (như cũ)
    if (in.startsWith("LIST:")) { 
        faceNames = in.substring(5); 
        sendData(); 
    } 
    
    // 2. LỆNH MỞ CỬA TỪ FACE ID (Cái bạn đang thiếu)
    else if (in == "OPEN_DOOR") {
        Serial.println("ESP32: DA MO KHOA BANG FACE ID"); 
        doorLocked = false;             // Mở chốt
        controlDoor(doorLocked, "FACE ID"); // Kích hoạt Servo + Timer 20s
    }
  }
}

// --- CÁC HÀM PHỤ TRỢ ---

void updateTimerDisplay(int remaining) {
    lcd.setCursor(0, 1);
    lcd.print("Dong sau: "); lcd.print(remaining); lcd.print("s  ");
}

void updatePassword(String newPass) {
  if(newPass.length() == 4) {
    currentPassString = newPass;
    preferences.putString("sys_pass", currentPassString);
    password.set((char*)currentPassString.c_str()); 
    digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW); 
    delay(100); digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW);
    Serial.println("Mat khau moi: " + currentPassString);
  }
}

void controlDoor(bool lock, String method) {
  digitalWrite(BUZZER_PIN, HIGH); delay(200); digitalWrite(BUZZER_PIN, LOW);
  
  if(lock) servo.write(110); // Góc KHÓA
  else servo.write(50);      // Góc MỞ
  
  if (!lock) { 
      openStartTime = millis(); timerActive = true; lastRemainingSec = -1; 
      lcd.clear(); lcd.print("MO KHOA: " + method);
      updateTimerDisplay(AUTO_CLOSE_DELAY / 1000);
  } else {
      timerActive = false;
      lcd.clear(); lcd.print("DA KHOA CUA");
      delay(1500); displayWelcomeMessage();
  }
  sendData();
}

void displayWelcomeMessage() { lcd.clear(); lcd.print("Moi nhap pass..."); }

void deleteCard(int index) {
  if (index < 0 || index >= cardCount) return;
  for (int i = index; i < cardCount - 1; i++) memcpy(cardList[i], cardList[i+1], 4);
  cardCount--;
  preferences.putInt("count", cardCount);
  for (int i = 0; i < cardCount; i++) { String key = "c" + String(i); preferences.putBytes(key.c_str(), cardList[i], 4); }
  sendData();
}

void sendData() {
  int rem = (timerActive && !doorLocked) ? (AUTO_CLOSE_DELAY - (millis() - openStartTime)) / 1000 : 20;
  String json = "{\"locked\":" + String(doorLocked) + ",\"remaining\":" + String(rem < 0 ? 0 : rem) + ",\"faceNames\":\"" + faceNames + "\",\"cardCnt\":" + String(cardCount) + "}";
  ws.textAll(json);
}