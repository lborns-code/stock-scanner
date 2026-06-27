@echo off
chcp 65001 >nul
echo מריץ Stock Scanner...
python main.py --now %*
pause
