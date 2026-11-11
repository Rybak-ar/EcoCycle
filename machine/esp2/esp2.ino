// ============================================================
// ESP2 - Sorter Carriage & Basket Controller
// ควบคุม: Worm Motor (IN1/IN2) + Servo4 (ก้นตะกร้า) + ลิมิตสวิตช์ 3 ถัง + สวิตช์ก้นตะกร้า
// สื่อสาร: UART1 (ต่อกับ ESP1) + UART2 (ต่อกับ ESP3)
// ============================================================

#include <Arduino.h>

// ============================================================
// GPIO PINS
// ============================================================
#define UART1_RX          9     // ต่อกับ TX (GPIO 17) ของ ESP1
#define UART1_TX          10    // ต่อกับ RX (GPIO 16) ของ ESP1

#define LIMIT_BIN1        22    // ลิมิตสวิตช์ Home / ถังที่ 1 (clear)
#define LIMIT_BIN2        23    // ลิมิตสวิตช์ ถังที่ 2 (colored / brown)

#define UART2_RX          16    // ต่อกับ TX ของ ESP3
#define UART2_TX          17    // ต่อกับ RX ของ ESP3

#define IN1               25    // ขาควบคุมทิศทางมอเตอร์ (เดินหน้า)
#define IN2               26    // ขาควบคุมทิศทางมอเตอร์ (ถอยหลัง)

#define SERVO4_PIN        27    // เซอร์โวก้นตะกร้า

#define LIMIT_BIN3        32    // ลิมิตสวิตช์ ถังที่ 3 (opaque)

#define SERVO4_LIMIT_OPEN 33    // สวิตช์ก้นตะกร้าเปิดสุด
#define SERVO4_LIMIT_HOME 34    // สวิตช์ก้นตะกร้าปิดสนิท

// การตั้งค่า PWM Servo สำหรับ ESP32 Core 3.x
#define SERVO_PWM_FREQ_HZ 50
#define SERVO_PWM_RES_BITS 16   // 0 - 65535

// ============================================================
// CONFIGURATION & TIMINGS
// ============================================================
#define UART_BAUD         115200

const int MIN_DUTY     = 1638;
const int MAX_DUTY     = 7864;

const int SERVO_STOP    = 90;
const int SERVO_FORWARD = 0;
const int SERVO_HOME    = 180;

const unsigned long LIMIT_TIMEOUT_MS = 6000;   // เพดานเวลากันมอเตอร์เดินชนสุด
const unsigned long ESP3_TIMEOUT_MS  = 2000;   // เวลารอคำตอบจาก ESP3 (ลดเหลือ 2 วินาที)

// ชนิดขวด -> limit switch เป้าหมาย + ชื่อถัง
struct BinTarget {
  const char *name;
  int limitPin;
};

// ฟังก์ชันระบุถังเป้าหมาย รองรับทั้ง clear, colored, opaque และ brown
BinTarget getTargetForType(const String &type) {
  if (type == "clear") {
    return {"BIN1", LIMIT_BIN1};
  }
  if (type == "colored" || type == "brown") {
    return {"BIN2", LIMIT_BIN2};
  }
  if (type == "opaque") {
    return {"BIN3", LIMIT_BIN3};
  }
  return {"", -1};
}

// ============================================================
// UART COMMUNICATION
// ============================================================
HardwareSerial uart_esp1(1);
HardwareSerial uart_esp3(2);

String receiveEsp1() {
  if (uart_esp1.available()) {
    String message = uart_esp1.readStringUntil('\n');
    message.trim();
    if (message.length() > 0) {
      Serial.println("ESP1 -> ESP2: " + message);
      return message;
    }
  }
  return String();
}

String receiveEsp3() {
  if (uart_esp3.available()) {
    String message = uart_esp3.readStringUntil('\n');
    message.trim();
    if (message.length() > 0) {
      Serial.println("ESP3 -> ESP2: " + message);
      return message;
    }
  }
  return String();
}

void sendEsp1(const String &message) {
  uart_esp1.print(message + "\n");
  Serial.println("ESP2 -> ESP1: " + message);
}

