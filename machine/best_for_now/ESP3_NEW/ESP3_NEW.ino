// ============================================================
// ESP3 - Drop Check + Bin Level Monitor
// Arduino IDE 1.8.19 + ESP32 Core 3.0.2
//
// ลำดับการทำงาน (แยกเป็น 2 เฟส ตามที่ ESP2 จะเรียกคนละจังหวะ):
// เฟส A: DROP_CHECK:BIN1/BIN2/BIN3
//        -> เฝ้ารอ IR ของถังนั้นเองว่าขวดตกเข้าไปจริงภายใน 1.5 วินาที
//        -> ตอบกลับ DROP:OK หรือ DROP:TIMEOUT
//        (ESP2 เรียกตอนฝา Servo4 เปิดค้างอยู่ ก่อนจะปิดฝา)
// เฟส B: CHECK_LEVEL
//        -> อ่านระดับถัง BIN1/BIN2/BIN3 ด้วยอัลตราโซนิก
//        -> ตอบกลับ LEVEL:BIN1=..,BIN2=..,BIN3=..
//        (ESP2 เรียกหลังปิดฝา + ถอยมอเตอร์กลับ Home แล้ว)
//
// อัปเดตจากไฟล์เทสที่ทดสอบจริงแล้ว:
// - uart_test.ino        -> ฝั่ง ESP2 ย้ายมาใช้ GPIO16/17 (UART2)
//                           แทน GPIO1/3 (UART0) จึงต้องย้ายฝั่ง ESP3
//                           มาที่ GPIO16/17 ด้วย เพื่อให้ต่อสายตรงกัน
//                           และเลิกชนกับ Serial Monitor
// - ultra_sonic_ir.ino    -> อ่านอัลตราโซนิกด้วยสูตรเดิม (ตรงกันอยู่แล้ว)
//                           และ IR ใช้ pinMode(INPUT) ธรรมดา (ไม่ pull-up)
// ============================================================

#include <Arduino.h>

// ========================= PINOUT ESP3 =========================

// ESP3 <-> ESP2 (UART2) - ตาม uart_test.ino (ฝั่ง ESP2 ใช้ GPIO16/17)
#define UART_ESP2_RX 16
#define UART_ESP2_TX 17

#define BIN1_TRIG 27
#define BIN1_ECHO 26

#define BIN2_TRIG 14
#define BIN2_ECHO 15

#define BIN3_TRIG 12
#define BIN3_ECHO 13

#define BIN1_IR 18
#define BIN2_IR 19
#define BIN3_IR 21

// ตาม Pinout ที่ให้มา ไม่มี Drop Sensor แยกต่างหาก
// จึงใช้ IR ของถังเป้าหมายเอง (BIN1_IR/BIN2_IR/BIN3_IR) เป็นตัวยืนยันว่า
// ขวดตกเข้าถังนั้นจริง (เลือกขาตามชื่อถังที่ ESP2 ส่งมา)
int getBinIRPin(const String &binName) {
  if (binName == "BIN1") return BIN1_IR;
  if (binName == "BIN2") return BIN2_IR;
  if (binName == "BIN3") return BIN3_IR;
  return -1;
}

// ========================= CONFIG =========================

#define UART_BAUD 115200

const unsigned long DROP_CHECK_TIMEOUT_MS = 3000;

const float FULL_DISTANCE_CM = 10.0;

const int ULTRASONIC_READS = 3;

HardwareSerial uart_esp2(2);

// ========================= UART =========================

void sendEsp2(const String &message) {
  uart_esp2.print(message);
  uart_esp2.print('\n');
  Serial.println("ESP3 -> ESP2: " + message);
}

void logEsp2(const String &text) {
  sendEsp2("LOG:ESP3:" + text);
}

// ========================= DROP CHECK =========================

// เช็ค IR ทั้ง 3 ถังพร้อมกันระหว่างรอ (ไม่ใช่แค่ถังเป้าหมายอย่างเดียว)
// เพื่อรู้ว่าขวดตกถังไหนจริง ๆ (เผื่อกรณีตกผิดถัง)
// คืนค่าเป็นชื่อถังที่ตรวจพบ ("BIN1"/"BIN2"/"BIN3") หรือ "" ถ้าไม่พบเลยใน timeout
String checkBottleDropAllBins() {

  unsigned long start = millis();

  while (millis() - start < DROP_CHECK_TIMEOUT_MS) {

    // Active LOW (0) = มีวัตถุตัดผ่าน
    if (digitalRead(BIN1_IR) == LOW) return "BIN1";
    if (digitalRead(BIN2_IR) == LOW) return "BIN2";
    if (digitalRead(BIN3_IR) == LOW) return "BIN3";

    delay(1);
  }

  return "";
}

// ========================= ULTRASONIC =========================
// สูตรเดียวกับ ultra_sonic_ir.ino (ตรงกันอยู่แล้ว)

float readDistanceCM(int trigPin, int echoPin) {

  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);

  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);

  digitalWrite(trigPin, LOW);

  unsigned long duration =
      pulseIn(echoPin, HIGH, 30000);

  if (duration == 0) {
    return -1;
  }

  return duration * 0.0343 / 2.0;
}

String getUltrasonicBinStatus(int trigPin, int echoPin) {

  float total = 0;
  int valid = 0;

  for (int i = 0; i < ULTRASONIC_READS; i++) {

    float distance =
        readDistanceCM(trigPin, echoPin);

    if (distance > 0) {
      total += distance;
      valid++;
    }

    delay(30);
  }

  // ถ้าอ่านไม่ได้ ให้ถือว่า OK
  if (valid == 0) {
    return "OK";
  }

  float average = total / valid;

  if (average <= FULL_DISTANCE_CM) {
    return "FULL";
  }

  return "OK";
}

