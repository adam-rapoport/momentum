use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Keeps the sidecar handle alive for the app's lifetime.
struct BackendProcess(Mutex<Option<CommandChild>>);
/// PID of the sidecar's PyInstaller bootloader, used to terminate the whole
/// backend process subtree on exit.
struct BackendPid(u32);
/// Per-launch shared secret for the local backend API. Generated here, passed
/// to the sidecar via PMOMENTUM_AUTH_TOKEN, and handed to the webview through
/// the `get_backend_token` command. Without it, any website the user visits
/// could drive the backend on 127.0.0.1 (see backend/app/security.py).
struct AuthToken(String);

#[tauri::command]
fn get_backend_token(token: tauri::State<AuthToken>) -> String {
    token.0.clone()
}

/// 32 random bytes, hex-encoded. Reads /dev/urandom directly — fine for this
/// macOS/Linux-only desktop build (terminate_backend below already shells out
/// to Unix tools).
fn generate_token() -> String {
    use std::io::Read;
    let mut buf = [0u8; 32];
    std::fs::File::open("/dev/urandom")
        .and_then(|mut f| f.read_exact(&mut buf))
        .expect("failed to read /dev/urandom for the backend auth token");
    buf.iter().map(|b| format!("{b:02x}")).collect()
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
    let token = generate_token();
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_backend_token])
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // Launch the bundled Python backend (PyInstaller one-file) as a
            // sidecar listening on 127.0.0.1:8000, with the per-launch auth
            // token it must require on every API/WS request.
            let (mut rx, child) = app
                .shell()
                .sidecar("pmomentum-backend")?
                .env("PMOMENTUM_AUTH_TOKEN", &token)
                .spawn()?;
            let pid = child.pid();
            app.manage(BackendPid(pid));
            app.manage(BackendProcess(Mutex::new(Some(child))));
            app.manage(AuthToken(token.clone()));

            // Drain the backend's stdout/stderr so its pipe never backs up, and
            // surface it in our logs for debugging.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) = event {
                        log::info!("[backend] {}", String::from_utf8_lossy(&bytes).trim_end());
                    }
                }
            });

            // The window is shown immediately (tauri.conf.json `visible: true`) so
            // the user sees the web app's "Starting pMomentum…" loading screen right
            // away instead of a blank wait. The web app (see BootGate) polls the
            // backend's readiness and only renders the real UI once it's serving, so
            // we no longer hide the window here.
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