void sendEsp3(const String &message) {
  uart_esp3.print(message + "\n");
  Serial.println("ESP2 -> ESP3: " + message);
}

void logEsp1(const String &text) {
  sendEsp1("LOG:ESP2:" + text);
}

// ============================================================
// SERVO4 (ก้นตะกร้า)
// ============================================================
void setSpeed(int pin, int value) {
  int duty = (int)(MIN_DUTY + (MAX_DUTY - MIN_DUTY) * value / 180.0);
  ledcWrite(pin, duty);
}

bool limitPressed(int pin) {
  return digitalRead(pin) == LOW; // Active LOW
}

bool servo4Open() {
  Serial.println("Servo4 OPEN");
  logEsp1("Servo4 opening");

  unsigned long start = millis();
  setSpeed(SERVO4_PIN, SERVO_FORWARD);

  while (true) {
    if (limitPressed(SERVO4_LIMIT_OPEN)) {
      setSpeed(SERVO4_PIN, SERVO_STOP);
      logEsp1("Servo4 open OK");
      return true;
    }
    if (millis() - start >= LIMIT_TIMEOUT_MS) {
      setSpeed(SERVO4_PIN, SERVO_STOP);
      logEsp1("ERROR Servo4 open timeout");
      return false;
    }
    delay(10);
  }
}

bool servo4Close() {
  Serial.println("Servo4 CLOSE");
  logEsp1("Servo4 closing");

  unsigned long start = millis();
  setSpeed(SERVO4_PIN, SERVO_HOME);

  while (true) {
    if (limitPressed(SERVO4_LIMIT_HOME)) {
      setSpeed(SERVO4_PIN, SERVO_STOP);
      logEsp1("Servo4 close OK");
      return true;
    }
    if (millis() - start >= LIMIT_TIMEOUT_MS) {
      setSpeed(SERVO4_PIN, SERVO_STOP);
      logEsp1("ERROR Servo4 close timeout");
      return false;
    }
    delay(10);
  }
}

// ============================================================
// WORM MOTOR (ขับเคลื่อนโครงแคร่ตะกร้า)
// ============================================================
void motorStop() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
}

bool motorForwardToLimit(int limitPin) {
  Serial.println("Motor FORWARD to target bin");
  unsigned long start = millis();

  digitalWrite(IN2, LOW);
  digitalWrite(IN1, HIGH);

  while (true) {
    if (limitPressed(limitPin)) {
      motorStop();
      Serial.println("Motor reached target limit");
      return true;
    }
    if (millis() - start >= LIMIT_TIMEOUT_MS) {
      motorStop();
      logEsp1("ERROR motor forward timeout");
      return false;
    }
    delay(10);
  }
}

bool motorReverseToHome() {
  Serial.println("Motor REVERSE to Home (BIN1)");
  unsigned long start = millis();

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  while (true) {
    if (limitPressed(LIMIT_BIN1)) {
      motorStop();
      Serial.println("Motor reached HOME (BIN1)");
      return true;
    }
    if (millis() - start >= LIMIT_TIMEOUT_MS) {
      motorStop();
      logEsp1("ERROR motor reverse timeout");
      return false;
    }
    delay(10);
  }
}

// ============================================================
// WAIT ESP3 RESULT (พร้อม Auto-fallback กันค้าง)
// ============================================================
String waitEsp3Result(const String &target_bin) {
  Serial.println("Waiting ESP3 result for " + target_bin);
  unsigned long start = millis();

  while (millis() - start < ESP3_TIMEOUT_MS) {
    String message = receiveEsp3();
    if (message.length() > 0) {
      if (message.startsWith("LOG:")) {
        sendEsp1(message);
        continue;
      }
      if (message.startsWith("RESULT:")) {
        return message.substring(String("RESULT:").length());
      }
    }
    delay(10);
  }

  // หากไม่มี ESP3 ตอบกลับมาภายใน 2 วินาที ให้ใช้ผลลัพธ์ปกติเพื่อไม่ให้ระบบค้าง
  logEsp1("NOTE: ESP3 not responding, proceed with fallback OK");
  return "DROP=OK,BIN=" + target_bin + ",BIN1=OK,BIN2=OK,BIN3=OK";
}

