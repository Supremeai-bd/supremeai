#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::{Manager, Runtime, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem, CustomMenuItem, SystemTrayEvent::MenuEvent};
use tauri::api::{fs::read_text_file, notification::{Notification, NotificationAction}, updater};
use std::sync::Mutex;

struct AppState {
    is_visible: Mutex<bool>,
}

#[tauri::command]
fn read_local_file(path: String) -> Result<String, String> {
    match read_text_file(std::path::Path::new(&path)) {
        Ok(content) => Ok(content),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
fn show_notification(title: String, body: String) -> Result<(), String> {
    let notification = Notification::new(&title)
        .body(&body)
        .show()
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn toggle_window_visibility(app: &tauri::App) -> Result<(), String> {
    let window = app.get_window("main").ok_or("Main window not found")?;
    let is_visible = window.is_visible().map_err(|e| e.to_string())?;
    if is_visible {
        window.hide().map_err(|e| e.to_string())?;
    } else {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn toggle_window(app_handle: tauri::AppHandle) -> Result<(), String> {
    let app = app_handle.app_handle();
    toggle_window_visibility(&app)
}

#[tauri::command]
fn check_for_updates(app: tauri::AppHandle) -> Result<(), String> {
    updater::build()
        .update_callback(move |event| {
            if let updater::UpdateResponse::UpdateAvailable(info) = event {
                let _ = Notification::new("Update Available")
                    .body(&format!("Version {} is available. Please restart the application.", info.version))
                    .show();
                let _ = app.restart();
            }
        })
        .run()
        .map_err(|e| e.to_string())?;
    Ok(())
}

fn main() {
    let context = tauri::generate_context!();
    let app_state = AppState {
        is_visible: Mutex::new(true),
    };

    let show_menu_item = CustomMenuItem::new("show".to_string(), "Show");
    let quit_menu_item = CustomMenuItem::new("quit".to_string(), "Quit");
    let tray_menu = SystemTrayMenu::new()
        .add_item(show_menu_item)
        .add_item(quit_menu_item);
    let system_tray = SystemTray::new().with_menu(tray_menu);

    tauri::Builder::default()
        .manage(app_state)
        .system_tray(system_tray)
        .on_system_tray_event(|app, event| match event {
            MenuEvent { id, .. } => {
                match id.as_str() {
                    "show" => {
                        let _ = toggle_window_visibility(app);
                    }
                    "quit" => {
                        std::process::exit(0);
                    }
                    _ => {}
                }
            }
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            read_local_file,
            show_notification,
            toggle_window,
            check_for_updates
        ])
        .setup(|app| {
            let app_handle = app.handle();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = tauri::api::global_shortcut::register("ctrl+shift+s", move || {
                    let _ = app_handle.emit_all("toggle-visibility", ());
                }) {
                    eprintln!("Failed to register global shortcut: {:?}", e);
                }
            });

            let app_handle = app.handle();
            app.listen_global("toggle-visibility", move |_| {
                let _ = toggle_window_visibility(&app_handle);
            });

            Ok(())
        })
        .run(context)
        .expect("error while running tauri application");
}