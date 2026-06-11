@echo off
REM Lean CLV snapshot (h2h, eu region ~4 the-odds-api credits).
REM Registered as Windows Task "TennisCLVSnapshot" (every 6h). Remove with:
REM   schtasks /delete /tn "TennisCLVSnapshot" /f
cd /d "G:\tennis betting"
set PYTHONUTF8=1
"C:\Users\Utente\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe" -X utf8 -m src.data.scraper --snapshot --lean >> "G:\tennis betting\data\live\snapshot_cron.log" 2>&1