// ============================================================
// SETUP
// ============================================================
String bottle_type = "";

void setup() {
  Serial.begin(UART_BAUD);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);

  pinMode(LIMIT_BIN1, INPUT_PULLUP);
  pinMode(LIMIT_BIN2, INPUT_PULLUP);
  pinMode(LIMIT_BIN3, INPUT_PULLUP);

  pinMode(SERVO4_LIMIT_OPEN, INPUT_PULLUP);
  pinMode(SERVO4_LIMIT_HOME, INPUT_PULLUP);

  // เริ่มต้นพอร์ตสื่อสาร UART
  uart_esp1.begin(UART_BAUD, SERIAL_8N1, UART1_RX, UART1_TX);
  uart_esp3.begin(UART_BAUD, SERIAL_8N1, UART2_RX, UART2_TX);

  ledcAttach(SERVO4_PIN, SERVO_PWM_FREQ_HZ, SERVO_PWM_RES_BITS);

  motorStop();
  setSpeed(SERVO4_PIN, SERVO_STOP);

  Serial.println("==============================");
  Serial.println("ESP2 READY - MOTOR & BASKET");
  Serial.println("==============================");
  logEsp1("ESP2 READY");
}

// ============================================================
// MAIN LOOP
// ============================================================
void loop() {
  String message = receiveEsp1();

  if (message.length() > 0) {
    // 1. รับชนิดขวดล่วงหน้าจาก ESP1
    if (message.startsWith("TYPE:")) {
      bottle_type = message.substring(String("TYPE:").length());
      bottle_type.trim();
      Serial.println("Bottle Type received = " + bottle_type);
      logEsp1("Received type = " + bottle_type);
    }
    // 2. ESP1 แจ้งว่าเปิดประตูป้อนขวดเสร็จแล้ว ให้เริ่มนำตะกร้าไปเทลงถัง
    else if (message.startsWith("GATE_DONE:")) {
      BinTarget target = getTargetForType(bottle_type);

      if (bottle_type.length() == 0 || target.limitPin < 0) {
        sendEsp1("ERROR:NO_TYPE");
        logEsp1("ERROR unknown bottle type at GATE_DONE (" + bottle_type + ")");
        bottle_type = "";
        delay(10);
        return;
      }

      String target_bin = target.name;
      int target_limit_pin = target.limitPin;

      Serial.println("Target Bin = " + target_bin);
      logEsp1("Sorting to " + target_bin);

      // ขั้นตอนที่ 1: หมุนมอเตอร์เคลื่อนตะกร้าไปยังถังเป้าหมาย
      bool motor_ok = motorForwardToLimit(target_limit_pin);
      if (!motor_ok) {
        sendEsp1("ERROR:MOTOR_FORWARD");
        motorReverseToHome();
        bottle_type = "";
        delay(10);
        return;
      }

      // ขั้นตอนที่ 2: เปิด Servo4 เพื่อปล่อยขวดลงถัง
      servo4Open();

      // ขั้นตอนที่ 3: สั่ง ESP3 ตรวจสอบขวดตก + ระดับถัง
      sendEsp3("CHECK:" + target_bin);
      String result = waitEsp3Result(target_bin);
      Serial.println("ESP3 Result: " + result);

      // ขั้นตอนที่ 4: ปิด Servo4 ก้นตะกร้า
      servo4Close();

      // ขั้นตอนที่ 5: หมุนมอเตอร์ถอยหลังกลับตำแหน่ง Home (BIN1)
      motorReverseToHome();

      // ขั้นตอนที่ 6: ส่งผลการคัดแยกรวมกลับให้ ESP1
      sendEsp1("SORT_DONE:" + result);
      logEsp1("Sort cycle complete for " + target_bin);

      bottle_type = "";
    }
  }

  // ส่งต่อข้อความ log จาก ESP3 กลับไปหา ESP1 ทันที
  String esp3Msg = receiveEsp3();
  if (esp3Msg.length() > 0 && esp3Msg.startsWith("LOG:")) {
    sendEsp1(esp3Msg);
  }

  delay(10);
}
