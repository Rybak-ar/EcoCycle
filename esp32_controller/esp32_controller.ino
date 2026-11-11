#include <Arduino.h>
#include "HX711.h"
#include <ESP32Servo.h>

// ==========================================
// การตั้งค่าขา (Pins) ของ ESP32
// ==========================================
// 1. โมดูลชั่งน้ำหนัก (HX711)
const int LOADCELL_DOUT_PIN = 21;
const int LOADCELL_SCK_PIN = 22;

// 2. เซอร์โวมอเตอร์ (ใช้คัดแยกขวด)
const int SERVO_PIN = 18;

// ==========================================
// ตัวแปรและออบเจ็กต์
// ==========================================
HX711 scale;
Servo sorterServo;

// ค่า Calibration Factor
// *** ต้องปรับค่านี้ใหม่ตอนนำตุ้มน้ำหนักมาตรฐานมาทดสอบ ***
float calibration_factor = 420.0; 

void setup() {
  // ตั้งค่า Baud Rate ให้ตรงกับฝั่ง Python (115200)
  Serial.begin(115200);
  
  // ตั้งค่า Load Cell
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  scale.set_scale(calibration_factor);
  scale.tare(); // เซ็ตน้ำหนักให้เป็น 0 เมื่อเปิดเครื่อง
  
  // ตั้งค่า Servo Motor
  sorterServo.attach(SERVO_PIN);
  sorterServo.write(90); // หมุนไปที่ตำแหน่งเริ่มต้น (จุดพัก)
  
  Serial.println("ESP32 Ready");
}

void loop() {
  // ----------------------------------------------------
  // 1. อ่านค่าน้ำหนักและส่งให้ Raspberry Pi (ส่งทุกๆ 300 ms)
  // ----------------------------------------------------
  static unsigned long last_print = 0;
  if (millis() - last_print > 300) {
    if (scale.is_ready()) {
      float weight = scale.get_units(5); // อ่านค่าเฉลี่ย 5 ครั้ง
      
      // ลบค่าติดลบเล็กน้อยที่เกิดจากสัญญาณรบกวนให้เป็น 0
      if (weight < 2.0 && weight > -2.0) {
        weight = 0.0;
      }

      // พิมพ์ส่งกลับไปให้ Python
      // Python ใช้ Regex ดักตัวเลขไว้แล้ว ดังนั้นพิมพ์ข้อความแทรกได้เลย
      Serial.print("Weight = ");
      Serial.print(weight);
      Serial.println(" g");
    }
    last_print = millis();
  }

  // ----------------------------------------------------
  // 2. รอรับคำสั่งชนิดขวดจาก Raspberry Pi (Python)
  // ----------------------------------------------------
  if (Serial.available() > 0) {
    // อ่านข้อความที่ Python ยิงมา (เช่น "clear\n")
    String bottleType = Serial.readStringUntil('\n');
    bottleType.trim(); // ตัดช่องว่างและตัวอักษรขยะทิ้ง
    
    if (bottleType.length() > 0) {
      Serial.print("Received Type: ");
      Serial.println(bottleType);
      
      // คัดแยกขวดแต่ละประเภท
      if (bottleType == "clear") {
        // หมุนเซอร์โวปัดขวดใส (เช่น 45 องศา)
        sorterServo.write(45);
        delay(2000); // หน่วงเวลาให้ขวดตกลงไป
        sorterServo.write(90); // กลับจุดพัก
      } 
      else if (bottleType == "opaque") {
        // หมุนเซอร์โวปัดขวดขุ่น (เช่น 135 องศา)
        sorterServo.write(135);
        delay(2000);
        sorterServo.write(90);
      } 
      else if (bottleType == "brown") {
        // หมุนเซอร์โวปัดขวดสีชา (เช่น 180 องศา)
        sorterServo.write(180);
        delay(2000);
        sorterServo.write(90);
      }
      
      // หลังจากคัดแยกขวดเสร็จ อาจจะมีการกระเพื่อมของเครื่องชั่ง
      // ให้ Tare เครื่องชั่งใหม่เพื่อความชัวร์ (ถ้าจำเป็น)
      // scale.tare(); 
    }
  }
}
