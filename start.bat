@echo off
chcp 65001 >nul
echo ========================================
echo   中学自动调课系统 v2.0
echo ========================================
echo.

pip install streamlit pandas openpyxl -q 2>nul

echo [INFO] 检查依赖...
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo [ERROR] Streamlit未安装成功
    pause
    exit /b 1
)

echo [OK] 依赖检查通过
echo.
echo [INFO] 启动应用...
echo    访问地址: http://localhost:8501
echo    按 Ctrl+C 停止服务
echo.

python -m streamlit run app.py --server.headless true --server.port 8501
