#!/bin/bash
# ========================================================
# 1-Click Autostart Setup for Raspberry Pi 5
# ========================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
START_SCRIPT="$PROJECT_DIR/start_kiosk.sh"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/ecocycle_kiosk.desktop"

echo "=========================================="
echo "  EcoCycle Pro - Auto-Start Setup (Pi 5)  "
echo "=========================================="
echo ""

# 1. Give execute permission to start script
chmod +x "$START_SCRIPT"
echo "[✓] กำหนดสิทธิ์รันให้ $START_SCRIPT"

# 2. XDG Desktop Autostart (~/.config/autostart) - วิธีหลักมาตรฐาน
mkdir -p "$AUTOSTART_DIR"
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Type=Application
Name=EcoCycle Pro Kiosk
Comment=Start EcoCycle Pro Kiosk automatically on boot
Exec=$START_SCRIPT
Path=$PROJECT_DIR
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF
chmod +x "$DESKTOP_FILE"
echo "[✓] ติดตั้ง Desktop Autostart: $DESKTOP_FILE"

# 3. ล้างการตั้งค่าซ้ำซ้อนจาก labwc / wayfire เพื่อป้องกันเปิด 2 หน้าต่าง
LABWC_AUTOSTART="$HOME/.config/labwc/autostart"
if [ -f "$LABWC_AUTOSTART" ]; then
    sed -i '/start_kiosk.sh/d' "$LABWC_AUTOSTART"
fi

WAYFIRE_INI="$HOME/.config/wayfire.ini"
if [ -f "$WAYFIRE_INI" ]; then
    sed -i '/ecocycle_kiosk/d' "$WAYFIRE_INI"
fi
echo "[✓] ป้องกันการเปิดหน้าต่างซ้ำซ้อนเรียบร้อย"

# 4. Check user dialout & video permissions
echo ""
echo "[i] ตรวจสอบสิทธิ์การใช้งานพอร์ต USB และกล้อง..."
USER_GROUPS=$(groups 2>/dev/null || echo "")

NEED_GROUP=0
if [[ ! "$USER_GROUPS" =~ "dialout" ]]; then
    echo "    - เพิ่มสิทธิ์ '$USER' เข้ากลุ่ม dialout (ESP32 Serial)"
    sudo usermod -a -G dialout "$USER" 2>/dev/null || true
    NEED_GROUP=1
fi

if [[ ! "$USER_GROUPS" =~ "video" ]]; then
    echo "    - เพิ่มสิทธิ์ '$USER' เข้ากลุ่ม video (Camera)"
    sudo usermod -a -G video "$USER" 2>/dev/null || true
    NEED_GROUP=1
fi

echo ""
echo "=========================================="
echo "  ติดตั้งระบบ Auto-Start เรียบร้อยแล้ว!    "
echo "=========================================="
echo "ระบบจะเปิดหน้าจอคีออส 1 หน้าต่างเต็มจอทันทีที่เปิดเครื่อง"
