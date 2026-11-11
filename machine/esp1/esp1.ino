// ============================================================
// ESP1 - Main Controller (Standalone, Production-Ready)
// Arduino IDE 1.8.19 + ESP32 Core 3.0.2
// หน้าที่: ชั่งน้ำหนัก, รับชนิดขวดจาก Serial Monitor/คอมพิวเตอร์
// (ไม่ต้องใช้ Raspberry Pi) ควบคุม Servo 1/2/3 และส่งงานให้ ESP2
//
// สิ่งที่ปรับจากเวอร์ชันเดิม (STANDALONE_FIXED):
// 1. ค่าคาลิเบรทเครื่องชั่ง (scale_val / correction) บันทึกลง
//    NVS (Preferences) จะได้ไม่ต้องคาลิเบรทใหม่ทุกครั้งที่รีสตาร์ท
// 2. เพิ่มคำสั่ง Serial: CAL:<น้ำหนักจริงกรัม>, TARE, STATUS, HELP
// 3. เช็คผลลัพธ์ของ gate3Close()/gate1Close()/gate2RejectCycle()
//    จริงจัง ถ้าประตูปิดไม่สนิท (limit switch timeout) จะไม่ส่ง
//    งานต่อให้ ESP2 แบบเงียบๆ อีกต่อไป แต่จะแจ้งเตือนและรอให้
//    ผู้ดูแลตรวจสอบก่อน
// 4. อ่านน้ำหนักแบบเฉลี่ยหลายครั้ง (ลด noise ของ HX711)
// 5. เช็ค HX711 ตอนบูตว่าอ่านค่าได้จริงหรือไม่ ก่อนประกาศ READY
// 6. ไม่ recalibrate ทับถ้าขวดยังไม่ถูกยกออกจากตาชั่งจริง
//
// หมายเหตุ: ยืนยันสายจริงแล้วว่า ESP1<->ESP2 ใช้ GPIO18/19
// (ส่วน ESP2<->ESP3 ใช้ GPIO16/17 แยกกันคนละคู่ ไม่ชนกัน)
// ตรงกับที่ตั้งไว้ในไฟล์ ESP2_NEW.ino (ESP1_RX=18, ESP1_TX=19)
// ============================================================

#include <Arduino.h>
#include <math.h>
#include <ESP32Servo.h>
#include <Preferences.h>

// ========================= PINOUT ESP1 =========================
#define SERVO1_PIN          23 // ประตูบานพับ (Door) - เปิดทางให้ขวดลงตะกร้า
#define SERVO2_PIN          13 // คัดแยกของโกง (Reject)
#define SERVO3_PIN          12 // ฐานดีด/ก้านผลัก (Base Pusher) - ผลักขวดผ่านประตู

#define HX711_DOUT           4
#define HX711_SCK            5

#define IR_PIN              21

// ยืนยันสายจริงแล้ว: ESP1<->ESP2 ใช้ GPIO18/19
#define UART_ESP2_RX        18
#define UART_ESP2_TX        19

#define SERVO2_LIMIT_HOME   15
#define SERVO3_LIMIT_HOME   25 // ย้ายจาก GPIO18 (ชนกับ UART_ESP2_RX ใหม่)

// ========================= CONFIG =========================
#define UART_BAUD 115200

// กำหนดทิศทางของ Servo (Continuous)
const int SERVO_STOP = 90;
const int SERVO_FORWARD = 0;
const int SERVO_HOME = 180;

// ความเร็วปิด Gate1 (ใช้ SERVO_HOME = 180 เต็มแรงบิดให้ประตูปิดสนิท)
const int GATE1_CLOSE_SPEED = 180;

