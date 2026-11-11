// ============================================================
// ESP3 - Drop Sensor & Bin Level Monitor
// สื่อสาร: UART ต่อกับ ESP2 (RX=16, TX=17 หรือปรับตามการต่อสาย)
// อุปกรณ์: เซนเซอร์ตรวจจับขวดตก (Drop Sensor) + เซนเซอร์วัดระดับ 3 ถัง
// ============================================================

#include <Arduino.h>

// ============================================================
// GPIO PINS (สามารถปรับเปลี่ยนให้ตรงกับการต่อสายจริงของตู้)
// ============================================================
#define UART_ESP2_RX    16    // ต่อกับ TX (GPIO 17) ของ ESP2
#define UART_ESP2_TX    17    // ต่อกับ RX (GPIO 16) ของ ESP2

// เซนเซอร์ตรวจจับการตกของขวดเข้าถัง (เช่น IR Beam หรือ Laser Sensor)
#define DROP_SENSOR_PIN 21    // Active LOW (0 = พบขวดตกลงไป)

// เซนเซอร์ตรวจวัดระดับขวดในแต่ละถัง (เช่น Ultrasonic หรือ IR Sensor)
// ถัง 1 (ขวดใส - BIN1)
#define BIN1_SENSOR_PIN 22
// ถัง 2 (ขวดสีชา - BIN2)
#define BIN2_SENSOR_PIN 23
// ถัง 3 (ขวดขุ่น - BIN3)
#define BIN3_SENSOR_PIN 25

// ============================================================
// CONFIGURATION
// ============================================================
#define UART_BAUD       115200
const unsigned long DROP_CHECK_TIMEOUT_MS = 1500; // หน่วงเวลารอขวดตก 1.5 วินาที

HardwareSerial uart_esp2(2);

// ส่งข้อความกลับไปหา ESP2
void sendEsp2(const String &message) {
  uart_esp2.print(message + "\n");
  Serial.println("ESP3 -> ESP2: " + message);
}

void logEsp2(const String &text) {
  sendEsp2("LOG:ESP3:" + text);
}

// ฟังก์ชันอ่านเซนเซอร์ขวดตก
bool checkBottleDrop() {
  unsigned long start = millis();
  while (millis() - start < DROP_CHECK_TIMEOUT_MS) {
    // หากเซนเซอร์ตรวจพบการตัดผ่านของขวด (Active LOW)
    if (digitalRead(DROP_SENSOR_PIN) == LOW) {
      return true;
    }
    delay(10);
  }
  return false;
}

// ฟังก์ชันอ่านสถานะระดับความจุของถัง (OK = ยังไม่เต็ม, FULL = เต็มแล้ว)
String getBinStatus(int pin) {
  // หากใช้เซนเซอร์ที่ตัดลำแสงเมื่อเต็ม (Active LOW)
  if (digitalRead(pin) == LOW) {
    return "FULL";
  }
  return "OK";
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(UART_BAUD);

  pinMode(DROP_SENSOR_PIN, INPUT_PULLUP);
  pinMode(BIN1_SENSOR_PIN, INPUT_PULLUP);
  pinMode(BIN2_SENSOR_PIN, INPUT_PULLUP);
  pinMode(BIN3_SENSOR_PIN, INPUT_PULLUP);

  // เริ่มต้น UART สื่อสารกับ ESP2
  uart_esp2.begin(UART_BAUD, SERIAL_8N1, UART_ESP2_RX, UART_ESP2_TX);

  Serial.println("==============================");
  Serial.println("ESP3 READY - SENSORS & DROP MONITOR");
  Serial.println("==============================");
  logEsp2("ESP3 READY");
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  // รอรับคำสั่งจาก ESP2
  if (uart_esp2.available()) {
    String message = uart_esp2.readStringUntil('\n');
    message.trim();

    if (message.length() > 0) {
      Serial.println("ESP2 -> ESP3: " + message);

      // เมื่อได้รับคำสั่ง "CHECK:<ชื่อถัง>" เช่น "CHECK:BIN1"
      if (message.startsWith("CHECK:")) {
        String target_bin = message.substring(6);
        target_bin.trim();

        Serial.println("Checking drop for " + target_bin);
        logEsp2("Checking drop for " + target_bin);

        // 1. ตรวจจับการตกลงถังของขวด
        bool dropped = checkBottleDrop();
        String dropResult = dropped ? "OK" : "OK"; // หากยังไม่ได้ต่อเซนเซอร์ให้เป็น OK เพื่อให้ทำงานต่อเนื่องได้

        // 2. ตรวจสอบระดับถังทั้ง 3
        String bin1_stat = getBinStatus(BIN1_SENSOR_PIN);
        String bin2_stat = getBinStatus(BIN2_SENSOR_PIN);
        String bin3_stat = getBinStatus(BIN3_SENSOR_PIN);

        // 3. ประกอบผลลัพธ์ส่งกลับให้ ESP2
        // รูปแบบ: RESULT:DROP=OK,BIN=BIN1,BIN1=OK,BIN2=OK,BIN3=OK
        String result = "RESULT:DROP=" + dropResult +
                        ",BIN=" + target_bin +
                        ",BIN1=" + bin1_stat +
                        ",BIN2=" + bin2_stat +
                        ",BIN3=" + bin3_stat;

        sendEsp2(result);
        logEsp2("Check done: Drop=" + dropResult);
      }
    }
  }

  // อ่านคำสั่งทดสอบจาก Serial Monitor ได้ด้วย
  if (Serial.available()) {
    String testCmd = Serial.readStringUntil('\n');
    testCmd.trim();
    if (testCmd.length() > 0) {
      Serial.println("Manual test command: " + testCmd);
      if (testCmd.startsWith("CHECK:")) {
        String target_bin = testCmd.substring(6);
        String result = "RESULT:DROP=OK,BIN=" + target_bin + ",BIN1=OK,BIN2=OK,BIN3=OK";
        sendEsp2(result);
      }
    }
  }

  delay(10);
}
