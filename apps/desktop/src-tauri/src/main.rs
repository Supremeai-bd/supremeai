#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use tauri::{Manager, Runtime, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem, CustomMenuItem, SystemTrayEvent::MenuEvent};
use tauri::api::{fs::read_text_file, notification::{Notification, NotificationAction}, global_shortcut, updater::{self, Message}};
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

#[tauri::command]
fn toggle_window(app_handle: tauri::AppHandle) -> Result<(), String> {
    let window = app_handle.get_window("main").ok_or("Main window not found")?;
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
fn check_for_updates() -> Result<(), String> {
    updater::build()
        .update_callback(move |event| {
            if let Message::UpdateAvailable = event {
                // Notify the user about the update
                let _ = Notification::new("Update Available")
                    .body("A new version is available. Please restart the application.")
                    .show();
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

    // Build the system tray menu
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
            SystemTrayEvent::MenuEvent { id, .. } => {
                let item = match id.as_str() {
                    "show" => {
                        // Toggle window visibility
                        let window = app.get_window("main").expect("Failed to get window");
                        if window.is_visible().unwrap_or(false) {
                            let _ = window.hide();
                        } else {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                        return;
                    }
                    "quit" => {
                        std::process::exit(0);
                    }
                    _ => return,
                };
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
            // Set up global shortcut for Ctrl+Shift+S to toggle window
            let app_handle = app.app_handle();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = global_shortcut::register("ctrl+shift+s", move || {
                    // Emit a custom event or call a command to toggle window
                    if let Err(e) = app_handle.emit_all("toggle-visibility", ()) {
                        eprintln!("Failed to emit toggle-visibility event: {}", e);
                    }
                }) {
                    eprintln!("Failed to register global shortcut: {}", e);
                }
            });

            // Listen for the custom event to toggle window
            let app_handle = app.app_handle();
            app.listen_global("toggle-visibility", move |_| {
                if let Err(e) = AppState::toggle_window(app_handle.clone()) {
                    eprintln!("Failed to toggle window: {}", e);
                }
            });

            Ok(())
        })
        .run(context)
        .expect("error while running tauri application");
}

// Implement the toggle_window method for AppState
impl AppState {
    fn toggle_window(app_handle: tauri::AppHandle) -> Result<(), String> {
        let window = app_handle.get_window("main").ok_or("Main window not found")?;
        let is_visible = window.is_visible().map_err(|e| e.to_string())?;
        if is_visible {
            window.hide().map_err(|e| e.to_string())?;
        } else {
            window.show().map_err(|e| e.to_string())?;
            window.set_focus().map_err(|e| e.to_string())?;
        }
        Ok(())
    }
}