const unsigned long STABLE_TIME_MS = 600;
const unsigned long IR_WAIT_TIMEOUT_MS = 2500;
const unsigned long LIMIT_TIMEOUT_MS = 5000;
const unsigned long SETTLE_WAIT_MS = 800;       // หน่วงเวลา 800ms ให้ประตูเปิดสุดและนิ่งสนิท 100% ก่อนก้านผลักทำงาน
const unsigned long GATE1_OPEN_TIME_MS = 1800;  // เปิดประตูกว้างเต็มที่ 1800ms ให้เปิดกว้างสุดจนสุดระยะ
const unsigned long GATE1_CLOSE_TIME_MS = 1800; // ปิดประตูกลับตำแหน่งเดิม 1800ms ให้ประตูปิดสนิท
const unsigned long GATE3_FORWARD_TIME_MS = 1000; // ดีด/ดันขวดไปข้างหน้า 1000ms ให้ขวดพ้นบานประตูลงตะกร้า
const unsigned long REJECT_FORWARD_TIME_MS = 900;
const unsigned long BOTTLE_DROP_PAUSE_MS = 800; // หน่วงเวลาหลังก้านผลักดันขวด ให้ขวดหล่นลงตะกร้าสนิทก่อนดึงก้านกลับ
const unsigned long GATE1_AFTER_CLOSE_WAIT_MS = 500;
const unsigned long BOTTLE_REMOVE_TIMEOUT_MS = 10000;
const unsigned long HX711_BOOT_CHECK_TIMEOUT_MS = 2000;

const float ZERO_WEIGHT = 10.0; // เกณฑ์ตรวจจับตาชั่ง (กรัม) สำหรับขวดขั้นต่ำ 10.0g (ตรงกับ Python AI Detector)
const float EMPTY_BOTTLE_MAX_WEIGHT = 800.0; // รองรับขวดแก้ว/ขวดสีชา (120-300g), ขวดลิตร และแรงกระแทกตอนวาง ไม่ให้เตือน CHEAT_WEIGHT
const int WEIGHT_SAMPLES = 8; // จำนวนครั้งที่อ่านมาเฉลี่ยกันต่อ 1 ค่า

// ---- ค่าคาลิเบรท (ค่าเริ่มต้น จะถูกโหลดทับจาก NVS ถ้ามีการเคยคาลิเบรทไว้) ----
float scale_val = 409.0;
float correction = 1.0;
long offset = 0;

Preferences prefs;
HardwareSerial uart_esp2(2);

Servo servo1;
Servo servo2;
Servo servo3;

unsigned long bottleStartTime = 0;
bool bottleDetected = false;

// เก็บชนิดขวดที่ Pi5 ส่งมาล่วงหน้า (เผื่อ Pi5 ตรวจจับด้วยกล้องเสร็จก่อนขวดขึ้นตาชั่ง/ก่อนชั่งเสร็จ)
String pendingBottleType = "";
unsigned long lastWeightPrint = 0;
unsigned long negativeDriftStart = 0;

bool machineFault = false; // true เมื่อกลไกค้าง ต้องให้คนตรวจก่อนทำงานต่อ

// ========================= COMMUNICATION =========================

void sendStatus(const String &message) {
  Serial.println(message);
}

void sendEsp2(const String &message) {
  uart_esp2.print(message);
  uart_esp2.print('\n');
  Serial.println("ESP1 -> ESP2: " + message);
}

void logStatus(const String &text) {
  sendStatus("LOG:ESP1:" + text);
}

String receiveTypeCommand() {
  if (!Serial.available()) return "";
  String message = Serial.readStringUntil('\n');
  message.trim();
  return message;
}

String receiveEsp2Message() {
  if (!uart_esp2.available()) return "";
  String message = uart_esp2.readStringUntil('\n');
  message.trim();

  if (message.length() > 0) {
    Serial.println("ESP2 -> ESP1: " + message);
  }

  return message;
}

String parseBottleType(String msg) {
  msg.trim();

  if (msg.startsWith("TYPE:")) {
    msg = msg.substring(5);
    msg.trim();
  }

  msg.toLowerCase();

  if (msg == "brown") return "colored";
  if (msg == "clear") return "clear";
  if (msg == "colored") return "colored";
  if (msg == "opaque") return "opaque";

  return "";
}

// ========================= CALIBRATION (NVS) =========================

void loadCalibration() {
  prefs.begin("esp1cal", true); // read-only
  scale_val = prefs.getFloat("scale_val", scale_val);
  correction = prefs.getFloat("correction", correction);
  prefs.end();
}

void saveCalibration() {
  prefs.begin("esp1cal", false); // read-write
  prefs.putFloat("scale_val", scale_val);
  prefs.putFloat("correction", correction);
  prefs.end();
}

// ========================= HX711 =========================

