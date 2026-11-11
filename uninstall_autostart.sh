#!/bin/bash
# ========================================================
# Disable Autostart for Raspberry Pi 5 (EcoCycle Pro)
# ========================================================

DESKTOP_FILE="$HOME/.config/autostart/ecocycle_kiosk.desktop"
WAYFIRE_INI="$HOME/.config/wayfire.ini"
LABWC_AUTOSTART="$HOME/.config/labwc/autostart"

[ -f "$DESKTOP_FILE" ] && rm -f "$DESKTOP_FILE" && echo "[✓] ลบ XDG Autostart แล้ว"

if [ -f "$WAYFIRE_INI" ]; then
    sed -i '/ecocycle_kiosk/d' "$WAYFIRE_INI"
    echo "[✓] ลบออกจาก Wayfire config แล้ว"
fi

if [ -f "$LABWC_AUTOSTART" ]; then
    sed -i '/start_kiosk.sh/d' "$LABWC_AUTOSTART"
    echo "[✓] ลบออกจาก labwc config แล้ว"
fi

echo "[✓] ยกเลิกการเปิดโปรแกรมอัตโนมัติเรียบร้อยทั้งหมดแล้ว"
