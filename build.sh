#!/bin/bash
# FileDrop 打包脚本

echo "================================"
echo "FileDrop 打包脚本"
echo "================================"
echo ""

# 检查 pyinstaller
if ! command -v pyinstaller &> /dev/null; then
    echo "正在安装 PyInstaller..."
    pip install pyinstaller
fi

echo "正在打包..."
pyinstaller \
    --onefile \
    --windowed \
    --name FileDrop \
    --clean \
    filedop.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 打包成功！"
    echo ""
    echo "输出文件: dist/FileDrop"
    echo ""
else
    echo ""
    echo "❌ 打包失败"
    echo ""
fi