long hx711ReadRaw() {
  unsigned long waitStart = millis();

  while (digitalRead(HX711_DOUT) == HIGH) {
    if (millis() - waitStart > 1000) {
      return offset; // HX711 ไม่ตอบสนอง คืนค่าเดิมกันค้าง
    }
  }

  long value = 0;

  for (int i = 0; i < 24; i++) {
    digitalWrite(HX711_SCK, HIGH);
    delayMicroseconds(1);

    value = value << 1;

    digitalWrite(HX711_SCK, LOW);
    delayMicroseconds(1);

    if (digitalRead(HX711_DOUT)) {
      value++;
    }
  }

  // Pulse ที่ 25 เพื่อเลือก Gain 128
  digitalWrite(HX711_SCK, HIGH);
  delayMicroseconds(1);
  digitalWrite(HX711_SCK, LOW);
  delayMicroseconds(1);

  // แปลงค่า signed 24-bit
  if (value & 0x800000) {
    value |= 0xFF000000;
  }

  return value;
}

// อ่านค่าเฉลี่ยหลายครั้งเพื่อลด noise
long hx711ReadAveraged(int samples) {
  long total = 0;
  int valid = 0;

  for (int i = 0; i < samples; i++) {
    total += hx711ReadRaw();
    valid++;
    delay(2);
  }

  if (valid == 0) return offset;
  return total / valid;
}

bool hx711SelfCheck() {
  unsigned long start = millis();

  while (millis() - start < HX711_BOOT_CHECK_TIMEOUT_MS) {
    if (digitalRead(HX711_DOUT) == LOW) {
      return true; // มีสัญญาณตอบสนอง แปลว่า HX711 ต่ออยู่จริง
    }
    delay(10);
  }

  return false;
}

float readWeight() {
  long raw = hx711ReadAveraged(WEIGHT_SAMPLES);

  float rawDiff = (float)(raw - offset);

  // ป้องกันค่าติดลบกลายเป็นน้ำหนักบวก:
  // หาก rawDiff <= 0 (เช่น ไม่มีของ หรือถาดตาชั่งถูกยก/เด้งขึ้น) 
  // ต้องคืนค่า 0.0g ห้ามใช้ fabs() ที่ทำให้ค่าติดลบกลายเป็นขวดเด็ดขาด!
  if (rawDiff <= 0) {
    return 0.0;
  }

  float weight = (rawDiff / scale_val) * correction;

  if (weight < ZERO_WEIGHT) {
    weight = 0.0;
  }

  return weight;
}

// ฟังก์ชันเซ็ตศูนย์ตาชั่งแบบ Trimmed-Mean กรองแรงสั่นสะเทือนและ noise ทางกล
// ทำงานโดยอ่านค่า 20 ครั้ง ตัดค่าสูงสุด/ต่ำสุดออก แล้วเฉลี่ยเฉพาะค่ากลาง
void performRobustTare() {
  logStatus("ACTION:ROBUST_TARE:START");
  delay(500); // หน่วงเวลารอแรงสั่นสะเทือนกลไกสงบสนิท 100%

  const int NUM_TARE_SAMPLES = 20;
  long samples[NUM_TARE_SAMPLES];

  for (int i = 0; i < NUM_TARE_SAMPLES; i++) {
    samples[i] = hx711ReadRaw();
    delay(4);
  }

  // เรียงลำดับค่าน้อยไปมาก (Bubble sort) เพื่อตัด Outliers
  for (int i = 0; i < NUM_TARE_SAMPLES - 1; i++) {
    for (int j = i + 1; j < NUM_TARE_SAMPLES; j++) {
      if (samples[i] > samples[j]) {
        long temp = samples[i];
        samples[i] = samples[j];
        samples[j] = temp;
      }
    }
  }

  // ตัด 4 ค่าต่ำสุด (0..3) และ 4 ค่าสูงสุด (16..19) ออก
  // นำค่าตรงกลาง 12 ค่า (4..15) มาหาค่าเฉลี่ย
  long sum = 0;
  for (int i = 4; i < 16; i++) {
    sum += samples[i];
  }
  offset = sum / 12;

  logStatus("ACTION:ROBUST_TARE_OK:offset=" + String(offset));
  sendStatus("STATUS:TARE_DONE offset=" + String(offset));

  // ล้างบัฟเฟอร์ Serial ป้องกันคำสั่ง TYPE ตกค้างมาเริ่มรอบใหม่เอง
  while (Serial.available()) {
    Serial.read();
  }
  pendingBottleType = "";
  bottleDetected = false;
  negativeDriftStart = 0;
}

void recalibrateOffset() {
  performRobustTare();
}

void performCycleTare() {
  performRobustTare();
}

