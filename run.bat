@echo off
REM Start the JBS Digital Link prototype.
REM
REM Uncomment these two lines to generate codes against the real domain
REM instead of this machine's LAN address. Do NOT uncomment them until
REM jbs-qr.com actually serves this app - otherwise you will produce codes
REM that look final but resolve to nothing.
REM   set JBS_DL_DOMAIN=jbs-qr.com
REM   set JBS_DL_SCHEME=https

cd /d "%~dp0"
echo Starting JBS Digital Link on http://localhost:8000
echo Admin:  http://localhost:8000/admin/
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
