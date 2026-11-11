// ============================================================
// ESP2 - Carriage + Basket Controller
// Arduino IDE 1.8.19 + ESP32 Core 3.0.2
//
// หน้าที่ (ลำดับใหม่):
// 1. รับ TYPE และ GATE_DONE จาก ESP1 (GATE_DONE ตอนนี้ไม่มีข้อมูลแนบ)
// 2. เลื่อนตะกร้าไปถังเป้าหมาย
// 3. เปิด Servo4 จนสุดลิมิต แล้ว "ค้างไว้" ที่ตำแหน่งเปิด (ไม่ปิดทันที)
// 4. ส่ง DROP_CHECK:BINx ให้ ESP3 เฝ้ารอ IR ในถังเป้าหมายว่าขวดตกจริง
// 5. ได้ DROP:OK (หรือ timeout) กลับมา -> ค่อยปิด Servo4 กลับด้วยลิมิต Home
// 6. หมุนมอเตอร์ 12V กลับจนชนลิมิตถังแรก (Home)
// 7. ขอระดับความจุถังทั้ง 3 จาก ESP3 ผ่านอัลตราโซนิก (CHECK_LEVEL)
// 8. รวมผล (Drop + ระดับถัง) ส่งกลับ ESP1 -> ESP1 ส่งต่อให้ Pi5
//
// อัปเดตจากไฟล์เทสที่ทดสอบจริงแล้ว:
// - uart_test.ino      -> ย้าย UART ESP1/ESP3 ออกจาก GPIO1/3
//                         (เลิกชน Serial Monitor)
// - limit_sw_test.ino,
//   servo_limit.ino    -> Limit Switch กดแล้ว = HIGH (ใช้ INPUT_PULLUP)
// - mg995.ino,
//   servo_limit.ino    -> คุม Servo ด้วยไลบรารี ESP32Servo (servo.write)
// - l298n_test.ino     -> คุมมอเตอร์ IN1/IN2 แบบเดิม (ตรงกันอยู่แล้ว)
// ============================================================

#include <Arduino.h>
#include <ESP32Servo.h>

// ========================= PINOUT ESP2 =========================

#define LIMIT_BIN1          22
#define LIMIT_BIN2          23
#define LIMIT_BIN3          32

#define SERVO_OPEN_LIMIT    33
#define SERVO_HOME_LIMIT    21

#define IN1                  26//25
#define IN2                  25//26

#define SERVO4_PIN           27

// ESP2 <-> ESP1  (UART1) - ตาม uart_test.ino
#define ESP1_RX              18
#define ESP1_TX              19

// ESP2 <-> ESP3  (UART2) - ตาม uart_test.ino
// ย้ายออกจาก GPIO1/3 (UART0) เพื่อไม่ให้ชนกับ Serial Monitor
#define ESP3_RX              16
#define ESP3_TX              17

// ========================= CONFIG =========================

#define UART_BAUD 115200

const int SERVO_STOP = 90;
const int SERVO_FORWARD = 0;
const int SERVO_HOME = 180;

const unsigned long LIMIT_TIMEOUT_MS = 10000;
const unsigned long ESP3_TIMEOUT_MS = 4500;

// ========================= UART =========================

HardwareSerial uart_esp1(1);
HardwareSerial uart_esp3(2);

// ========================= SERVO4 =========================

Servo servo4;

String bottleType = "";
bool machineFault = false; // true = ค้าง รอ RESET_FAULT (พิมพ์ผ่าน Serial Monitor)

void sendEsp1(const String &message) {
  uart_esp1.print(message);
  uart_esp1.print('\n');
  Serial.println("ESP2 -> ESP1: " + message);
}

void sendEsp3(const String &message) {
  uart_esp3.print(message);
  uart_esp3.print('\n');
  Serial.println("ESP2 -> ESP3: " + message);
}

void logEsp1(const String &text) {
  sendEsp1("LOG:ESP2:" + text);
}

String receiveEsp1() {
  if (!uart_esp1.available()) return "";

  String message = uart_esp1.readStringUntil('\n');
  message.trim();

  if (message.length() > 0) {
    Serial.println("ESP1 -> ESP2: " + message);
  }

  return message;
}

String receiveEsp3() {
  if (!uart_esp3.available()) return "";

  String message = uart_esp3.readStringUntil('\n');
  message.trim();

  if (message.length() > 0) {
    Serial.println("ESP3 -> ESP2: " + message);
  }

  return message;
}

