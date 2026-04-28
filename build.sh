#!/bin/bash
# FileDrop 打包脚本 - 无终端窗口版本

echo "================================"
echo "FileDrop 打包脚本"
echo "================================"
echo ""

# 安装依赖
echo "[1/3] 安装依赖..."
pip install -q pyinstaller flask requests zeroconf 2>/dev/null || pip install pyinstaller flask requests zeroconf

# 清理旧构建
echo "[2/3] 清理旧构建..."
rm -rf dist build

# 打包 - 使用 --windowed 确保无终端窗口
echo "[3/3] 打包应用（无终端窗口）..."
pyinstaller \
    --onefile \
    --windowed \
    --name FileDrop \
    --clean \
    --noconfirm \
    --log-level WARN \
    filedrop.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 打包成功！"
    echo ""
    echo "输出文件: dist/FileDrop"
    echo ""
    echo "注意: Mac版本双击运行即可，无终端窗口"
else
    echo ""
    echo "❌ 打包失败"
fi
