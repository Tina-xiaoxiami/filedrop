#!/usr/bin/env python3
"""
FileDrop - 本地文件传输工具 (改进版)
深色主题 + 无终端窗口 + 调试信息
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import socket
import threading
import json
import os
import sys
from pathlib import Path
import requests
from flask import Flask, request
from zeroconf import ServiceInfo, Zeroconf, ServiceBrowser, ServiceListener
import uuid
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置目录
CONFIG_DIR = Path.home() / ".filedrop"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRUST_FILE = CONFIG_DIR / "trust.json"
CONFIG_DIR.mkdir(exist_ok=True)

# 深色主题配色
COLORS = {
    'bg': '#0F172A',
    'surface': '#1E293B',
    'surface_light': '#334155',
    'text': '#E2E8F0',
    'text_secondary': '#94A3B8',
    'primary': '#3B82F6',
    'primary_dark': '#2563EB',
    'success': '#4ADE80',
    'warning': '#FBBF24',
    'error': '#EF4444',
}


class FileDropApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FileDrop")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.configure(bg=COLORS['bg'])

        # 设备信息
        self.device_id = str(uuid.uuid4())[:8]
        self.device_name = socket.gethostname()
        self.port = 8765
        self.save_path = self.load_save_path()

        # 设备列表
        self.discovered_devices = {}
        self.paired_devices = self.load_trust_list()
        self.selected_device = None

        # 创建自定义样式
        self.setup_styles()

        # 创建 UI
        self.setup_ui()

        # 启动服务
        self.start_services()

        # 刷新设备列表
        self.refresh_devices()

    def setup_styles(self):
        """设置自定义样式"""
        style = ttk.Style()
        style.theme_use('clam')

        # 配置颜色
        style.configure('Custom.TFrame', background=COLORS['bg'])
        style.configure('Custom.TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['text'],
                       font=('Helvetica', 11))
        style.configure('Title.TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['text'],
                       font=('Helvetica', 24, 'bold'))
        style.configure('Subtitle.TLabel',
                       background=COLORS['bg'],
                       foreground=COLORS['text_secondary'],
                       font=('Helvetica', 10))

        # 按钮样式
        style.configure('Primary.TButton',
                       background=COLORS['primary'],
                       foreground='white',
                       font=('Helvetica', 11, 'bold'),
                       padding=(20, 10))
        style.map('Primary.TButton',
                  background=[('active', COLORS['primary_dark'])])

        style.configure('Secondary.TButton',
                       background=COLORS['surface_light'],
                       foreground=COLORS['text'],
                       font=('Helvetica', 10),
                       padding=(15, 8))

        # 列表框样式
        style.configure('Custom.TLabelframe',
                       background=COLORS['surface'],
                       foreground=COLORS['text'])
        style.configure('Custom.TLabelframe.Label',
                       background=COLORS['surface'],
                       foreground=COLORS['text'],
                       font=('Helvetica', 12, 'bold'))

    def setup_ui(self):
        """设置现代化界面"""
        # 主容器
        main_container = tk.Frame(self.root, bg=COLORS['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 顶部标题栏
        header = tk.Frame(main_container, bg=COLORS['bg'])
        header.pack(fill=tk.X, pady=(0, 20))

        # Logo 和标题
        title_frame = tk.Frame(header, bg=COLORS['bg'])
        title_frame.pack(side=tk.LEFT)

        icon_label = tk.Label(title_frame, text="📡",
                             font=('Helvetica', 32),
                             bg=COLORS['bg'], fg=COLORS['primary'])
        icon_label.pack(side=tk.LEFT, padx=(0, 10))

        text_frame = tk.Frame(title_frame, bg=COLORS['bg'])
        text_frame.pack(side=tk.LEFT)

        title = tk.Label(text_frame, text="FileDrop",
                        font=('Helvetica', 24, 'bold'),
                        bg=COLORS['bg'], fg=COLORS['text'])
        title.pack(anchor=tk.W)

        subtitle = tk.Label(text_frame,
                           text=f"本机: {self.device_name} | ID: {self.device_id}",
                           font=('Helvetica', 10),
                           bg=COLORS['bg'], fg=COLORS['text_secondary'])
        subtitle.pack(anchor=tk.W)

        # 设置按钮
        settings_btn = tk.Button(header, text="⚙️ 设置",
                                font=('Helvetica', 11),
                                bg=COLORS['surface_light'],
                                fg=COLORS['text'],
                                activebackground=COLORS['surface'],
                                activeforeground=COLORS['text'],
                                bd=0, padx=15, pady=8,
                                cursor='hand2',
                                command=self.open_settings)
        settings_btn.pack(side=tk.RIGHT)

        # 内容区域
        content = tk.Frame(main_container, bg=COLORS['bg'])
        content.pack(fill=tk.BOTH, expand=True)

        # 左侧 - 设备列表
        left_panel = tk.Frame(content, bg=COLORS['surface'], bd=1, relief=tk.FLAT)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 设备列表标题
        list_header = tk.Frame(left_panel, bg=COLORS['surface'])
        list_header.pack(fill=tk.X, padx=15, pady=15)

        tk.Label(list_header, text="发现的设备",
                font=('Helvetica', 14, 'bold'),
                bg=COLORS['surface'], fg=COLORS['text']).pack(side=tk.LEFT)

        # 刷新按钮
        refresh_btn = tk.Button(list_header, text="🔄 刷新",
                               font=('Helvetica', 10),
                               bg=COLORS['surface_light'],
                               fg=COLORS['text'],
                               activebackground=COLORS['primary'],
                               bd=0, padx=10, pady=5,
                               cursor='hand2',
                               command=self.force_refresh)
        refresh_btn.pack(side=tk.RIGHT)

        # 设备列表框（自定义样式）
        list_frame = tk.Frame(left_panel, bg=COLORS['surface_light'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # 滚动条
        scrollbar = tk.Scrollbar(list_frame, bg=COLORS['surface_light'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.device_listbox = tk.Listbox(
            list_frame,
            bg=COLORS['surface_light'],
            fg=COLORS['text'],
            selectbackground=COLORS['primary'],
            selectforeground='white',
            font=('Helvetica', 12),
            height=10,
            bd=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        self.device_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.device_listbox.yview)

        self.device_listbox.bind("<<ListboxSelect>>", self.on_device_select)

        # 右侧 - 操作面板
        right_panel = tk.Frame(content, bg=COLORS['surface'], bd=1, relief=tk.FLAT)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # 操作区域
        action_frame = tk.Frame(right_panel, bg=COLORS['surface'])
        action_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 选中设备信息
        self.device_info_frame = tk.Frame(action_frame, bg=COLORS['surface'])
        self.device_info_frame.pack(fill=tk.X, pady=(0, 20))

        self.selected_label = tk.Label(self.device_info_frame,
                                      text="未选择设备",
                                      font=('Helvetica', 14),
                                      bg=COLORS['surface'],
                                      fg=COLORS['text_secondary'])
        self.selected_label.pack()

        # 操作按钮区域
        self.action_buttons = tk.Frame(action_frame, bg=COLORS['surface'])
        self.action_buttons.pack(fill=tk.X, pady=20)

        # 配对按钮
        self.pair_btn = tk.Button(self.action_buttons,
                                 text="🔒 配对设备",
                                 font=('Helvetica', 12, 'bold'),
                                 bg=COLORS['primary'],
                                 fg='white',
                                 activebackground=COLORS['primary_dark'],
                                 activeforeground='white',
                                 bd=0, padx=30, pady=12,
                                 cursor='hand2',
                                 state=tk.DISABLED,
                                 command=self.pair_device)
        self.pair_btn.pack(fill=tk.X, pady=(0, 10))

        # 发送文件按钮
        self.send_btn = tk.Button(self.action_buttons,
                                 text="📤 发送文件",
                                 font=('Helvetica', 12, 'bold'),
                                 bg=COLORS['success'],
                                 fg='white',
                                 activebackground='#22c55e',
                                 activeforeground='white',
                                 bd=0, padx=30, pady=12,
                                 cursor='hand2',
                                 state=tk.DISABLED,
                                 command=self.send_file)
        self.send_btn.pack(fill=tk.X)

        # 文件拖放区域（视觉提示）
        self.drop_zone = tk.Frame(action_frame,
                                  bg=COLORS['surface_light'],
                                  bd=2, relief=tk.DASHED)
        self.drop_zone.pack(fill=tk.BOTH, expand=True, pady=20)
        self.drop_zone.pack_propagate(False)
        self.drop_zone.configure(height=150)

        drop_label = tk.Label(self.drop_zone,
                             text="💡 使用说明\n\n"
                                  "1. 确保两台设备在同一WiFi下\n"
                                  "2. 等待设备自动发现\n"
                                  "3. 首次使用需要配对\n"
                                  "4. 选择设备后点击发送文件",
                             font=('Helvetica', 11),
                             bg=COLORS['surface_light'],
                             fg=COLORS['text_secondary'],
                             justify=tk.LEFT)
        drop_label.pack(expand=True)

        # 底部状态栏
        self.status_frame = tk.Frame(main_container, bg=COLORS['surface'])
        self.status_frame.pack(fill=tk.X, pady=(20, 0))

        self.status_label = tk.Label(self.status_frame,
                                    text="🟡 正在初始化服务...",
                                    font=('Helvetica', 10),
                                    bg=COLORS['surface'],
                                    fg=COLORS['text_secondary'])
        self.status_label.pack(side=tk.LEFT, padx=15, pady=10)

        # 调试信息按钮
        debug_btn = tk.Button(self.status_frame, text="🔍 调试信息",
                             font=('Helvetica', 9),
                             bg=COLORS['surface'],
                             fg=COLORS['text_secondary'],
                             activebackground=COLORS['surface_light'],
                             bd=0, padx=10, pady=5,
                             cursor='hand2',
                             command=self.show_debug_info)
        debug_btn.pack(side=tk.RIGHT, padx=15, pady=10)

    def start_services(self):
        """启动服务"""
        try:
            # HTTP 服务器线程
            self.http_thread = threading.Thread(target=self.start_http_server, daemon=True)
            self.http_thread.start()
            logger.info("HTTP 服务器线程已启动")

            # mDNS 服务
            self.zeroconf = Zeroconf()
            self.start_mdns_service()
            logger.info("mDNS 服务已启动")

            # 设备发现
            self.browser = ServiceBrowser(
                self.zeroconf,
                "_filedrop._tcp.local.",
                FileDropListener(self)
            )
            logger.info("设备发现已启动")

            self.update_status("🟢 服务运行正常，正在搜索设备...", COLORS['success'])

        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            self.update_status(f"🔴 启动失败: {e}", COLORS['error'])

    def get_local_ip(self):
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            logger.error(f"获取 IP 失败: {e}")
            return "127.0.0.1"

    def start_mdns_service(self):
        """注册 mDNS 服务"""
        try:
            info = ServiceInfo(
                "_filedrop._tcp.local.",
                f"{self.device_name}._filedrop._tcp.local.",
                addresses=[socket.inet_aton(self.get_local_ip())],
                port=self.port,
                properties={"id": self.device_id, "name": self.device_name}
            )
            self.zeroconf.register_service(info)
            logger.info(f"mDNS 服务已注册: {self.device_name} ({self.get_local_ip()}:{self.port})")
        except Exception as e:
            logger.error(f"注册 mDNS 服务失败: {e}")

    def start_http_server(self):
        """启动 HTTP 文件接收服务"""
        app = Flask(__name__)

        @app.route("/upload", methods=["POST"])
        def upload():
            try:
                if "file" not in request.files:
                    return "No file", 400
                file = request.files["file"]
                if file.filename == "":
                    return "No filename", 400

                filepath = Path(self.save_path) / file.filename
                file.save(str(filepath))

                self.root.after(0, lambda: self.show_notification(
                    "文件接收", f"收到: {file.filename}\n保存到: {self.save_path}"
                ))
                logger.info(f"收到文件: {file.filename}")
                return "OK", 200
            except Exception as e:
                logger.error(f"接收文件失败: {e}")
                return str(e), 500

        @app.route("/pair", methods=["POST"])
        def pair():
            try:
                data = request.json
                self.paired_devices[data["id"]] = {
                    "id": data["id"],
                    "name": data["name"],
                    "ip": data["ip"],
                    "port": data["port"]
                }
                self.save_trust_list()
                logger.info(f"配对成功: {data['name']}")
                return "OK", 200
            except Exception as e:
                logger.error(f"配对失败: {e}")
                return str(e), 500

        app.run(host="0.0.0.0", port=self.port, threaded=True, debug=False, use_reloader=False)

    def refresh_devices(self):
        """刷新设备列表"""
        self.device_listbox.delete(0, tk.END)

        has_devices = False

        # 显示已配对设备
        if self.paired_devices:
            self.device_listbox.insert(tk.END, "【已配对设备】")
            self.device_listbox.itemconfig(tk.END, {'fg': COLORS['success'], 'font': ('Helvetica', 10, 'bold')})
            for d in self.paired_devices.values():
                display = f"  ✓ {d['name']}"
                self.device_listbox.insert(tk.END, display)
                self.device_listbox.itemconfig(tk.END, {'fg': COLORS['text']})
            has_devices = True

        # 显示发现但未配对的设备
        new_devices = [d for d in self.discovered_devices.values()
                       if d["id"] not in self.paired_devices]
        if new_devices:
            if self.paired_devices:
                self.device_listbox.insert(tk.END, "")
            self.device_listbox.insert(tk.END, "【新设备】")
            self.device_listbox.itemconfig(tk.END, {'fg': COLORS['warning'], 'font': ('Helvetica', 10, 'bold')})
            for d in new_devices:
                display = f"  • {d['name']}"
                self.device_listbox.insert(tk.END, display)
                self.device_listbox.itemconfig(tk.END, {'fg': COLORS['text_secondary']})
            has_devices = True

        if not has_devices:
            self.device_listbox.insert(tk.END, "未发现设备...")
            self.device_listbox.itemconfig(tk.END, {'fg': COLORS['text_secondary']})

        # 3秒后刷新
        self.root.after(3000, self.refresh_devices)

    def force_refresh(self):
        """强制刷新"""
        self.discovered_devices.clear()
        self.update_status("🔄 正在重新搜索设备...", COLORS['warning'])
        self.refresh_devices()

    def on_device_select(self, event):
        """设备选择事件"""
        selection = self.device_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        text = self.device_listbox.get(idx)

        # 检查是否选择了有效设备
        if text.startswith("  ✓"):
            # 已配对设备
            name = text.strip()[2:].strip()
            for d in self.paired_devices.values():
                if d["name"] == name:
                    self.selected_device = d
                    self.update_device_info(d, paired=True)
                    self.pair_btn.config(state=tk.DISABLED, bg=COLORS['surface_light'])
                    self.send_btn.config(state=tk.NORMAL, bg=COLORS['success'])
                    break
        elif text.startswith("  •"):
            # 未配对设备
            name = text.strip()[2:].strip()
            for d in self.discovered_devices.values():
                if d["name"] == name:
                    self.selected_device = d
                    self.update_device_info(d, paired=False)
                    self.pair_btn.config(state=tk.NORMAL, bg=COLORS['primary'])
                    self.send_btn.config(state=tk.DISABLED, bg=COLORS['surface_light'])
                    break

    def update_device_info(self, device, paired=False):
        """更新设备信息显示"""
        for widget in self.device_info_frame.winfo_children():
            widget.destroy()

        status = "已配对 ✓" if paired else "未配对"
        status_color = COLORS['success'] if paired else COLORS['warning']

        tk.Label(self.device_info_frame,
                text=device['name'],
                font=('Helvetica', 16, 'bold'),
                bg=COLORS['surface'], fg=COLORS['text']).pack(anchor=tk.W)

        info_frame = tk.Frame(self.device_info_frame, bg=COLORS['surface'])
        info_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Label(info_frame,
                text=f"IP: {device['ip']}:{device['port']}",
                font=('Helvetica', 10),
                bg=COLORS['surface'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)

        tk.Label(info_frame,
                text=status,
                font=('Helvetica', 10, 'bold'),
                bg=COLORS['surface'], fg=status_color).pack(side=tk.RIGHT)

    def pair_device(self):
        """配对设备"""
        if not self.selected_device:
            return

        d = self.selected_device
        try:
            self.update_status(f"正在配对 {d['name']}...", COLORS['warning'])
            response = requests.post(
                f"http://{d['ip']}:{d['port']}/pair",
                json={
                    "id": self.device_id,
                    "name": self.device_name,
                    "ip": self.get_local_ip(),
                    "port": self.port
                },
                timeout=5
            )

            if response.status_code == 200:
                self.paired_devices[d["id"]] = d
                self.save_trust_list()
                self.show_notification("成功", f"已与 {d['name']} 配对")
                self.update_status(f"已配对 {d['name']}", COLORS['success'])
                self.refresh_devices()
            else:
                self.show_notification("失败", f"配对请求被拒绝: {response.status_code}")
        except Exception as e:
            logger.error(f"配对失败: {e}")
            self.show_notification("错误", f"配对失败: {e}")
            self.update_status(f"配对失败: {e}", COLORS['error'])

    def send_file(self):
        """发送文件"""
        if not self.selected_device:
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        d = self.selected_device
        filename = os.path.basename(filepath)

        try:
            self.update_status(f"正在发送 {filename}...", COLORS['warning'])

            with open(filepath, "rb") as f:
                files = {"file": (filename, f)}
                response = requests.post(
                    f"http://{d['ip']}:{d['port']}/upload",
                    files=files,
                    timeout=300
                )

            if response.status_code == 200:
                self.show_notification("成功", f"文件发送成功！\n{filename}")
                self.update_status("文件发送成功", COLORS['success'])
            else:
                self.show_notification("失败", f"发送失败: {response.text}")
                self.update_status(f"发送失败: {response.status_code}", COLORS['error'])
        except Exception as e:
            logger.error(f"发送失败: {e}")
            self.show_notification("错误", f"发送失败: {e}")
            self.update_status(f"发送失败: {e}", COLORS['error'])

    def open_settings(self):
        """打开设置对话框"""
        window = tk.Toplevel(self.root)
        window.title("设置")
        window.geometry("500x300")
        window.configure(bg=COLORS['surface'])
        window.transient(self.root)
        window.grab_set()

        frame = tk.Frame(window, bg=COLORS['surface'])
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="接收文件保存位置",
                font=('Helvetica', 12, 'bold'),
                bg=COLORS['surface'], fg=COLORS['text']).pack(anchor=tk.W, pady=(0, 10))

        path_frame = tk.Frame(frame, bg=COLORS['surface'])
        path_frame.pack(fill=tk.X, pady=(0, 20))

        entry = tk.Entry(path_frame, font=('Helvetica', 11),
                        bg=COLORS['surface_light'], fg=COLORS['text'],
                        bd=0, highlightthickness=1, highlightbackground=COLORS['surface_light'])
        entry.insert(0, str(self.save_path))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)

        def choose():
            folder = filedialog.askdirectory()
            if folder:
                entry.delete(0, tk.END)
                entry.insert(0, folder)

        tk.Button(path_frame, text="浏览...",
                 font=('Helvetica', 10),
                 bg=COLORS['surface_light'], fg=COLORS['text'],
                 activebackground=COLORS['primary'],
                 bd=0, padx=15, pady=8,
                 cursor='hand2',
                 command=choose).pack(side=tk.RIGHT, padx=(10, 0))

        def save():
            self.save_path = entry.get()
            self.save_config()
            self.show_notification("成功", "设置已保存")
            window.destroy()

        tk.Button(frame, text="保存",
                 font=('Helvetica', 12, 'bold'),
                 bg=COLORS['primary'], fg='white',
                 activebackground=COLORS['primary_dark'],
                 bd=0, padx=30, pady=10,
                 cursor='hand2',
                 command=save).pack(pady=20)

    def show_notification(self, title, message):
        """显示通知"""
        messagebox.showinfo(title, message)

    def update_status(self, text, color):
        """更新状态栏"""
        self.status_label.config(text=text, fg=color)

    def show_debug_info(self):
        """显示调试信息"""
        info = f"""
