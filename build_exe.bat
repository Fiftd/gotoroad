@echo off
rem Build the game exe with PyInstaller (Windows).  Result: dist\<name>\<name>.exe
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] installing pyinstaller, pygame, pillow ...
py -m pip install --upgrade pyinstaller pygame pillow
if errorlevel 1 goto fail
echo [2/2] building ...
py -m PyInstaller --noconfirm --clean gotoroad.spec
if errorlevel 1 goto fail
echo.
echo Done. Open the folder in dist\ and run the exe.
explorer dist
pause
exit /b 0
:fail
echo.
echo BUILD FAILED - see the messages above.
pause
exit /b 1
