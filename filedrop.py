#!/usr/bin/env python3
"""
FileDrop - 本地文件传输工具
使用 Python + tkinter 开发，支持 macOS 和 Windows
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

# 配置目录
CONFIG_DIR = Path.home() / ".filedrop"
CONFIG_FILE = CONFIG_DIR / "config.json"
TRUST_FILE = CONFIG_DIR / "trust.json"
CONFIG_DIR.mkdir(exist_ok=True)


class FileDropApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FileDrop - 本地文件传输")
        self.root.geometry("600x500")
        self.root.minsize(500, 400)

        # 设备信息
        self.device_id = str(uuid.uuid4())[:8]
        self.device_name = socket.gethostname()
        self.port = 8765
        self.save_path = self.load_save_path()

        # 设备列表
        self.discovered_devices = {}
        self.paired_devices = self.load_trust_list()
        self.selected_device = None

        # 创建 UI
        self.setup_ui()

        # 启动服务
        self.start_services()

        # 刷新设备列表
        self.refresh_devices()

    def setup_ui(self):
        """设置界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        title = ttk.Label(main_frame, text="📡 FileDrop", font=("Helvetica", 20, "bold"))
        title.pack(pady=(0, 5))

        # 本机信息
        info = ttk.Label(main_frame, text=f"本机: {self.device_name}", foreground="gray")
        info.pack(pady=(0, 20))

        # 设备列表
        list_frame = ttk.LabelFrame(main_frame, text="发现的设备", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.device_listbox = tk.Listbox(list_frame, height=8, font=("Helvetica", 11))
        self.device_listbox.pack(fill=tk.BOTH, expand=True)
        self.device_listbox.bind("<<ListboxSelect>>", self.on_device_select)

        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.pair_btn = ttk.Button(btn_frame, text="🔒 配对设备", command=self.pair_device, state=tk.DISABLED)
        self.pair_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.send_btn = ttk.Button(btn_frame, text="📤 发送文件", command=self.send_file, state=tk.DISABLED)
        self.send_btn.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="⚙️ 设置", command=self.open_settings).pack(side=tk.RIGHT)

        # 状态栏
        self.status_label = ttk.Label(main_frame, text="正在搜索设备...", foreground="gray")
        self.status_label.pack(pady=(10, 0))

    def start_services(self):
        """启动 mDNS 和 HTTP 服务"""
        # HTTP 服务器线程
        self.http_thread = threading.Thread(target=self.start_http_server, daemon=True)
        self.http_thread.start()

        # mDNS 服务
        self.zeroconf = Zeroconf()
        self.start_mdns_service()

        # 设备发现
        self.browser = ServiceBrowser(self.zeroconf, "_filedrop._tcp.local.", FileDropListener(self))

    def get_local_ip(self):
        """获取本机 IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def start_mdns_service(self):
        """注册 mDNS 服务"""
        info = ServiceInfo(
            "_filedrop._tcp.local.",
            f"{self.device_name}._filedrop._tcp.local.",
            addresses=[socket.inet_aton(self.get_local_ip())],
            port=self.port,
            properties={"id": self.device_id, "name": self.device_name}
        )
        self.zeroconf.register_service(info)

    def start_http_server(self):
        """启动 HTTP 文件接收服务"""
        app = Flask(__name__)

        @app.route("/upload", methods=["POST"])
        def upload():
            if "file" not in request.files:
                return "No file", 400
            file = request.files["file"]
            if file.filename == "":
                return "No filename", 400

            filepath = Path(self.save_path) / file.filename
            file.save(str(filepath))

            self.root.after(0, lambda: messagebox.showinfo("文件接收", f"收到: {file.filename}"))
            return "OK", 200

        @app.route("/pair", methods=["POST"])
        def pair():
            data = request.json
            self.paired_devices[data["id"]] = {
                "id": data["id"],
                "name": data["name"],
                "ip": data["ip"],
                "port": data["port"]
            }
            self.save_trust_list()
            return "OK", 200

        app.run(host="0.0.0.0", port=self.port, threaded=True)

    def refresh_devices(self):
        """刷新设备列表"""
        self.device_listbox.delete(0, tk.END)

        if self.paired_devices:
            self.device_listbox.insert(tk.END, "【已配对设备】")
            for d in self.paired_devices.values():
                self.device_listbox.insert(tk.END, f"✓ {d['name']} ({d['ip']})")

        new_devices = [d for d in self.discovered_devices.values() if d["id"] not in self.paired_devices]
        if new_devices:
            if self.paired_devices:
                self.device_listbox.insert(tk.END, "")
            self.device_listbox.insert(tk.END, "【新设备】")
            for d in new_devices:
                self.device_listbox.insert(tk.END, f"{d['name']} ({d['ip']})")

        if not self.paired_devices and not new_devices:
            self.device_listbox.insert(tk.END, "未发现设备...")

        self.root.after(3000, self.refresh_devices)

    def on_device_select(self, event):
        """设备选择事件"""
        selection = self.device_listbox.curselection()
        if not selection:
            return

        text = self.device_listbox.get(selection[0])
        if text.startswith("✓"):
            name = text.split(" (")[0][2:]
            for d in self.paired_devices.values():
                if d["name"] == name:
                    self.selected_device = d
                    self.send_btn.config(state=tk.NORMAL)
                    self.pair_btn.config(state=tk.DISABLED)
                    break
        elif not text.startswith("【") and text != "未发现设备...":
            name = text.split(" (")[0]
            for d in self.discovered_devices.values():
                if d["name"] == name:
                    self.selected_device = d
                    self.pair_btn.config(state=tk.NORMAL)
                    self.send_btn.config(state=tk.DISABLED)
                    break

    def pair_device(self):
        """配对设备"""
        if not self.selected_device:
            return

        d = self.selected_device
        try:
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
                messagebox.showinfo("成功", f"已与 {d['name']} 配对")
        except Exception as e:
            messagebox.showerror("错误", f"配对失败: {e}")

    def send_file(self):
        """发送文件"""
        if not self.selected_device:
            return

        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        d = self.selected_device
        try:
            self.status_label.config(text=f"正在发送 {os.path.basename(filepath)}...")

            with open(filepath, "rb") as f:
                files = {"file": (os.path.basename(filepath), f)}
                response = requests.post(
                    f"http://{d['ip']}:{d['port']}/upload",
                    files=files,
                    timeout=300
                )

            if response.status_code == 200:
                messagebox.showinfo("成功", "文件发送成功！")
            else:
                messagebox.showerror("失败", f"发送失败: {response.text}")
        except Exception as e:
            messagebox.showerror("错误", f"发送失败: {e}")
        finally:
            self.status_label.config(text="就绪")

    def open_settings(self):
        """打开设置对话框"""
        window = tk.Toplevel(self.root)
        window.title("设置")
        window.geometry("400x150")

        frame = ttk.Frame(window, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="接收文件保存位置:").pack(anchor=tk.W, pady=(0, 5))

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))

        entry = ttk.Entry(path_frame)
        entry.insert(0, str(self.save_path))
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def choose():
            folder = filedialog.askdirectory()
            if folder:
                entry.delete(0, tk.END)
                entry.insert(0, folder)

        ttk.Button(path_frame, text="浏览...", command=choose).pack(side=tk.RIGHT, padx=(5, 0))

        def save():
            self.save_path = entry.get()
            self.save_config()
            messagebox.showinfo("成功", "设置已保存")
            window.destroy()

        ttk.Button(frame, text="保存", command=save).pack(pady=10)

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
        self.zeroconf.close()
        self.root.destroy()


class FileDropListener(ServiceListener):
    """mDNS 服务发现监听器"""

    def __init__(self, app):
        self.app = app

    def add_service(self, zc, type_, name):
        info = zc.get_service_info(type_, name)
        if info:
            device_id = info.properties.get(b"id", b"").decode()
            device_name = info.properties.get(b"name", b"").decode() or name.split(".")[0]

            if device_id and device_id != self.app.device_id:
                self.app.discovered_devices[device_id] = {
                    "id": device_id,
                    "name": device_name,
                    "ip": socket.inet_ntoa(info.addresses[0]),
                    "port": info.port
                }

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
