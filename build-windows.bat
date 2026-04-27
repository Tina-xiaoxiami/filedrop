@echo off
chcp 65001
cls
echo ============================================
echo  FileDrop Windows 一键打包脚本
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] 未找到 Python
    echo     请从 https://python.org 下载安装
    echo     安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

echo [1/3] Python 已安装
echo.

:: 安装依赖
echo [2/3] 安装依赖...
pip install flask requests zeroconf pyinstaller
if errorlevel 1 (
    echo [X] 依赖安装失败
    pause
    exit /b 1
)

echo.
echo [3/3] 打包中...（需要几分钟）
pyinstaller ^
    --onefile ^
    --windowed ^
    --name FileDrop ^
    --clean ^
    filedrop.py

if errorlevel 1 (
    echo [X] 打包失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo ✅ 打包成功！
echo ============================================
echo.
echo 输出文件: dist\FileDrop.exe
echo.
echo 使用方法:
echo 1. 将 FileDrop.exe 复制到桌面
echo 2. 双击运行
echo 3. 在另一台电脑上也运行 FileDrop
echo 4. 配对后即可传输文件
echo.
pause