// รอจนขวด/วัตถุถูกยกออกจากตาชั่งจริง และนิ่งสนิทก่อนจะ recalibrate
void waitBottleRemovedThenRecalibrate() {
  unsigned long start = millis();
  unsigned long stableZeroStart = 0;

  while (millis() - start < BOTTLE_REMOVE_TIMEOUT_MS) {
    // ส่งข้อมูลน้ำหนักและ IR ต่อเนื่องให้ Pi5
    if (millis() - lastWeightPrint >= 150) {
      int irVal = readIR();
      Serial.print("Weight = ");
      Serial.print(readWeight(), 1);
      Serial.print(" g, IR = ");
      Serial.println(irVal);
      lastWeightPrint = millis();
    }

    // ต้องแน่ใจว่าน้ำหนักลดลงต่ำกว่า ZERO_WEIGHT ต่อเนื่องอย่างน้อย 1.0 วินาทีเต็ม
    // จึงจะมั่นใจได้ว่ามือผู้ใช้ยกขวดออกไปพ้นแล้ว และแรงสั่นสะเทือนกลไกหยุดนิ่งแล้ว
    if (readWeight() < ZERO_WEIGHT) {
      if (stableZeroStart == 0) {
        stableZeroStart = millis();
      } else if (millis() - stableZeroStart >= 1000) {
        delay(200);
        offset = hx711ReadAveraged(WEIGHT_SAMPLES);
        logStatus("ACTION:RECALIBRATE_OK");
        return;
      }
    } else {
      stableZeroStart = 0;
    }
    delay(50);
  }

  logStatus("WARNING:BOTTLE_STILL_ON_SCALE - ไม่ recalibrate เพื่อความปลอดภัย");
  sendStatus("STATUS:WARNING:กรุณายกขวด/วัตถุออกจากตาชั่ง แล้วเครื่องจะคาลิเบรทให้อัตโนมัติ");
}

// ========================= SERVO =========================

void stopServos() {
  servo1.write(SERVO_STOP);
  servo2.write(SERVO_STOP);
  servo3.write(SERVO_STOP);
}

bool limitPressed(int pin) {
  // ทดสอบกับสวิตช์จริงแล้ว: กด = HIGH (INPUT_PULLUP)
  return digitalRead(pin) == HIGH;
}

int readIR() {
  return digitalRead(IR_PIN);
}

// ========================= GATE 1 =========================
// Gate 1 ไม่มี limit switch กำกับ ใช้เวลาคุมเท่านั้น (ตามของเดิม)

bool gate1Open() {
  logStatus("ACTION:Gate1_OPEN:START");

  servo1.write(SERVO_FORWARD);
  delay(GATE1_OPEN_TIME_MS);
  servo1.write(SERVO_STOP);

  logStatus("ACTION:Gate1_OPEN:สำเร็จ");
  return true;
}

bool gate1Close() {
  logStatus("ACTION:Gate1_CLOSE:START");

  servo1.write(GATE1_CLOSE_SPEED); // หมุนช้าลง (เดิมใช้ SERVO_HOME = เต็มสปีด)
  delay(GATE1_CLOSE_TIME_MS);
  servo1.write(SERVO_STOP);

  logStatus("ACTION:Gate1_CLOSE:สำเร็จ");
  return true;
}

// ========================= GATE 2 =========================

bool gate2RejectCycle() {
  logStatus("ACTION:Gate2_REJECT:START");

  servo2.write(SERVO_FORWARD);
  delay(REJECT_FORWARD_TIME_MS);
  servo2.write(SERVO_STOP);

  delay(SETTLE_WAIT_MS);

  unsigned long start = millis();
  servo2.write(SERVO_HOME);

  while (millis() - start < LIMIT_TIMEOUT_MS) {
    if (limitPressed(SERVO2_LIMIT_HOME)) {
      servo2.write(SERVO_STOP);
      logStatus("ACTION:Gate2_REJECT:สำเร็จ");
      return true;
    }
    delay(10);
  }

  // Fallback: หากลิมิตสวิตช์ไม่สัมผัส หรือสายหลุด ให้หยุดเซอร์โวตามเวลา ไม่ล็อกเครื่อง
  servo2.write(SERVO_STOP);
  logStatus("ACTION:Gate2_REJECT:ปิดตามเวลาสำรอง (ไม่ล็อกระบบ)");
  return true;
}

// ========================= GATE 3 =========================

