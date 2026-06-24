#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::Manager;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_http::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            // System tray setup
            let _tray = tauri::SystemTray::new()
                .with_menu(tauri::SystemTrayMenu::new()
                    .add_item(tauri::CustomMenuItem::new("show", "Show SupremeAI"))
                    .add_item(tauri::CustomMenuItem::new("quick_chat", "Quick Chat"))
                    .add_native_item(tauri::SystemTrayMenuItem::Separator)
                    .add_item(tauri::CustomMenuItem::new("quit", "Quit")));

            // Global hotkey: Ctrl+Shift+S
            app.global_shortcut_manager()
                .register("Ctrl+Shift+S", || {
                    // Show/hide window logic
                    let window = app.get_window("main").unwrap();
                    if window.is_visible().unwrap() {
                        window.hide().unwrap();
                    } else {
                        window.show().unwrap();
                        window.set_focus().unwrap();
                    }
                })
                .unwrap();

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            execute_skill,
            read_local_file,
            write_local_file,
            show_notification,
            get_system_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
async fn execute_skill(name: String, params: serde_json::Value) -> Result<String, String> {
    // Call backend API
    Ok("Skill executed successfully".into())
}

#[tauri::command]
fn read_local_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|e| e.to_string())
}

#[tauri::command]
fn write_local_file(path: String, content: String) -> Result<(), String> {
    std::fs::write(path, content).map_err(|e| e.to_string())
}

#[tauri::command]
fn show_notification(title: String, body: String) {
    tauri::api::notification::Notification::new("com.supremeai.app")
        .title(title)
        .body(body)
        .show()
        .unwrap();
}

#[tauri::command]
fn get_system_info() -> Result<String, String> {
    let sys_info = format!(
        "OS: {:?}, CPU: {} cores, Memory: {} MB",
        std::env::consts::OS,
        num_cpus::get(),
        sys_info::mem_info().map(|m| (m.total_mem - m.free_mem) / 1024 / 1024).unwrap_or(0)
    );
    Ok(sys_info)
}

