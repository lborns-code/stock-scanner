@echo off
chcp 65001 >nul
echo.
echo ══════════════════════════════════════
echo   LIOR'S STOCK SCANNER — SETUP V3
echo ══════════════════════════════════════
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python לא נמצא
    echo     הורד מ: https://www.python.org/downloads/
    echo     סמן: Add Python to PATH
    pause & exit /b 1
)
echo [OK] Python נמצא
echo.
echo [1/3] מתקין חבילות...
pip install -r requirements.txt -q
echo [OK] חבילות מותקנות
echo.
echo [2/3] API Key
echo קבל מ: https://console.anthropic.com/keys
set /p KEY=הדבק API Key:
python -c "
import json
with open('config.json', encoding='utf-8') as f:
    c = json.load(f)
c['anthropic_api_key'] = '%KEY%'
with open('config.json', 'w', encoding='utf-8') as f:
    json.dump(c, f, ensure_ascii=False, indent=2)
print('   [OK] API Key נשמר')
"
echo.
echo [3/3] מאתחל מסד נתונים...
python -c "from agents.database import init_db; init_db()"
echo [OK] מסד נתונים מוכן
echo.
set /p DEMO=להריץ דוח דמו עכשיו לבדיקה? (y/n):
if /i "%DEMO%"=="y" python main.py --demo
echo.
echo ══════════════════════════════════════
echo   הסטאפ הושלם!
echo.
echo   פקודות:
echo   python main.py --demo    # דוח דמו
echo   python main.py --now     # סריקה אמיתית
echo   python main.py           # אוטומטי 06:30+20:00
echo ══════════════════════════════════════
pause