bool gate3Open() {
  logStatus("ACTION:Gate3_OPEN:START");

  servo3.write(SERVO_FORWARD);
  delay(GATE3_FORWARD_TIME_MS);
  servo3.write(SERVO_STOP);

  logStatus("ACTION:Gate3_OPEN:สำเร็จ");
  return true;
}

bool gate3Close() {
  logStatus("ACTION:Gate3_CLOSE:START");

  unsigned long start = millis();
  servo3.write(SERVO_HOME);

  // รอลิมิตสวิตช์แตะ (ปกติหมุนปิดใช้เวลาประมาณ 600-800ms)
  while (millis() - start < 1200) {
    if (limitPressed(SERVO3_LIMIT_HOME)) {
      servo3.write(SERVO_STOP);
      logStatus("ACTION:Gate3_CLOSE:สำเร็จ (สวิตช์แตะ)");
      return true;
    }
    delay(10);
  }

  // Fallback: หากลิมิตสวิตช์ไม่สัมผัส หรือสายหลุด ให้หยุดเซอร์โวตามเวลา ไม่ล็อกเครื่อง
  servo3.write(SERVO_STOP);
  logStatus("ACTION:Gate3_CLOSE:ปิดตามเวลาสำรอง (ไม่ล็อกระบบ)");
  return true;
}

// ========================= WAIT ESP2 =========================

String waitEsp2SortDone() {
  unsigned long start = millis();

  while (millis() - start < 20000) {
    String message = receiveEsp2Message();

    if (message.length() == 0) {
      delay(10);
      continue;
    }

    if (message.startsWith("LOG:")) {
      sendStatus(message);
      continue;
    }

    if (message.startsWith("SORT_DONE:")) {
      return message.substring(10);
    }

    if (message.startsWith("ERROR:")) {
      return message;
    }
  }

  return "ERROR:ESP2_TIMEOUT";
}

// ========================= SERIAL COMMANDS (CAL / TARE / STATUS) =========================
// คืนค่า true ถ้าข้อความนี้ถูกจัดการเป็นคำสั่งระบบไปแล้ว (ไม่ใช่ TYPE:)

bool handleSystemCommand(const String &msgIn) {
  String msg = msgIn;
  msg.trim();

  if (msg.equalsIgnoreCase("TARE")) {
    recalibrateOffset();
    sendStatus("STATUS:TARE_DONE offset=" + String(offset));
    return true;
  }

  if (msg.equalsIgnoreCase("STATUS")) {
    sendStatus("STATUS:scale_val=" + String(scale_val, 3) +
               " correction=" + String(correction, 3) +
               " offset=" + String(offset) +
               " fault=" + String(machineFault ? "1" : "0"));
    return true;
  }

  if (msg.equalsIgnoreCase("RESET_FAULT")) {
    machineFault = false;
    sendEsp2("RESET_FAULT");
    sendStatus("STATUS:FAULT_CLEARED");
    return true;
  }

  if (msg.equalsIgnoreCase("HELP")) {
    sendStatus("STATUS:CMDS: TYPE:clear|colored|brown|opaque , CAL:<known_weight_g> , TARE , STATUS , RESET_FAULT");
    return true;
  }

  if (msg.startsWith("CAL:")) {
    float knownWeight = msg.substring(4).toFloat();

    if (knownWeight <= 0) {
      sendStatus("STATUS:ERROR:CAL_INVALID_WEIGHT");
      return true;
    }

    sendStatus("STATUS:กำลังคาลิเบรท วางน้ำหนักมาตรฐาน " + String(knownWeight, 1) + " g บนตาชั่งแล้วรอ...");
    delay(1000);

    long raw = hx711ReadAveraged(WEIGHT_SAMPLES * 2);
    float rawDiff = (float)(raw - offset);

    if (fabs(rawDiff) < 1.0) {
      sendStatus("STATUS:ERROR:CAL_NO_WEIGHT_DETECTED");
      return true;
    }

    scale_val = fabs(rawDiff) / knownWeight;
    correction = 1.0;

    saveCalibration();

    sendStatus("STATUS:CAL_DONE scale_val=" + String(scale_val, 3));
    return true;
  }

  return false;
}

// ========================= SETUP =========================

