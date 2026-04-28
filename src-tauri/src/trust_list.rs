use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

const TRUST_LIST_FILE: &str = "trust_list.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustEntry {
    pub device_id: String,
    pub device_name: String,
    pub paired_at: i64,
}

#[derive(Debug, Default, Serialize, Deserialize)]
pub struct TrustList {
    devices: HashMap<String, TrustEntry>,
}

impl TrustList {
    pub fn load() -> Self {
        let path = Self::trust_list_path();
        if path.exists() {
            if let Ok(content) = fs::read_to_string(&path) {
                if let Ok(list) = serde_json::from_str(&content) {
                    return list;
                }
            }
        }
        Self::default()
    }

    pub fn save(&self) {
        let path = Self::trust_list_path();
        if let Ok(content) = serde_json::to_string_pretty(self) {
            let _ = fs::write(path, content);
        }
    }

    pub fn add(&mut self, entry: TrustEntry) {
        self.devices.insert(entry.device_id.clone(), entry);
    }

    pub fn remove(&mut self, device_id: &str) {
        self.devices.remove(device_id);
    }

    pub fn is_trusted(&self, device_id: &str) -> bool {
        self.devices.contains_key(device_id)
    }

    pub fn get(&self, device_id: &str) -> Option<&TrustEntry> {
        self.devices.get(device_id)
    }

    pub fn list(&self) -> Vec<&TrustEntry> {
        self.devices.values().collect()
    }

    fn trust_list_path() -> PathBuf {
        dirs::config_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("FileDrop")
            .join(TRUST_LIST_FILE)
    }
}
