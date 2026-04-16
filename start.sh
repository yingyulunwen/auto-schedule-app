#!/bin/bash
# 中学自动调课系统 - 启动脚本

echo "========================================"
echo "  中学自动调课系统 v2.0"
echo "========================================"
echo ""

# 检查Python
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python版本: $python_version"

# 安装依赖
echo ""
echo "📦 安装依赖..."
pip install streamlit pandas openpyxl -q

# 检查课表文件
if [ ! -f "用户上传/2025-2026第一学期七八九年级班级课表（2025.12.23修改)(1)_1776239900375_0_udqx.xlsx" ]; then
    echo "⚠️  警告: 课表文件不存在，请先放入 用户上传/ 目录"
fi

# 启动
echo ""
echo "🚀 启动应用..."
echo "   访问地址: http://localhost:8501"
echo "   按 Ctrl+C 停止服务"
echo ""

streamlit run app.py --server.headless true --server.port 8501