void setup() {
  Serial.begin(UART_BAUD);
  Serial.setTimeout(50);

  pinMode(HX711_DOUT, INPUT);
  pinMode(HX711_SCK, OUTPUT);
  digitalWrite(HX711_SCK, LOW);

  pinMode(IR_PIN, INPUT_PULLUP);
  pinMode(SERVO2_LIMIT_HOME, INPUT_PULLUP);
  pinMode(SERVO3_LIMIT_HOME, INPUT_PULLUP);

  uart_esp2.begin(UART_BAUD, SERIAL_8N1, UART_ESP2_RX, UART_ESP2_TX);
  uart_esp2.setTimeout(50);

  servo1.attach(SERVO1_PIN);
  servo2.attach(SERVO2_PIN);
  servo3.attach(SERVO3_PIN);

  stopServos();

  loadCalibration();

  Serial.println("\n==================================");
  Serial.println("   ESP1 READY - STANDALONE MODE   ");
  Serial.println("==================================");

  if (!hx711SelfCheck()) {
    Serial.println("!!! WARNING: ไม่พบสัญญาณตอบสนองจาก HX711 (เช็คสาย DOUT/SCK) !!!");
    logStatus("WARNING:HX711_NOT_RESPONDING");
  }

  delay(300);
  offset = hx711ReadAveraged(WEIGHT_SAMPLES);

  Serial.println("scale_val=" + String(scale_val, 3) + " correction=" + String(correction, 3));
  Serial.println("พิมพ์ HELP เพื่อดูคำสั่งทั้งหมด");

  logStatus("ESP1 READY - STANDALONE WITH ESP32SERVO");
}

// ========================= LOOP =========================

