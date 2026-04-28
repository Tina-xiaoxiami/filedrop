use serde::{Deserialize, Serialize};
use tokio::fs::File;
use tokio::io::AsyncReadExt;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransferProgress {
    pub file_name: String,
    pub total_size: u64,
    pub transferred: u64,
    pub status: TransferStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransferStatus {
    Pending,
    Transferring,
    Completed,
    Failed(String),
}

pub struct FileTransfer;

impl FileTransfer {
    pub fn new() -> Self {
        Self
    }

    pub async fn send_file(
        &self,
        target_ip: &str,
        target_port: u16,
        file_path: &str,
    ) -> Result<(), String> {
        let mut file = File::open(file_path)
            .await
            .map_err(|e| format!("Failed to open file: {}", e))?;

        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)
            .await
            .map_err(|e| format!("Failed to read file: {}", e))?;

        let filename = std::path::Path::new(file_path)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unnamed");

        // 构建 multipart 表单数据
        let form = reqwest::multipart::Form::new()
            .part("file", reqwest::multipart::Part::bytes(buffer).file_name(filename.to_string()));

        let client = reqwest::Client::new();
        let url = format!("http://{}:{}/api/send", target_ip, target_port);

        let response = client
            .post(&url)
            .multipart(form)
            .send()
            .await
            .map_err(|e| format!("Failed to send file: {}", e))?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(format!("Server returned error: {}", response.status()))
        }
    }
}
