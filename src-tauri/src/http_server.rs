use axum::{
    extract::{DefaultBodyLimit, Multipart, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tower_http::cors::CorsLayer;
use tokio::io::AsyncWriteExt;

use crate::trust_list::TrustList;

#[derive(Clone)]
struct ServerState {
    save_path: Arc<Mutex<PathBuf>>,
    trust_list: Arc<Mutex<TrustList>>,
}

pub async fn start(
    port: u16,
    save_path: Arc<Mutex<PathBuf>>,
    trust_list: Arc<Mutex<TrustList>>,
) {
    let state = ServerState {
        save_path,
        trust_list,
    };

    let app = Router::new()
        .route("/api/ping", get(ping))
        .route("/api/pair-request", post(handle_pair_request))
        .route("/api/send", post(handle_send_file))
        .layer(DefaultBodyLimit::max(1024 * 1024 * 1024)) // 1GB 限制
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();

    axum::serve(listener, app).await.unwrap();
}

async fn ping() -> impl IntoResponse {
    Json(serde_json::json!({ "status": "ok" }))
}

#[derive(Deserialize)]
struct PairRequest {
    device_id: String,
    device_name: String,
}

#[derive(Serialize)]
struct PairResponse {
    accepted: bool,
}

async fn handle_pair_request(
    State(state): State<ServerState>,
    Json(request): Json<PairRequest>,
) -> impl IntoResponse {
    // 这里可以实现更复杂的配对确认逻辑
    // 例如：弹窗询问用户是否接受配对
    // 简化版本：自动接受

    let mut trust_list = state.trust_list.lock().unwrap();
    trust_list.add(crate::trust_list::TrustEntry {
        device_id: request.device_id.clone(),
        device_name: request.device_name,
        paired_at: chrono::Utc::now().timestamp(),
    });
    trust_list.save();

    (StatusCode::OK, Json(PairResponse { accepted: true }))
}

async fn handle_send_file(
    State(state): State<ServerState>,
    mut multipart: Multipart,
) -> impl IntoResponse {
    let save_path = state.save_path.lock().unwrap().clone();

    while let Some(field) = multipart.next_field().await.unwrap() {
        let name = field.name().unwrap_or("unknown").to_string();
        let filename = field.file_name().unwrap_or("unnamed").to_string();
        let data = field.bytes().await.unwrap();

        let filepath = save_path.join(&filename);

        // 写入文件
        if let Ok(mut file) = tokio::fs::File::create(&filepath).await {
            if let Err(e) = file.write_all(&data).await {
                return (StatusCode::INTERNAL_SERVER_ERROR, format!("Write error: {}", e));
            }
        } else {
            return (StatusCode::INTERNAL_SERVER_ERROR, "Failed to create file".to_string());
        }
    }

    (StatusCode::OK, "File received".to_string())
}
