// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager, State};
use tauri::menu::{MenuBuilder, MenuItemBuilder};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::Listener;
use tauri::Emitter;
use tokio::sync::mpsc;
use uuid::Uuid;

mod mdns;
mod http_server;
mod trust_list;
mod file_transfer;

use mdns::{DeviceInfo, MdnsService};
use trust_list::{TrustList, TrustEntry};
use file_transfer::{TransferProgress, FileTransfer};

/// 应用状态
pub struct AppState {
    pub device_id: String,
    pub device_name: String,
    pub port: u16,
    pub mdns: Arc<MdnsService>,
    pub trust_list: Arc<Mutex<TrustList>>,
    pub save_path: Arc<Mutex<PathBuf>>,
}

impl AppState {
    pub fn new() -> Self {
        let device_id = Uuid::new_v4().to_string()[..8].to_string();
        let device_name = whoami::devicename();
        let port = 8765;

        let trust_list = Arc::new(Mutex::new(TrustList::load()));
        let save_path = Arc::new(Mutex::new(Self::default_save_path()));

        let mdns = Arc::new(MdnsService::new(
            device_id.clone(),
            device_name.clone(),
            port,
        ));

        Self {
            device_id,
            device_name,
            port,
            mdns,
            trust_list,
            save_path,
        }
    }

    fn default_save_path() -> PathBuf {
        dirs::download_dir().unwrap_or_else(|| PathBuf::from("."))
    }
}

// ===== Tauri 命令 =====

/// 获取设备信息
#[tauri::command]
pub fn get_device_info(state: State<Arc<AppState>>) -> DeviceInfo {
    DeviceInfo {
        id: state.device_id.clone(),
        name: state.device_name.clone(),
        ip: get_local_ip(),
        port: state.port,
    }
}

/// 获取发现的设备列表
#[tauri::command]
pub async fn get_discovered_devices(state: State<Arc<AppState>>) -> Vec<DeviceInfo> {
    let discovered = state.mdns.get_discovered_devices();
    let trust_list = state.trust_list.lock().unwrap();

    discovered
        .into_iter()
        .map(|d| {
            let is_paired = trust_list.is_trusted(&d.id);
            DeviceInfo {
                id: d.id,
                name: d.name,
                ip: d.ip,
                port: d.port,
                is_paired,
            }
        })
        .collect()
}

/// 发送配对请求
#[tauri::command]
pub async fn send_pair_request(
    device_id: String,
    state: State<Arc<AppState>>,
) -> Result<(), String> {
    let devices = state.mdns.get_discovered_devices();
    let device = devices
        .iter()
        .find(|d| d.id == device_id)
        .cloned()
        .ok_or_else(|| "Device not found".to_string())?;

    // 发送配对请求到目标设备
    let client = reqwest::Client::new();
    let url = format!("http://{}:{}/api/pair-request", device.ip, device.port);

    let response = client
        .post(&url)
        .json(&serde_json::json!({
            "device_id": state.device_id,
            "device_name": state.device_name,
        }))
        .send()
        .await
        .map_err(|e| format!("Failed to send pair request: {}", e))?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err("Pair request rejected".to_string())
    }
}

/// 接受配对
#[tauri::command]
pub fn accept_pair(device_id: String, device_name: String, state: State<Arc<AppState>>) -> Result<(), String> {
    let mut trust_list = state.trust_list.lock().unwrap();
    trust_list.add(TrustEntry {
        device_id: device_id.clone(),
        device_name,
        paired_at: chrono::Utc::now().timestamp(),
    });
    trust_list.save();
    Ok(())
}

/// 发送文件
#[tauri::command]
pub async fn send_file(
    device_id: String,
    file_path: String,
    state: State<Arc<AppState>>,
) -> Result<(), String> {
    let devices = state.mdns.get_discovered_devices();
    let device = devices
        .iter()
        .find(|d| d.id == device_id)
        .cloned()
        .map_err(|_| "Device not found")?;

    // 检查是否已配对
    let trust_list = state.trust_list.lock().unwrap();
    if !trust_list.is_trusted(&device_id) {
        return Err("Device not paired".to_string());
    }

    // 发送文件
    let transfer = FileTransfer::new();
    transfer
        .send_file(&device.ip, device.port, &file_path)
        .await
        .map_err(|e| format!("Transfer failed: {}", e))?;

    Ok(())
}

/// 选择文件
#[tauri::command]
pub async fn select_file(app: AppHandle) -> Result<Option<String>, String> {
    use tauri::dialog::FileDialogBuilder;

    let (tx, rx) = tokio::sync::oneshot::channel();

    FileDialogBuilder::new()
        .pick_file(move |path| {
            let _ = tx.send(path.map(|p| p.to_string_lossy().to_string()));
        });

    rx.await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

/// 选择文件夹
#[tauri::command]
pub async fn select_folder(app: AppHandle) -> Result<Option<String>, String> {
    use tauri::dialog::FileDialogBuilder;

    let (tx, rx) = tokio::sync::oneshot::channel();

    FileDialogBuilder::new()
        .pick_folder(move |path| {
            let _ = tx.send(path.map(|p| p.to_string_lossy().to_string()));
        });

    rx.await
        .map_err(|e| e.to_string())?
        .map_err(|e| e.to_string())
}

/// 设置保存路径
#[tauri::command]
pub fn set_save_path(path: String, state: State<Arc<AppState>>) -> Result<(), String> {
    let mut save_path = state.save_path.lock().unwrap();
    *save_path = PathBuf::from(path);
    Ok(())
}

/// 获取保存路径
#[tauri::command]
pub fn get_save_path(state: State<Arc<AppState>>) -> String {
    let save_path = state.save_path.lock().unwrap();
    save_path.to_string_lossy().to_string()
}

// ===== 辅助函数 =====

fn get_local_ip() -> String {
    let socket = std::net::UdpSocket::bind("0.0.0.0:0").unwrap();
    socket.connect("8.8.8.8:80").unwrap();
    let addr = socket.local_addr().unwrap();
    addr.ip().to_string()
}

// ===== 应用入口 =====

pub fn run() {
    tauri::Builder::default()
        .manage(Arc::new(AppState::new()))
        .setup(|app| {
            let app_handle = app.handle();
            let state: State<Arc<AppState>> = app_handle.state();

            // 启动 mDNS 服务
            let mdns = state.mdns.clone();
            tokio::spawn(async move {
                mdns.start().await;
            });

            // 启动 HTTP 服务器
            let http_port = state.port;
            let save_path = state.save_path.clone();
            let trust_list = state.trust_list.clone();

            tokio::spawn(async move {
                http_server::start(http_port, save_path, trust_list).await;
            });

            // 设置系统托盘
            setup_tray(app)?;

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_device_info,
            get_discovered_devices,
            send_pair_request,
            accept_pair,
            send_file,
            select_file,
            select_folder,
            set_save_path,
            get_save_path,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn setup_tray(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle();

    let show = MenuItemBuilder::new("显示")
        .id("show")
        .build(app_handle)?;

    let quit = MenuItemBuilder::new("退出")
        .id("quit")
        .build(app_handle)?;

    let menu = MenuBuilder::new(app_handle)
        .items(&[&show, &quit])
        .build()?;

    TrayIconBuilder::new()
        .menu(&menu)
        .icon(app_handle.default_window_icon().unwrap().clone())
        .on_menu_event(move |app, event| {
            match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                }
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        })
        .on_tray_icon_event(move |tray, event| {
            if let TrayIconEvent::Click { .. } = event {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    window.show().unwrap();
                    window.set_focus().unwrap();
                }
            }
        })
        .build(app)?;

    Ok(())
}
