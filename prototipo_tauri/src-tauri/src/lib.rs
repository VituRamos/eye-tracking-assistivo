//! Aplicativo Tauri da Prancha Assistiva.
//!
//! A interface React é só apresentação: câmera, MediaPipe, dwell,
//! calibração e perfis continuam no motor Python (`ponte.py`, empacotado
//! como `eye-core.exe`). A comunicação é feita por stdin/stdout, com um
//! objeto JSON por linha, sem portas de rede.

use std::{
    fs::OpenOptions,
    io::{BufRead, BufReader, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::Mutex,
    thread,
};

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager, State};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

struct Processo {
    child: Child,
    stdin: ChildStdin,
}

#[derive(Default)]
struct EstadoMotor {
    processo: Mutex<Option<Processo>>,
}

/// Pasta gravável do aplicativo (perfis, logs e settings.yaml).
fn pasta_dados(app: &AppHandle) -> Result<PathBuf, String> {
    let pasta = app
        .path()
        .app_local_data_dir()
        .map_err(|e| format!("Não foi possível resolver a pasta de dados: {e}"))?;
    std::fs::create_dir_all(&pasta)
        .map_err(|e| format!("Não foi possível criar '{}': {e}", pasta.display()))?;
    Ok(pasta)
}

/// Descobre o executável do motor (instalado ou em desenvolvimento).
fn resolver_motor(app: &AppHandle) -> Result<(PathBuf, Vec<String>), String> {
    if let Ok(caminho) = std::env::var("EYE_CORE_EXE") {
        let programa = PathBuf::from(caminho);
        if programa.exists() {
            return Ok((programa, Vec::new()));
        }
    }

    let mut candidatos: Vec<PathBuf> = Vec::new();
    if let Ok(recursos) = app.path().resource_dir() {
        candidatos.push(recursos.join("eye-core").join("eye-core.exe"));
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(pasta) = exe.parent() {
            candidatos.push(pasta.join("eye-core").join("eye-core.exe"));
        }
    }
    for candidato in &candidatos {
        if candidato.exists() {
            return Ok((candidato.clone(), Vec::new()));
        }
    }

    // Desenvolvimento: usa o Python do projeto e o ponte.py ao lado.
    let raiz = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..");
    let python = raiz.join(".venv").join("Scripts").join("python.exe");
    let ponte = raiz.join("ponte.py");
    if python.exists() && ponte.exists() {
        return Ok((
            python,
            vec![ponte.to_string_lossy().to_string()],
        ));
    }

    let listados = candidatos
        .iter()
        .map(|c| c.display().to_string())
        .collect::<Vec<_>>()
        .join("\n  ");
    Err(format!(
        "Motor de rastreamento não encontrado. Locais verificados:\n  {listados}\n  {}\n  {}",
        python.display(),
        ponte.display()
    ))
}

/// Inicia o motor uma única vez. Chamado pela interface depois de
/// registrar os listeners de eventos.
#[tauri::command]
fn iniciar_motor(app: AppHandle, estado: State<'_, EstadoMotor>) -> Result<(), String> {
    let mut guard = estado
        .processo
        .lock()
        .map_err(|_| "Estado do motor indisponível.".to_string())?;
    if guard.is_some() {
        return Ok(());
    }

    let dados = pasta_dados(&app)?;
    let config = dados.join("settings.yaml");
    let (programa, mut argumentos) = resolver_motor(&app)?;
    argumentos.push("--dados".into());
    argumentos.push(dados.to_string_lossy().to_string());
    argumentos.push("--config".into());
    argumentos.push(config.to_string_lossy().to_string());

    let mut comando = Command::new(&programa);
    comando
        .args(&argumentos)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(pasta) = programa.parent() {
        comando.current_dir(pasta);
    }
    #[cfg(windows)]
    comando.creation_flags(CREATE_NO_WINDOW);

    let mut child = comando
        .spawn()
        .map_err(|e| format!("Não foi possível iniciar '{}': {e}", programa.display()))?;

    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "O motor não abriu a entrada padrão.".to_string())?;
    let stdout = child
        .stdout
        .take()
        .ok_or_else(|| "O motor não abriu a saída padrão.".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "O motor não abriu a saída de erro.".to_string())?;

    // stdout -> evento "motor" no WebView.
    let app_leitura = app.clone();
    thread::spawn(move || {
        let leitor = BufReader::new(stdout);
        for linha in leitor.lines() {
            let Ok(linha) = linha else { break };
            let linha = linha.trim();
            if linha.is_empty() {
                continue;
            }
            match serde_json::from_str::<Value>(linha) {
                Ok(valor) => {
                    let _ = app_leitura.emit("motor", valor);
                }
                Err(erro) => {
                    eprintln!("[motor] linha inválida ignorada: {erro}");
                }
            }
        }
        let _ = app_leitura.emit("motor_encerrado", Value::Null);
    });

    // stderr -> arquivo de diagnóstico (o motor também grava logs próprios).
    let caminho_log = dados.join("logs").join("ponte_stderr.log");
    thread::spawn(move || {
        if let Some(pasta) = caminho_log.parent() {
            let _ = std::fs::create_dir_all(pasta);
        }
        let mut arquivo = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&caminho_log)
            .ok();
        let mut leitor = BufReader::new(stderr);
        let mut buffer = Vec::new();
        loop {
            buffer.clear();
            match leitor.read_until(b'\n', &mut buffer) {
                Ok(0) => break,
                Ok(_) => {
                    let texto = String::from_utf8_lossy(&buffer);
                    if let Some(arquivo) = arquivo.as_mut() {
                        let _ = arquivo.write_all(texto.as_bytes());
                        let _ = arquivo.flush();
                    }
                    eprint!("{texto}");
                }
                Err(_) => break,
            }
        }
    });

    *guard = Some(Processo { child, stdin });

    let _ = app.emit(
        "motor",
        json!({
            "tipo": "status",
            "etapa": "inicio",
            "texto": "Iniciando o motor de rastreamento..."
        }),
    );
    Ok(())
}

/// Envia um comando JSON ao motor (uma linha no stdin).
#[tauri::command]
fn enviar_comando(comando: Value, estado: State<'_, EstadoMotor>) -> Result<(), String> {
    let mut guard = estado
        .processo
        .lock()
        .map_err(|_| "Estado do motor indisponível.".to_string())?;
    let processo = guard
        .as_mut()
        .ok_or_else(|| "O motor ainda não foi iniciado.".to_string())?;

    let mut linha = serde_json::to_string(&comando)
        .map_err(|e| format!("Comando inválido: {e}"))?;
    linha.push('\n');
    processo
        .stdin
        .write_all(linha.as_bytes())
        .and_then(|_| processo.stdin.flush())
        .map_err(|e| format!("Não foi possível enviar o comando ao motor: {e}"))
}

/// Encerra o motor (usado ao fechar a janela).
fn encerrar_motor(app: &AppHandle) {
    let estado = app.state::<EstadoMotor>();
    let Ok(mut guard) = estado.processo.lock() else {
        return;
    };
    if let Some(mut processo) = guard.take() {
        let _ = processo.child.kill();
        let _ = processo.child.wait();
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(EstadoMotor::default())
        .invoke_handler(tauri::generate_handler![iniciar_motor, enviar_comando])
        .build(tauri::generate_context!())
        .expect("erro ao montar o aplicativo");

    app.run(|handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            encerrar_motor(handle);
        }
    });
}