// ========================= COMMANDS (แยก 2 เฟส) =========================
// เฟส A: DROP_CHECK:BINx -> เฝ้ารอ IR ของถังนั้นว่าขวดตกจริง
// เฟส B: CHECK_LEVEL     -> อ่านระดับถังทั้ง 3 ด้วยอัลตราโซนิก (เรียกทีหลัง
//                           หลังจาก ESP2 ปิดฝา + ถอยมอเตอร์กลับ Home แล้ว)

void processDropCheck(String targetBin) {

  targetBin.trim();
  logEsp2("ACTION:DROP_CHECK:START:" + targetBin);

  if (getBinIRPin(targetBin) < 0) {
    Serial.println("DROP_CHECK: ไม่รู้จักถัง " + targetBin);
    logEsp2("ACTION:DROP_CHECK:ไม่สำเร็จ (unknown bin)");
    sendEsp2("ERROR:UNKNOWN_BIN");
    return;
  }

  String detectedBin = checkBottleDropAllBins();

  Serial.println("------------------------------");
  Serial.println("DROP_CHECK TARGET = " + targetBin);

  if (detectedBin.length() == 0) {
    // ไม่มี IR ถังไหนตรวจพบเลยภายในเวลาที่กำหนด
    Serial.println("DROP = NONE (ไม่พบขวดตกถังไหนเลย)");
    Serial.println("------------------------------");
    logEsp2("ACTION:DROP_CHECK:ไม่สำเร็จ (ไม่พบขวดตกถังไหนเลย)");
    sendEsp2("DROP:NONE");
    return;
  }

  if (detectedBin == targetBin) {
    Serial.println("DROP = OK (ตกถัง " + detectedBin + " ตรงตามเป้าหมาย)");
    Serial.println("------------------------------");
    logEsp2("ACTION:DROP_CHECK:สำเร็จ (ตกถัง " + detectedBin + ")");
    sendEsp2("DROP:OK");
  } else {
    // ขวดตกถังอื่นที่ไม่ใช่เป้าหมาย - แจ้งเตือนว่าตกผิดถัง
    Serial.println("DROP = MISMATCH (ตกถัง " + detectedBin +
                    " แต่เป้าหมายคือ " + targetBin + ")");
    Serial.println("------------------------------");
    logEsp2("ACTION:DROP_CHECK:สำเร็จบางส่วน (ตกผิดถัง " + detectedBin + ")");
    sendEsp2("DROP:MISMATCH:" + detectedBin);
  }
}

void processLevelCheck() {

  logEsp2("ACTION:CHECK_LEVEL:START");

  String bin1Status =
      getUltrasonicBinStatus(BIN1_TRIG, BIN1_ECHO);

  String bin2Status =
      getUltrasonicBinStatus(BIN2_TRIG, BIN2_ECHO);

  String bin3Status =
      getUltrasonicBinStatus(BIN3_TRIG, BIN3_ECHO);

  Serial.println("------------------------------");
  Serial.println("BIN1 = " + bin1Status);
  Serial.println("BIN2 = " + bin2Status);
  Serial.println("BIN3 = " + bin3Status);
  Serial.println("------------------------------");

  String result =
      "LEVEL:BIN1=" + bin1Status +
      ",BIN2=" + bin2Status +
      ",BIN3=" + bin3Status;

  logEsp2("ACTION:CHECK_LEVEL:สำเร็จ (" + result.substring(6) + ")");
  sendEsp2(result);
}

// ========================= SETUP =========================

void setup() {

  Serial.begin(UART_BAUD);
  Serial.setTimeout(50);

  uart_esp2.begin(UART_BAUD,
                  SERIAL_8N1,
                  UART_ESP2_RX,
                  UART_ESP2_TX);
  uart_esp2.setTimeout(50);

  pinMode(BIN1_TRIG, OUTPUT);
  pinMode(BIN1_ECHO, INPUT);

  pinMode(BIN2_TRIG, OUTPUT);
  pinMode(BIN2_ECHO, INPUT);

  pinMode(BIN3_TRIG, OUTPUT);
  pinMode(BIN3_ECHO, INPUT);

  // ใช้ INPUT_PULLUP เพื่อป้องกันสัญญาณรบกวน (Floating Input)
  pinMode(BIN1_IR, INPUT_PULLUP);
  pinMode(BIN2_IR, INPUT_PULLUP);
  pinMode(BIN3_IR, INPUT_PULLUP);

  digitalWrite(BIN1_TRIG, LOW);
  digitalWrite(BIN2_TRIG, LOW);
  digitalWrite(BIN3_TRIG, LOW);

  Serial.println("==============================");
  Serial.println("ESP3 READY - STANDBY");
  Serial.println("==============================");

  logEsp2("ESP3 READY");
}

// ========================= LOOP =========================

void loop() {

  // Standby รอคำสั่งจาก ESP2
  if (uart_esp2.available()) {

    String message =
        uart_esp2.readStringUntil('\n');

    message.trim();

    if (message.length() == 0) {
      return;
    }

    Serial.println("ESP2 -> ESP3: " + message);

    // เฟส A: DROP_CHECK:BIN1 / BIN2 / BIN3 -> เฝ้ารอ IR ถังนั้น
    if (message.startsWith("DROP_CHECK:")) {

      String targetBin =
          message.substring(11);

      targetBin.trim();

      processDropCheck(targetBin);
    }

    // เฟส B: CHECK_LEVEL -> อ่านระดับถังทั้ง 3 (เรียกหลังมอเตอร์กลับ Home)
    else if (message.startsWith("CHECK_LEVEL")) {

      processLevelCheck();
    }
  }

  delay(5);
}
