import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  CONFIG_PADRAO,
  SNAPSHOT_INICIAL,
  type Comando,
  type SnapshotApp,
} from "../types";

/** True quando a página está rodando dentro do WebView do Tauri. */
export function emTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

interface StatusMotor {
  tipo: "status";
  etapa: string;
  texto: string;
}

interface ErroMotor {
  tipo: "erro_fatal";
  texto: string;
}

type MensagemMotor =
  | ({ tipo: "snapshot" } & Partial<SnapshotApp>)
  | StatusMotor
  | ErroMotor
  | { tipo: "pronto"; versao?: string; simulacao?: boolean }
  | { tipo: "encerrado" };

function normalizar(payload: Partial<SnapshotApp>): SnapshotApp {
  return {
    ...SNAPSHOT_INICIAL,
    ...payload,
    gaze: { ...SNAPSHOT_INICIAL.gaze, ...payload.gaze },
    calibracao: { ...SNAPSHOT_INICIAL.calibracao, ...payload.calibracao },
    pranchaCalib: { ...SNAPSHOT_INICIAL.pranchaCalib, ...payload.pranchaCalib },
    historico: { ...SNAPSHOT_INICIAL.historico, ...payload.historico },
    config: {
      ...CONFIG_PADRAO,
      ...payload.config,
      deteccao: { ...CONFIG_PADRAO.deteccao, ...payload.config?.deteccao },
      calibracao: { ...CONFIG_PADRAO.calibracao, ...payload.config?.calibracao },
      prancha: { ...CONFIG_PADRAO.prancha, ...payload.config?.prancha },
      camera: { ...CONFIG_PADRAO.camera, ...payload.config?.camera },
      perfis: { ...CONFIG_PADRAO.perfis, ...payload.config?.perfis },
      feedback: { ...CONFIG_PADRAO.feedback, ...payload.config?.feedback },
      aparencia: { ...CONFIG_PADRAO.aparencia, ...payload.config?.aparencia },
      janela: { ...CONFIG_PADRAO.janela, ...payload.config?.janela },
    },
    conectado: true,
    bootTexto: null,
    erroMotor: null,
  };
}

class RealBackend {
  private snapshot: SnapshotApp = { ...SNAPSHOT_INICIAL };
  private listeners = new Set<() => void>();
  private registrado = false;
  private encerrando = false;

  constructor() {
    if (emTauri()) void this.registrar();
  }

  private async registrar(): Promise<void> {
    if (this.registrado) return;
    this.registrado = true;
    try {
      await listen<MensagemMotor>("motor", (evento) => this.receber(evento.payload));
      await listen("motor_encerrado", () => {
        if (this.encerrando) return;
        this.aplicar({
          conectado: false,
          bootTexto: null,
          erroMotor:
            "O motor de rastreamento foi encerrado. Feche e abra o aplicativo novamente.",
        });
      });
      // Só inicia o processo depois que os listeners acima estão ativos,
      // para não perder mensagens de erro da inicialização.
      await invoke("iniciar_motor");
    } catch (erro) {
      this.aplicar({
        conectado: false,
        bootTexto: null,
        erroMotor: `Não foi possível conectar ao motor local: ${String(erro)}`,
      });
    }
  }

  private receber(mensagem: MensagemMotor): void {
    if (!mensagem || typeof mensagem !== "object") return;

    if (mensagem.tipo === "snapshot") {
      this.aplicar(normalizar(mensagem));
      return;
    }
    if (mensagem.tipo === "status") {
      this.aplicar({ bootTexto: mensagem.texto, conectado: false });
      return;
    }
    if (mensagem.tipo === "erro_fatal") {
      this.aplicar({
        conectado: false,
        bootTexto: null,
        erroMotor: mensagem.texto,
      });
      return;
    }
    if (mensagem.tipo === "pronto") {
      this.aplicar({ conectado: true, bootTexto: null });
      return;
    }
    if (mensagem.tipo === "encerrado") {
      if (!this.encerrando) {
        this.aplicar({
          conectado: false,
          bootTexto: null,
          erroMotor: "O motor de rastreamento foi encerrado.",
        });
      }
    }
  }

  private aplicar(patch: Partial<SnapshotApp>): void {
    this.snapshot = { ...this.snapshot, ...patch };
    this.notificar();
  }

  private notificar(): void {
    for (const listener of this.listeners) listener();
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): SnapshotApp => this.snapshot;

  comando = (comando: Comando): void => {
    if (!emTauri()) return;
    if (comando.tipo === "sair") this.encerrando = true;
    invoke("enviar_comando", { comando }).catch((erro) => {
      this.aplicar({
        erroMotor: `Falha ao enviar o comando para o motor: ${String(erro)}`,
      });
    });
  };

  /** Usado pelo App para saber se deve encerrar o processo ao fechar a janela. */
  estaEncerrando = (): boolean => this.encerrando;
}

export const realBackend = new RealBackend();
