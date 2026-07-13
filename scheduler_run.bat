@echo off
setlocal enabledelayedexpansion
title 基金看板定时更新（单次）
set "SCRIPT=%~dp0fund_dashboard_trade.py"

REM 选一个能 import 依赖的 Python（优先系统 Python，回退 PATH）
set "PY="
for %%P in ("D:\Programs\Python\Python313\python.exe" python) do (
    "%%~P" -c "import requests, apscheduler, pandas, openpyxl" >nul 2>&1
    if !errorlevel! == 0 (
        set "PY=%%~P"
        goto :run
    )
)

echo [错误] 未找到可用 Python 或缺少依赖，请运行: pip install requests apscheduler pandas openpyxl
exit /b 1

:run
REM --service 7200：启动常驻进程，每 20 秒重写一次 HTML（单价实时更新），2 小时后自动退出
"%PY%" "%SCRIPT%" --service 7200
exit /b 0
