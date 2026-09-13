@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 手机/平板局域网访问模式：服务监听所有网卡（本机使用请双击「启动.bat」）
set IELTS_HOST=0.0.0.0
echo [模式] 已开启局域网访问。手机连同一 WiFi 后，用浏览器访问下方窗口中显示的「局域网访问」地址。
echo.
call "启动.bat"
