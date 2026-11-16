#!/bin/bash
# Checks the Cube's hardware and service, in plain words:  sudo bash setup/check.sh
ok()   { echo "  OK    $1"; }
bad()  { echo "  FIX   $1"; }
echo "Galaxy Cube check"
if i2cdetect -y 1 2>/dev/null | grep -q "3c"; then ok "Screen found (I2C 0x3c)"; else bad "Screen not found: check VCC/GND/SDA/SCL (spec §3)"; fi
if aplay -l 2>/dev/null | grep -qi "usb"; then ok "USB headset adapter found"; else echo "  --    No USB headset adapter (fine if you use the built-in speaker)"; fi
if aplay -l 2>/dev/null | grep -qi "voicehat\|i2s"; then ok "Built-in speaker/mic (I2S) found"; else bad "Built-in speaker/mic not found: check the I2S wires and reboot"; fi
if [ -x /opt/galaxy-cube/phantom-linux-arm8 ]; then ok "Phantom (console broadcast) installed"; else bad "Phantom missing: run setup/install.sh again"; fi
if [ -s /var/lib/galaxy-cube/token ]; then ok "Linked to an account"; else echo "  --    Not linked yet (the screen shows a code)"; fi
if systemctl is-active --quiet galaxy-cube; then ok "Cube program is running"; else bad "Cube program isn't running: sudo journalctl -u galaxy-cube -n 30"; fi
if nmcli -t -f NAME,TYPE con show --active 2>/dev/null | grep -v cube-setup | grep -q wireless; then ok "On Wi-Fi"; else bad "Not on Wi-Fi: Menu > Settings > Wi-Fi"; fi
