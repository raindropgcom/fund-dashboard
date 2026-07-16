@echo off
setlocal enabledelayedexpansion
title 基金看板本地常驻(静默)

REM 使用绝对路径，放到任何目录都能找到脚本
set "SCRIPT=E:\AKshare\fund_dashboard_trade.py"
if not exist "%SCRIPT%" (
    echo [错误] 找不到脚本: %SCRIPT%
    pause
    exit /b 1
)

REM 优先用 pythonw（无控制台窗口），回退到普通 python
set "PYW="
for %%P in ("D:\Programs\Python\Python313\pythonw.exe" "D:\Programs\Python\Python313\python.exe" "pythonw" "python") do (
    if exist "%%~P" (
        set "PYW=%%~P"
        goto :found
    )
)
:found
if not defined PYW (
    echo [错误] 找不到 Python，请安装 Python 3 并加入 PATH。
    pause
    exit /b 1
)

echo 使用 Python: %PYW%
echo 启动基金看板本地常驻（默认模式，无限刷新）...
REM 默认模式 = 无限常驻，每 20 秒重写一次 HTML；start 使其独立运行
start "" "%PYW%" "%SCRIPT%"
echo 已在后台启动。本窗口可随意关闭，看板进程不受影响。
exit /b 0