void loop() {
  float weight = readWeight();

  // Auto-Zero Tracking & Anti-Stuck Weight:
  // แก้ไขปัญหา drift ของตาชั่งตอนไม่มีขวด (เช่น ค้าง 0.8g ถึง 6.0g) 
  // หากมีน้ำหนักเกิน 6.0g หรือมีขวดวางอยู่ ห้าม Auto-Tare เด็ดขาด!
  if (!bottleDetected && pendingBottleType.length() == 0 && weight > 0.8 && weight < 6.0) {
    if (negativeDriftStart == 0) {
      negativeDriftStart = millis();
    } else if (millis() - negativeDriftStart >= 3000) {
      logStatus("ACTION:AUTO_ZERO_FIX_DRIFT:weight=" + String(weight, 1) + "g");
      performRobustTare();
      negativeDriftStart = 0;
    }
  } else {
    negativeDriftStart = 0;
  }

  // ส่งข้อมูลน้ำหนักและสถานะเซนเซอร์ IR ประตูอย่างต่อเนื่องให้ Pi5 (ทุก 150ms)
  if (millis() - lastWeightPrint >= 150) {
    int irVal = readIR();
    Serial.print("Weight = ");
    Serial.print(weight, 1);
    Serial.print(" g, IR = ");
    Serial.println(irVal);
    lastWeightPrint = millis();
  }

  // ส่งข้อความจาก ESP2 ต่อไปยังคอมพิวเตอร์
  String esp2Message = receiveEsp2Message();
  if (esp2Message.length() > 0) {
    sendStatus(esp2Message);
  }

  // รับคำสั่งระบบ (CAL / TARE / STATUS / HELP) ได้ตลอดเวลา แม้ไม่มีขวด
  // และรับชนิดขวดจาก Pi5 ล่วงหน้าไว้ก่อน เผื่อ Pi5 ส่งมาก่อนขวดขึ้นตาชั่ง/ชั่งเสร็จ
  if (Serial.available()) {
    String cmd = receiveTypeCommand();

    if (cmd.length() > 0) {
      String earlyType = parseBottleType(cmd);

      if (earlyType.length() > 0) {
        pendingBottleType = earlyType;
        Serial.println("รับชนิดขวดล่วงหน้าจาก Pi5: " + pendingBottleType);
      } else if (handleSystemCommand(cmd)) {
        return;
      }
    }
  }

  if (machineFault) {
    // เครื่องค้างจากรอบก่อน ต้องพิมพ์ RESET_FAULT หลังตรวจสอบกลไกแล้ว
    delay(200);
    return;
  }

  if (weight > ZERO_WEIGHT) {

    if (!bottleDetected) {
      bottleDetected = true;
      bottleStartTime = millis();
      Serial.println("Bottle detected");
    }

    // บังคับให้รอเวลาหน่วงทางกล STABLE_TIME_MS (600ms) ให้แรงสั่นไหวและคลื่นกระแทกสงบสนิทก่อนเสมอ
    if (millis() - bottleStartTime >= STABLE_TIME_MS) {

      float finalWeight = readWeight();

      Serial.print("FINAL WEIGHT = ");
      Serial.print(finalWeight, 1);
      Serial.println(" g");

      // ตรวจน้ำหนักเกิน (สงสัยว่ามีของแอบใส่มา / มีน้ำในขวด)
      if (finalWeight > EMPTY_BOTTLE_MAX_WEIGHT) {
        // หน่วงเวลา 300ms เพื่อตรวจสอบว่าไม่ใช่คลื่นแรงกระแทกจากการวางขวดแรง (Dynamic Impact Shock Wave)
        delay(300);
        float verifyWeight = readWeight();
        if (verifyWeight <= EMPTY_BOTTLE_MAX_WEIGHT) {
          finalWeight = verifyWeight; // แรงกระแทกสลายตัวแล้ว ใช้น้ำหนักจริงที่นิ่งสนิท
          Serial.print("IMPACT SHOCK ABSORBED: SETTLED WEIGHT = ");
          Serial.print(finalWeight, 1);
          Serial.println(" g");
        } else {
          Serial.println("STATUS:CHEAT_WEIGHT:" + String(verifyWeight, 1));
          pendingBottleType = "";

          if (!gate2RejectCycle()) {
            machineFault = true;
            sendStatus("STATUS:FAULT:GATE2_STUCK - กรุณาตรวจสอบกลไก Gate2 แล้วพิมพ์ RESET_FAULT");
            bottleDetected = false;
            return;
          }

          waitBottleRemovedThenRecalibrate();

          bottleDetected = false;
          return;
        }
      }

      String bottleType = "";
      unsigned long waitStart = millis();

      if (pendingBottleType.length() > 0) {
        // Pi5 ส่งชนิดขวดมาให้แล้วล่วงหน้า ใช้ได้เลยไม่ต้องรอ
        bottleType = pendingBottleType;
        pendingBottleType = "";
        Serial.println("ใช้ชนิดขวดที่ Pi5 ส่งมาล่วงหน้า: " + bottleType);
      } else {
        Serial.println("รอชนิดขวดจาก Pi5...");
        Serial.println("(หรือพิมพ์เองผ่าน Serial Monitor: TYPE:clear / TYPE:colored / TYPE:brown / TYPE:opaque)");

        while (bottleType.length() == 0 && millis() - waitStart < 12000) {
          // ส่งข้อมูลน้ำหนักและ IR หล่อเลี้ยง Pi5 ขณะรอตรวจจับ
          if (millis() - lastWeightPrint >= 200) {
            int irVal = readIR();
            Serial.print("Weight = ");
            Serial.print(finalWeight, 1);
            Serial.print(" g, IR = ");
            Serial.println(irVal);
            lastWeightPrint = millis();
          }

          String message = receiveTypeCommand();

          if (message.length() > 0) {

            if (!message.startsWith("TYPE:") && handleSystemCommand(message)) {
              continue;
            }

            bottleType = parseBottleType(message);

            if (bottleType.length() == 0) {
              Serial.println("ชนิดขวดไม่ถูกต้อง");
              Serial.println("ใช้: TYPE:clear, TYPE:colored, TYPE:brown หรือ TYPE:opaque");
            }
          }
          delay(10);
        }
      }

      if (bottleType.length() == 0) {
        Serial.println("STATUS:ERROR:NO_TYPE");
        bottleDetected = false;
        pendingBottleType = "";
        // หากรอจนหมดเวลาแล้วไม่ได้รับชนิดขวดจาก Pi5 แสดงว่าเป็นน้ำหนักค้างตกค้าง
        // ให้ทำการ Tare เซ็ตศูนย์ทันที เพื่อไม่ให้ติดลูปซ้ำ
        performRobustTare();
        return;
      }

      Serial.println("TYPE = " + bottleType);

      sendEsp2("TYPE:" + bottleType);

      // ===== ลำดับการทำงานของกลไกตามที่ผู้ใช้กำหนดอย่างเคร่งครัด =====
      // 1) ประตูเปิดก่อนให้สุด:
      //    สั่งเปิด Gate 1 (Servo 1) เต็มเวลาจนบานประตูเปิดกว้างสุดเต็มที่
      //    แล้วหยุด และหน่วงเวลาให้บานประตูนิ่งสนิท 100%
      gate1Open();
      delay(SETTLE_WAIT_MS);

      // 2) แล้วค่อยให้ฐานดีดขวดลงตะกร้า:
      //    สั่ง Gate 3 (Servo 3) ดันฐาน/ก้านผลักไปข้างหน้าเพื่อดีดขวดลงตะกร้าผ่านประตูที่เปิดอยู่
      logStatus("ACTION:Gate3_OPEN:START");
      unsigned long irStart = millis();
      bool irDetected = false;

      unsigned long g3Start = millis();
      servo3.write(SERVO_FORWARD);
      while (millis() - g3Start < GATE3_FORWARD_TIME_MS) {
        if (readIR() == LOW) {
          irDetected = true;
        }
        delay(5);
      }
      servo3.write(SERVO_STOP);
      logStatus("ACTION:Gate3_OPEN:สำเร็จ (ดีดขวดลงตะกร้าแล้ว)");

      // รอขวดตกผ่านเซนเซอร์ IR (ใต้ช่องปล่อยขวด) หรือหมดเวลา timeout
      while (!irDetected && millis() - irStart < IR_WAIT_TIMEOUT_MS) {
        if (readIR() == LOW) {
          irDetected = true;
        }
        delay(5);
      }

      Serial.print("IR detected = ");
      Serial.println(irDetected ? "YES" : "NO (timeout)");
      sendStatus("STATUS:GATE_IR:" + String(irDetected ? "OK" : "TIMEOUT"));

      if (!irDetected) {
        logStatus("WARNING:IR_NOT_DETECTED - ขวดอาจไม่ตกผ่านช่องตามที่ควร");
      }

      // หน่วงเวลาให้ขวดหล่นลงไปในตะกร้าอย่างสมบูรณ์
      delay(BOTTLE_DROP_PAUSE_MS);

      // 3) จากนั้นค่อยคืนตัวเซอโว:
      //    ก) คืนตัวฐานดีด (Gate 3) กลับเข้าตำแหน่ง Home ก่อน (เช็คชนลิมิตสวิตช์)
      bool gate3Ok = gate3Close();
      delay(300); // รอให้ฐานดีดกลับเข้าที่สนิท

      //    ข) คืนตัวบานประตู (Gate 1) ปิดกลับตำแหน่งเดิมจนสนิท
      bool gate1Ok = gate1Close();
      delay(GATE1_AFTER_CLOSE_WAIT_MS); // รอนิ่งสนิทหลังประตูปิด

      if (!gate3Ok || !gate1Ok) {
        machineFault = true;
        sendStatus("STATUS:FAULT:GATE_NOT_CLOSED - กรุณาตรวจสอบกลไกประตูแล้วพิมพ์ RESET_FAULT");
        bottleDetected = false;
        pendingBottleType = "";
        return;
      }

      // 4) เซ็ตศูนย์ตาชั่ง (Tare) ทันทีหลังเซอร์โวคืนตัวครบทั้งสองตัวและขวดหล่นไปแล้ว!
      //    (ณ จุดนี้ ตะกร้า ESP2 ยังไม่ขยับ ไม่มีแรงสั่นจากมอเตอร์ 12V ตาชั่งว่างเปล่า 100% จึงเซ็ตศูนย์ได้แม่นยำที่สุด)
      performRobustTare();

      // 5) ส่งให้ ESP2 - สั่งเริ่มเลื่อนตะกร้าไปทิ้งขวดลงถัง
      sendEsp2("GATE_DONE");
      String result = waitEsp2SortDone();

      if (result.startsWith("ERROR:")) {
        Serial.println("STATUS:" + result);
      } else {
        Serial.println("STATUS:DONE:" + result);
      }

      // หน่วงเวลาหลังตะกร้า ESP2 วิ่งกลับ Home แล้วตรวจสอบว่ามีแรงกระแทกทำให้ค่าน้ำหนักเบี่ยงเบนหรือไม่
      delay(400);
      float postSortWeight = readWeight();
      if (postSortWeight > 0.0 && postSortWeight < 25.0) {
        // หากมี residual drift จากแรงกระแทกของตะกร้า ESP2 ให้เซ็ตศูนย์ซ้ำอีกครั้ง
        performRobustTare();
      }

      bottleDetected = false;
      pendingBottleType = "";
      Serial.println("READY FOR NEXT BOTTLE");
    }

  } else {
    bottleDetected = false;
  }

  delay(20);
}
