use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::IpAddr;
use std::sync::{Arc, Mutex};
use mdns_sd::{ServiceDaemon, ServiceEvent, ServiceInfo};

const SERVICE_TYPE: &str = "_filedrop._tcp.local.";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceInfo {
    pub id: String,
    pub name: String,
    pub ip: String,
    pub port: u16,
}

pub struct MdnsService {
    device_id: String,
    device_name: String,
    port: u16,
    discovered: Arc<Mutex<HashMap<String, DeviceInfo>>>,
}

impl MdnsService {
    pub fn new(device_id: String, device_name: String, port: u16) -> Self {
        Self {
            device_id,
            device_name,
            port,
            discovered: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub async fn start(&self) {
        // 启动 mDNS 服务
        let mdns = ServiceDaemon::new().expect("Failed to create mDNS daemon");

        // 注册服务
        let my_ip = get_local_ip();
        let service_info = ServiceInfo::new(
            SERVICE_TYPE,
            &format!("FileDrop-{}", self.device_id),
            &format!("filedrop-{}.local.", self.device_id),
            &my_ip,
            self.port,
            &[("device_id", &self.device_id), ("device_name", &self.device_name)],
        )
        .expect("Failed to create service info");

        mdns.register(service_info)
            .expect("Failed to register mDNS service");

        // 浏览其他设备
        let receiver = mdns
            .browse(SERVICE_TYPE)
            .expect("Failed to browse mDNS services");

        let discovered = self.discovered.clone();
        let my_id = self.device_id.clone();

        tokio::spawn(async move {
            while let Ok(event) = receiver.recv() {
                match event {
                    ServiceEvent::ServiceResolved(info) => {
                        let properties = info.get_properties();
                        if let Some(device_id) = properties.get("device_id") {
                            // 跳过自己
                            if device_id != my_id {
                                let device_name = properties
                                    .get("device_name")
                                    .map(|s| s.to_string())
                                    .unwrap_or_else(|| "Unknown".to_string());

                                let device = DeviceInfo {
                                    id: device_id.to_string(),
                                    name: device_name,
                                    ip: info.get_addresses().first()
                                        .map(|a| a.to_string())
                                        .unwrap_or_default(),
                                    port: info.get_port(),
                                };

                                discovered.lock().unwrap().insert(device_id.to_string(), device);
                            }
                        }
                    }
                    ServiceEvent::ServiceRemoved(_, name) => {
                        // 移除离线的设备
                        let mut devices = discovered.lock().unwrap();
                        devices.retain(|_, d| !name.contains(&d.id));
                    }
                    _ => {}
                }
            }
        });
    }

    pub fn get_discovered_devices(&self) -> Vec<DeviceInfo> {
        self.discovered.lock().unwrap().values().cloned().collect()
    }
}

fn get_local_ip() -> IpAddr {
    let socket = std::net::UdpSocket::bind("0.0.0.0:0").unwrap();
    socket.connect("8.8.8.8:80").unwrap();
    socket.local_addr().unwrap().ip()
}