// ========================= TARGET BIN =========================
// ใช้ฟังก์ชันแบบคืนค่า bool แทน struct
// เพื่อหลีกเลี่ยงปัญหา Arduino IDE 1.8.19
// ที่สร้าง function prototype อัตโนมัติผิดตำแหน่ง

bool getTarget(String type, String &targetName, int &targetLimitPin) {
  type.trim();
  type.toLowerCase();

  if (type == "clear") {
    targetName = "BIN1";
    targetLimitPin = LIMIT_BIN1;
    return true;
  }

  if (type == "colored" || type == "brown") {
    targetName = "BIN2";
    targetLimitPin = LIMIT_BIN2;
    return true;
  }

  if (type == "opaque") {
    targetName = "BIN3";
    targetLimitPin = LIMIT_BIN3;
    return true;
  }

  targetName = "";
  targetLimitPin = -1;
  return false;
}

// ========================= LIMIT =========================
// ตาม limit_sw_test.ino / servo_limit.ino (INPUT_PULLUP)
// กดสวิตช์แล้วอ่านค่าได้ HIGH

bool limitPressed(int pin) {
  return digitalRead(pin) == HIGH;
}

// ========================= SERVO 4 =========================
// ตาม mg995.ino / servo_limit.ino : ใช้ไลบรารี ESP32Servo

void setServo(int value) {
  servo4.write(value);
}

bool servoOpen() {
  logEsp1("ACTION:Servo4_OPEN:START");

  unsigned long start = millis();
  setServo(SERVO_FORWARD);

  while (millis() - start < LIMIT_TIMEOUT_MS) {

    if (limitPressed(SERVO_OPEN_LIMIT)) {
      setServo(SERVO_STOP);
      logEsp1("ACTION:Servo4_OPEN:สำเร็จ");
      return true;
    }

    delay(10);
  }

  setServo(SERVO_STOP);
  logEsp1("ACTION:Servo4_OPEN:ไม่สำเร็จ (limit timeout)");
  return false;
}

bool servoHome() {
  logEsp1("ACTION:Servo4_CLOSE:START");

  unsigned long start = millis();
  setServo(SERVO_HOME);

  while (millis() - start < LIMIT_TIMEOUT_MS) {

    if (limitPressed(SERVO_HOME_LIMIT)) {
      setServo(SERVO_STOP);
      logEsp1("ACTION:Servo4_CLOSE:สำเร็จ");
      return true;
    }

    delay(10);
  }

  setServo(SERVO_STOP);
  logEsp1("ACTION:Servo4_CLOSE:ไม่สำเร็จ (limit timeout)");
  return false;
}

// ========================= MOTOR =========================
// ตาม l298n_test.ino (IN1/IN2 ตรงกับของเดิมอยู่แล้ว)

void motorStop() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
}

bool motorToBin(int targetLimit) {
  logEsp1("ACTION:Motor_FORWARD:START");

  unsigned long start = millis();

  // เดินหน้า
  digitalWrite(IN2, LOW);
  digitalWrite(IN1, HIGH);

  while (millis() - start < LIMIT_TIMEOUT_MS) {

    if (limitPressed(targetLimit)) {
      motorStop();
      logEsp1("ACTION:Motor_FORWARD:สำเร็จ");
      return true;
    }

    delay(10);
  }

  motorStop();
  logEsp1("ACTION:Motor_FORWARD:ไม่สำเร็จ (limit timeout)");
  return false;
}

bool motorHome() {
  logEsp1("ACTION:Motor_HOME:START");

  unsigned long start = millis();

  // ถอยกลับ Home ที่ BIN1
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  while (millis() - start < LIMIT_TIMEOUT_MS) {

    if (limitPressed(LIMIT_BIN1)) {
      motorStop();
      logEsp1("ACTION:Motor_HOME:สำเร็จ");
      return true;
    }

    delay(10);
  }

  motorStop();
  logEsp1("ACTION:Motor_HOME:ไม่สำเร็จ (limit timeout)");
  return false;
}

// ========================= WAIT ESP3 =========================
// แยกเป็น 2 เฟสตามลำดับใหม่:
// เฟส A: ยืนยันว่าขวดตกเข้าถัง (IR ในถังเป้าหมาย) ก่อนจะปิดฝา/ถอยมอเตอร์
// เฟส B: หลังถอยมอเตอร์กลับ Home แล้ว ค่อยขอระดับความจุถังทั้ง 3 ผ่านอัลตราโซนิก

