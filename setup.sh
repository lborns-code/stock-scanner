#!/bin/bash
# Lior's Stock Scanner — Linux/Mac Setup

set -e
echo ""
echo "══════════════════════════════════════"
echo "   LIOR'S STOCK SCANNER — SETUP V3"
echo "══════════════════════════════════════"
echo ""

# Python check
if ! command -v python3 &> /dev/null; then
    echo "[!] Python3 לא נמצא. התקן מ: https://www.python.org"
    exit 1
fi
echo "[OK] Python: $(python3 --version)"

# Install packages
echo ""
echo "[1/3] מתקין חבילות..."
pip3 install -r requirements.txt -q
echo "[OK] חבילות מותקנות"

# API Key
echo ""
echo "[2/3] הכנסת API Key"
echo "      קבל מ: https://console.anthropic.com/keys"
read -p "      הדבק API Key: " API_KEY

if [ -n "$API_KEY" ]; then
    python3 -c "
import json
with open('config.json', 'r', encoding='utf-8') as f:
    c = json.load(f)
c['anthropic_api_key'] = '$API_KEY'
with open('config.json', 'w', encoding='utf-8') as f:
    json.dump(c, f, ensure_ascii=False, indent=2)
print('   [OK] API Key נשמר')
"
fi

# Init DB
echo ""
echo "[3/3] מאתחל מסד נתונים..."
python3 -c "from agents.database import init_db; init_db()"
echo "[OK] מסד נתונים מוכן"

echo ""
read -p "להריץ דוח דמו עכשיו לבדיקה? (y/n): " RUN_DEMO
if [ "$RUN_DEMO" = "y" ]; then
    python3 main.py --demo
fi

echo ""
echo "══════════════════════════════════════"
echo "   הסטאפ הושלם!"
echo ""
echo "   פקודות:"
echo "   python3 main.py --demo    # דוח דמו"
echo "   python3 main.py --now     # סריקה אמיתית"
echo "   python3 main.py           # אוטומטי 06:30+20:00"
echo "══════════════════════════════════════"
