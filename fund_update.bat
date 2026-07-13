@echo off
setlocal enabledelayedexpansion
title 基金实时估值看板更新

REM 看板脚本路径（基于本 bat 所在目录，可移植）
set "SCRIPT=%~dp0fund_dashboard_trade.py"

REM 候选 Python：优先尝试 PATH 中的 python，再回退到已知装好依赖的系统 Python
REM 逐一检测能否导入所需依赖，选第一个可用的
set "PY="
for %%P in (python "D:\Programs\Python\Python313\python.exe") do (
    %%~P -c "import requests, apscheduler, pandas, openpyxl" >nul 2>&1
    if !errorlevel! == 0 (
        set "PY=%%~P"
        goto :found
    )
)

:found
if not defined PY (
    echo [错误] 找不到可用的 Python，或缺少依赖模块。
    echo 请先安装依赖： pip install requests apscheduler pandas openpyxl
    echo 或把 Python 加入系统 PATH。
    pause
    exit /b 1
)

echo 使用 Python: %PY%
echo 正在启动基金看板（Ctrl+C 可停止）...
echo.
start "" "%~dp0fund_code\fund_dashboard.html"
"%PY%" "%SCRIPT%"
if errorlevel 1 (
    echo.
    echo [错误] 运行失败，请检查上方报错信息。
    echo 常见原因：缺少依赖（pip install requests apscheduler pandas openpyxl）
    pause
    exit /b 1
)

echo.
echo 更新完成!
pause