设备信息:
  - 名称: {self.device_name}
  - ID: {self.device_id}
  - IP: {self.get_local_ip()}
  - 端口: {self.port}

保存路径: {self.save_path}

已配对设备: {len(self.paired_devices)}
已发现设备: {len(self.discovered_devices)}

服务状态:
  - HTTP 服务: 运行中 (端口 {self.port})
  - mDNS 服务: 运行中

注意:
  如果无法发现设备，请检查:
  1. 两台设备在同一 WiFi 网络
  2. 防火墙允许端口 {self.port}
  3. 路由器未禁用 mDNS/Bonjour
        """
        messagebox.showinfo("调试信息", info.strip())

    def load_save_path(self):
        """加载保存路径"""
        if CONFIG_FILE.exists():
            try:
                config = json.loads(CONFIG_FILE.read_text())
                return config.get("save_path", str(Path.home() / "Downloads"))
            except:
                pass
        return str(Path.home() / "Downloads")

    def save_config(self):
        """保存配置"""
        CONFIG_FILE.write_text(json.dumps({"save_path": self.save_path}, indent=2))

    def load_trust_list(self):
        """加载信任列表"""
        if TRUST_FILE.exists():
            try:
                return json.loads(TRUST_FILE.read_text())
            except:
                pass
        return {}

    def save_trust_list(self):
        """保存信任列表"""
        TRUST_FILE.write_text(json.dumps(self.paired_devices, indent=2))

    def on_closing(self):
        """关闭应用"""
        try:
            self.zeroconf.close()
        except:
            pass
        self.root.destroy()


class FileDropListener(ServiceListener):
    """mDNS 服务发现监听器"""

    def __init__(self, app):
        self.app = app

    def add_service(self, zc, type_, name):
        try:
            info = zc.get_service_info(type_, name)
            if info:
                device_id = info.properties.get(b"id", b"").decode()
                device_name = info.properties.get(b"name", b"").decode() or name.split(".")[0]

                if device_id and device_id != self.app.device_id:
                    device_ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else "unknown"
                    self.app.discovered_devices[device_id] = {
                        "id": device_id,
                        "name": device_name,
                        "ip": device_ip,
                        "port": info.port
                    }
                    logger.info(f"发现设备: {device_name} ({device_ip})")
        except Exception as e:
            logger.error(f"处理服务发现事件失败: {e}")

    def remove_service(self, zc, type_, name):
        pass

    def update_service(self, zc, type_, name):
        pass


def main():
    root = tk.Tk()
    app = FileDropApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