String waitEsp3Drop(String targetBin) {
  unsigned long start = millis();

  while (millis() - start < ESP3_TIMEOUT_MS) {

    String message = receiveEsp3();

    if (message.length() == 0) {
      delay(10);
      continue;
    }

    if (message.startsWith("LOG:")) {
      sendEsp1(message);
      continue;
    }

    if (message.startsWith("DROP:")) {
      return message.substring(5); // "OK" / "NONE" / "MISMATCH:BINx"
    }

    if (message.startsWith("ERROR:")) {
      return "ERROR";
    }
  }

  logEsp1("ERROR:ESP3_DROP_TIMEOUT");
  return "TIMEOUT";
}

String waitEsp3Level() {
  unsigned long start = millis();

  while (millis() - start < ESP3_TIMEOUT_MS) {

    String message = receiveEsp3();

    if (message.length() == 0) {
      delay(10);
      continue;
    }

    if (message.startsWith("LOG:")) {
      sendEsp1(message);
      continue;
    }

    if (message.startsWith("LEVEL:")) {
      return message.substring(6); // "BIN1=OK,BIN2=FULL,BIN3=OK"
    }

    if (message.startsWith("ERROR:")) {
      return "BIN1=UNKNOWN,BIN2=UNKNOWN,BIN3=UNKNOWN";
    }
  }

  logEsp1("ERROR:ESP3_LEVEL_TIMEOUT");
  return "BIN1=UNKNOWN,BIN2=UNKNOWN,BIN3=UNKNOWN";
}

// ========================= SETUP =========================

void setup() {
  Serial.begin(UART_BAUD);
  Serial.setTimeout(50);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  motorStop();

  pinMode(LIMIT_BIN1, INPUT_PULLUP);
  pinMode(LIMIT_BIN2, INPUT_PULLUP);
  pinMode(LIMIT_BIN3, INPUT_PULLUP);

  pinMode(SERVO_OPEN_LIMIT, INPUT_PULLUP);
  pinMode(SERVO_HOME_LIMIT, INPUT_PULLUP);

  uart_esp1.begin(UART_BAUD, SERIAL_8N1,
                  ESP1_RX, ESP1_TX);
  uart_esp1.setTimeout(50);

  uart_esp3.begin(UART_BAUD, SERIAL_8N1,
                  ESP3_RX, ESP3_TX);
  uart_esp3.setTimeout(50);

  servo4.attach(SERVO4_PIN);

  setServo(SERVO_STOP);

  Serial.println("ESP2 READY");
  logEsp1("ESP2 READY");
}

// ========================= LOOP =========================

