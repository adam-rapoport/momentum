use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use tauri::{AppHandle, Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Keeps the sidecar handle alive for the app's lifetime.
struct BackendProcess(Mutex<Option<CommandChild>>);
/// PID of the sidecar's PyInstaller bootloader, used to terminate the whole
/// backend process subtree on exit. Mutex because a respawn replaces it.
struct BackendPid(Mutex<u32>);
/// Per-launch shared secret for the local backend API. Generated here, passed
/// to the sidecar via PMOMENTUM_AUTH_TOKEN, and handed to the webview through
/// the `get_backend_token` command. Without it, any website the user visits
/// could drive the backend on 127.0.0.1 (see backend/app/security.py).
struct AuthToken(String);

/// True once the app has started exiting — a Terminated event caused by our
/// own kill must not be reported as a crash (or trigger a respawn).
static EXITING: AtomicBool = AtomicBool::new(false);
/// Whether the single automatic respawn after an unexpected sidecar death has
/// been used. One attempt only: a backend that dies twice is genuinely broken
/// and respawn-looping it would just burn CPU and spam logs.
static RESPAWN_USED: AtomicBool = AtomicBool::new(false);

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

/// Spawn the bundled Python backend (PyInstaller one-file) as a sidecar
/// listening on 127.0.0.1, store its handle/PID in managed state, and watch
/// its event stream: stdout/stderr are surfaced in our logs, and an
/// unexpected exit is logged, emitted to the webview (`backend-terminated`)
/// and answered with one automatic respawn attempt.
fn spawn_backend(app: &AppHandle, token: &str) -> Result<(), tauri_plugin_shell::Error> {
    let (mut rx, child) = app
        .shell()
        .sidecar("pmomentum-backend")?
        .env("PMOMENTUM_AUTH_TOKEN", token)
        .spawn()?;
    let pid = child.pid();
    *app.state::<BackendPid>().0.lock().unwrap() = pid;
    *app.state::<BackendProcess>().0.lock().unwrap() = Some(child);

    let app_handle = app.clone();
    let token = token.to_string();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                // Drain the backend's stdout/stderr so its pipe never backs
                // up, and surface it in our logs for debugging.
                CommandEvent::Stdout(bytes) | CommandEvent::Stderr(bytes) => {
                    log::info!("[backend] {}", String::from_utf8_lossy(&bytes).trim_end());
                }
                CommandEvent::Error(err) => {
                    eprintln!("[tauri] backend io error: {err}");
                    log::error!("[backend] io error: {err}");
                }
                CommandEvent::Terminated(payload) => {
                    if EXITING.load(Ordering::SeqCst) {
                        break; // our own shutdown kill — expected
                    }
                    eprintln!(
                        "[tauri] backend terminated unexpectedly (pid {pid}, code {:?}, signal {:?})",
                        payload.code, payload.signal
                    );
                    log::error!(
                        "[backend] terminated unexpectedly: code {:?}, signal {:?}",
                        payload.code,
                        payload.signal
                    );
                    let _ = app_handle.emit(
                        "backend-terminated",
                        serde_json::json!({
                            "code": payload.code,
                            "signal": payload.signal,
                        }),
                    );
                    if !RESPAWN_USED.swap(true, Ordering::SeqCst) {
                        eprintln!("[tauri] attempting one backend respawn");
                        match spawn_backend(&app_handle, &token) {
                            Ok(()) => {
                                let _ = app_handle.emit("backend-respawned", ());
                            }
                            Err(e) => {
                                eprintln!("[tauri] backend respawn failed: {e}");
                                let _ = app_handle
                                    .emit("backend-respawn-failed", e.to_string());
                            }
                        }
                    }
                    break;
                }
                // CommandEvent is non_exhaustive.
                _ => {}
            }
        }
    });
    Ok(())
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

            // Managed state first so spawn_backend (and its respawn path) can
            // update the handle/PID slots in place.
            app.manage(BackendPid(Mutex::new(0)));
            app.manage(BackendProcess(Mutex::new(None)));
            app.manage(AuthToken(token.clone()));

            spawn_backend(app.handle(), &token)?;

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
                // Flag first so the Terminated event from our own kill isn't
                // treated as a crash; the swap also makes the kill idempotent
                // when both ExitRequested and Exit fire.
                if !EXITING.swap(true, Ordering::SeqCst) {
                    eprintln!("[tauri] app exiting — terminating backend subtree");
                    if let Some(pid) = app_handle.try_state::<BackendPid>() {
                        let pid = *pid.0.lock().unwrap();
                        if pid != 0 {
                            terminate_backend(pid);
                        }
                    }
                }
            }
        });
}
