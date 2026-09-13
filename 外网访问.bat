@echo off
chcp 65001 >nul
title 雅思工作台 · 外网访问
cd /d "%~dp0"

echo [1/2] 检查本地服务...
curl.exe -s -o nul http://127.0.0.1:8000/api/stats
if errorlevel 1 (
    echo 本地服务未启动，先启动服务...
    start "雅思工作台" /min cmd /c "启动.bat"
    timeout /t 8 /nobreak >nul
)

echo [2/2] 建立外网隧道...
echo.
echo  稍等几秒，下方会出现一个 https://xxxx.trycloudflare.com 地址
echo  把这个地址发到手机/其他电脑的浏览器即可访问
echo  注意：本窗口要保持开启，关掉隧道就断了；每次启动地址会变
echo  注意：链接谁拿到谁能访问，请勿外传
echo.
tools\cloudflared.exe tunnel --url http://127.0.0.1:8000
pause