void loop() {

  // รับคำสั่ง RESET_FAULT ผ่าน Serial Monitor ได้ตลอดเวลา
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.equalsIgnoreCase("RESET_FAULT")) {
      machineFault = false;
      Serial.println("STATUS:FAULT_CLEARED");
      servoHome();
      motorHome();
    }
  }

  String message = receiveEsp1();

  // รับคำสั่ง RESET_FAULT จาก ESP1 (ส่งต่อมาจาก Pi5)
  if (message.equalsIgnoreCase("RESET_FAULT")) {
    machineFault = false;
    logEsp1("STATUS:FAULT_CLEARED");
    Serial.println("STATUS:FAULT_CLEARED (from ESP1/Pi5)");
    servoHome();
    motorHome();
    return;
  }

  if (machineFault) {
    // ค้างรอผู้ดูแลตรวจสอบก่อน ไม่ประมวลผลข้อความอื่นต่อ
    delay(200);
    return;
  }

  if (message.length() > 0) {

    // 1. รับชนิดขวด
    if (message.startsWith("TYPE:")) {

      bottleType = message.substring(5);
      bottleType.trim();

      logEsp1("TYPE=" + bottleType);
    }

    // 2. ESP1 แจ้งว่าขวดอยู่ในตะกร้าแล้ว (ตอนนี้ส่งมาแบบไม่มีข้อมูลแนบ)
    else if (message.startsWith("GATE_DONE")) {

      String targetName;
      int targetLimitPin;

      // 3. หา BIN เป้าหมาย
      if (!getTarget(bottleType,
                     targetName,
                     targetLimitPin)) {

        sendEsp1("ERROR:NO_VALID_TYPE");
        bottleType = "";
        return;
      }

      logEsp1("TARGET=" + targetName);

      // 4. เลื่อนตะกร้าไปเหนือถัง
      if (!motorToBin(targetLimitPin)) {

        sendEsp1("ERROR:MOTOR_FORWARD");

        motorHome();
        bottleType = "";
        return;
      }

      // 5. เปิดฝาก้นตะกร้าจนสุดลิมิต แล้ว "ค้างไว้" ที่ตำแหน่งเปิด
      //    (servoOpen() หยุดที่ SERVO_STOP ทันทีที่ลิมิตกด ไม่หมุนกลับเอง)
      if (!servoOpen()) {

        sendEsp1("ERROR:SERVO_OPEN");

        motorHome();
        bottleType = "";
        return;
      }

      // 6. ฝาเปิดค้างอยู่ -> สั่ง ESP3 เฝ้ารอ IR ทั้ง 3 ถัง ว่าขวดตกถังไหนจริง
      // ล้างข้อมูลเก่าที่ตกค้างใน uart_esp3 buffer ก่อนส่งคำสั่ง
      while (uart_esp3.available()) uart_esp3.read();

      logEsp1("ACTION:DROP_CHECK:START:" + targetName);
      sendEsp3("DROP_CHECK:" + targetName);
      String dropStatus = waitEsp3Drop(targetName);

      if (dropStatus == "NONE") {
        // แม้ไม่พบสัญญาณ IR (ขวดอาจใสมาก หรือเซนเซอร์ยังไม่ได้ติดตั้ง)
        // ต้องปิดฝาและถอยมอเตอร์กลับ Home เสมอ เพื่อไม่ให้กลไกค้างคาอยู่กลางตู้
        logEsp1("WARNING:DROP_NOT_DETECTED - ตรวจไม่พบขวดตกผ่าน IR ถัง");
        Serial.println("WARNING: ไม่พบขวดตกถัง ดำเนินการปิดฝาและกลับ Home ตามปกติ");
      } else if (dropStatus == "ERROR") {
        logEsp1("ACTION:DROP_CHECK:ไม่สำเร็จ (ESP3_ERROR)");
      } else if (dropStatus == "TIMEOUT") {
        logEsp1("ACTION:DROP_CHECK:ไม่สำเร็จ (ไม่ได้รับคำตอบจาก ESP3)");
      } else if (dropStatus.startsWith("MISMATCH:")) {
        // ขวดตกถังอื่นที่ไม่ใช่เป้าหมาย
        logEsp1("ACTION:DROP_CHECK:สำเร็จบางส่วน (ตกผิดถัง " + dropStatus.substring(9) + ")");
        targetName = dropStatus.substring(9);
      } else if (dropStatus == "OK") {
        logEsp1("ACTION:DROP_CHECK:สำเร็จ (ตกถูกถัง " + targetName + ")");
      }

      // 7. ยืนยันแล้ว -> ปิดฝาก้นตะกร้ากลับด้วยลิมิต Home
      if (!servoHome()) {
        sendEsp1("ERROR:SERVO_HOME");
        motorHome();
        bottleType = "";
        return;
      }

      // 8. หมุนมอเตอร์ 12V กลับจนชนลิมิตถังแรก (Home)
      if (!motorHome()) {
        sendEsp1("ERROR:MOTOR_HOME");
        bottleType = "";
        return;
      }

      // 9. หลังกลับ Home แล้ว ค่อยขอระดับความจุถังทั้ง 3 จาก ESP3 (อัลตราโซนิก)
      // ล้าง buffer เก่าก่อน
      while (uart_esp3.available()) uart_esp3.read();

      logEsp1("ACTION:CHECK_LEVEL:START");
      sendEsp3("CHECK_LEVEL");
      String levelResult = waitEsp3Level();

      if (levelResult.indexOf("UNKNOWN") >= 0) {
        // ไม่ได้รับคำตอบจริงจาก ESP3 (timeout/error)
        logEsp1("ACTION:CHECK_LEVEL:ไม่สำเร็จ (ไม่ได้รับคำตอบจาก ESP3)");
      } else {
        logEsp1("ACTION:CHECK_LEVEL:สำเร็จ (" + levelResult + ")");
      }

      // 10. รวมผลแล้วส่งกลับ ESP1 (มีชนิดขวด/บิน/สถานะ Drop/ระดับถังครบ)
      String result = "DROP=" + dropStatus +
                       ",BIN=" + targetName +
                       "," + levelResult;

      sendEsp1("SORT_DONE:" + result);

      bottleType = "";
    }
  }

  delay(10);
}
