# FileDrop - 本地文件传输工具

简洁优雅的跨平台文件传输工具，使用 Python + tkinter 开发。

## ✨ 特性

- **自动发现**：同一 WiFi 下的设备自动发现
- **信任列表**：首次配对后自动连接
- **极简操作**：点击选择文件即可发送
- **跨平台**：支持 macOS 和 Windows
- **单文件**：可打包成独立的可执行文件

## 🚀 快速开始

### 方式一：直接运行（需要 Python）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python filedop.py
```

### 方式二：打包成可执行文件

**macOS:**
```bash
# 安装依赖
pip install -r requirements.txt

# 打包
./build.sh

# 或手动
pyinstaller --onefile --windowed --name FileDrop filedop.py

# 输出: dist/FileDrop
```

**Windows:**
```powershell
# 1. 安装 Python（从 python.org 下载）
# 2. 打开 PowerShell

pip install -r requirements.txt
pyinstaller --onefile --windowed --name FileDrop filedop.py

# 输出: dist/FileDrop.exe
```

## 💡 使用方法

### 首次使用（配对）

1. 在两台电脑上都启动 FileDrop
2. 在设备列表中看到对方设备
3. 点击"配对设备"按钮
4. 配对成功，两台设备自动建立信任关系

### 日常传输

1. 打开 FileDrop
2. 选择要发送到的设备（已配对设备显示 ✓）
3. 点击"发送文件"按钮
4. 文件自动传输到对方的下载目录

### 设置

点击"设置"按钮可以修改接收文件的保存位置。

## 🛠️ 技术栈

- **GUI**: tkinter（Python 内置）
- **设备发现**: zeroconf (mDNS/Bonjour)
- **文件传输**: Flask HTTP 服务
- **打包**: PyInstaller

## 📁 项目结构

```
FileDrop/
├── filedop.py          # 主程序
├── requirements.txt      # Python 依赖
├── build.sh              # 打包脚本
└── README.md             # 使用说明
```

## ⚙️ 配置

配置文件保存在：
- **macOS**: `~/.filedrop/`
- **Windows**: `%USERPROFILE%\.filedrop\`

包含：
- `config.json` - 保存路径设置
- `trust.json` - 已配对设备列表

## 🔐 安全说明

- **本地传输**：所有文件通过局域网直接传输
- **信任机制**：首次配对后自动连接
- **无需互联网**：完全离线工作

## 📄 License

MIT
