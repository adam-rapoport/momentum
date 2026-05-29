use std::sync::Mutex;
use std::time::Duration;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Keeps the sidecar handle alive for the app's lifetime.
struct BackendProcess(Mutex<Option<CommandChild>>);
/// PID of the sidecar's PyInstaller bootloader, used to terminate the whole
/// backend process subtree on exit.
struct BackendPid(u32);

/// Poll the backend's /health endpoint until it answers, or give up after
/// `attempts`. Runs on a plain thread (blocking HTTP) so it never blocks the
/// async runtime or the UI thread.
fn wait_for_health(url: &str, attempts: u32) -> bool {
    for _ in 0..attempts {
        if ureq::get(url).timeout(Duration::from_secs(2)).call().is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    false
}

/// Terminate the backend sidecar AND its child worker. The PyInstaller one-file
/// binary runs as a bootloader parent plus a Python child that holds the port;
/// the bootloader does not forward a kill to that child, so we must target both
/// or the worker orphans (keeping port 8000 bound after the app quits).
fn terminate_backend(pid: u32) {
    use std::process::Command;
    let p = pid.to_string();
    // Children first (the uvicorn worker), then the bootloader itself.
    let _ = Command::new("/usr/bin/pkill").args(["-KILL", "-P", &p]).status();
    let _ = Command::new("/bin/kill").args(["-9", &p]).status();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Launch the bundled Python backend (PyInstaller one-file) as a
            // sidecar listening on 127.0.0.1:8000.
            let (mut rx, child) = app.shell().sidecar("pmomentum-backend")?.spawn()?;
            let pid = child.pid();
            app.manage(BackendPid(pid));
            app.manage(BackendProcess(Mutex::new(Some(child))));

            // Drain the backend's stdout/stderr so its pipe never backs up, and
            // surface it in our logs for debugging.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) = event {
                        log::info!("[backend] {}", String::from_utf8_lossy(&bytes).trim_end());
                    }
                }
            });

            // Reveal the window only once the backend is serving, so the user
            // never sees a UI pointed at a backend that isn't listening yet.
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                if !wait_for_health("http://127.0.0.1:8000/health", 120) {
                    log::error!("backend did not become healthy in time; showing window anyway");
                }
                if let Some(window) = handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // Kill the backend (and its worker child) whenever the app is exiting,
            // so no orphaned Python process keeps port 8000 bound. Handle both the
            // request and the final exit to be robust to how the quit was triggered.
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                eprintln!("[tauri] app exiting — terminating backend subtree");
                if let Some(pid) = app_handle.try_state::<BackendPid>() {
                    terminate_backend(pid.0);
                }
            }
        });
}
