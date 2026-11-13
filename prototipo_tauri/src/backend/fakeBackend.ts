import {
  BLOCOS,
  CONFIG_PADRAO,
  SNAPSHOT_INICIAL,
  bloco,
  type BlocoId,
  type Comando,
  type SnapshotApp,
} from "../types";

/**
 * Backend de demonstração usado somente quando a interface roda no
 * navegador (`npm run dev`), sem o motor Python.
 *
 * Ele reproduz o mesmo contrato de snapshot + comandos do motor real,
 * inclusive todas as telas de calibração e perfis, para permitir revisar
 * o visual e os fluxos sem webcam.
 */

const INTERVALO_ENVIO_MS = 33;
const CONFIRMA_MS = 1200;
const PAUSA_MS = 650;
const DURACAO_COLETA_MS = 3000;

type FaseBoard = "ocioso" | "focando" | "confirmado";

const REFERENCIAS_INICIAIS: Record<string, [number, number]> = Object.fromEntries(
  BLOCOS.map((b) => [b.id, [b.ratio.x, b.ratio.y] as [number, number]]),
);

const SNAPSHOT_DEMO: SnapshotApp = {
  ...SNAPSHOT_INICIAL,
  perfil: "Ana",
  perfilAtivo: "Ana",
  perfis: ["Ana", "João"],
  cameraOk: true,
  backend: "demonstração",
  rostoOk: true,
  poseOk: true,
  distanciaRosto: 0.22,
  distanciaEstado: "boa",
  distanciaAviso: false,
  gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
  pranchaCalibrada: true,
  calibracaoSimNao: true,
  dwellMs: 700,
  simulacao: true,
  conectado: true,
  bootTexto: null,
  erroMotor: null,
  config: CONFIG_PADRAO,
  calibracao: {
    ...SNAPSHOT_INICIAL.calibracao,
    mediaEsq: 0.3,
    mediaDir: 0.7,
    diferenca: 0.4,
    sucesso: true,
  },
  pranchaCalib: {
    ...SNAPSHOT_INICIAL.pranchaCalib,
    referencias: REFERENCIAS_INICIAIS,
    distancia: 0.4,
    sucesso: true,
  },
};

class FakeBackend {
  private snapshot: SnapshotApp = { ...SNAPSHOT_DEMO };
  private listeners = new Set<() => void>();
  private ultimoTs = 0;
  private acumuladoEnvio = 0;
  private avisoAte = 0;

  private boardFase: FaseBoard = "ocioso";
  private boardAlvo: BlocoId | null = null;
  private boardAcumulado = 0;
  private boardConfirmadoEm = 0;
  private boardPausaAte = 0;
  private boardAuto: BlocoId | null = null;
  private boardUltimo: BlocoId | null = null;
  private pointer: BlocoId | null = null;

  private simFase: FaseBoard = "ocioso";
  private simAlvo: "SIM" | "NAO" | null = null;
  private simAcumulado = 0;
  private simConfirmadoEm = 0;
  private simPausaAte = 0;
  private simUltimo: "SIM" | "NAO" | null = null;

  private coletaInicio = 0;
  private coletaAmostras = 0;

  private recentralizacaoAnterior: Record<string, [number, number]> | null = null;
  private distanciaRuimDesde = 0;
  private distanciaBoaDesde = 0;

  constructor() {
    requestAnimationFrame(this.tick);
  }

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = (): SnapshotApp => this.snapshot;

  comando = (comando: Comando): void => {
    switch (comando.tipo) {
      case "abrir_prancha":
        if (!this.snapshot.pranchaCalibrada) {
          this.avisar("Prancha sem calibração. Use Calibração para calibrar.");
          return;
        }
        this.resetarBoard();
        this.boardPausaAte = performance.now() + PAUSA_MS;
        this.distanciaRuimDesde = 0;
        this.distanciaBoaDesde = 0;
        this.aplicar({
          tela: "PRANCHA_ATIVO",
          foco: null,
          progresso: 0,
          confirmado: null,
          distanciaRosto: 0.22,
          distanciaEstado: "boa",
          distanciaAviso: false,
        });
        break;

      case "abrir_sim_nao":
        if (!this.snapshot.calibracaoSimNao) {
          this.avisar("Calibração SIM/NÃO ausente ou fraca.");
          return;
        }
        this.resetarSimNao();
        this.simPausaAte = performance.now() + PAUSA_MS;
        this.aplicar({ tela: "ATIVO", foco: null, progresso: 0, confirmado: null });
        break;

      case "abrir_calibracao":
        this.aplicar({ tela: "ESCOLHER_CALIBRACAO" });
        break;

      case "calibrar_prancha":
        this.coletaInicio = 0;
        this.coletaAmostras = 0;
        this.recentralizacaoAnterior = null;
        this.aplicar({
          tela: "PRANCHA_CALIB_PREPARAR",
          podeDesfazerRecentralizacao: false,
          pranchaCalib: {
            ...this.snapshot.pranchaCalib,
            blocoId: BLOCOS[0].id,
            indice: 0,
            total: BLOCOS.length,
            coletando: false,
            aguardando: true,
            progresso: 0,
            amostras: 0,
            descartadas: 0,
            distancia: 0,
            sucesso: false,
            referencias: {},
          },
        });
        break;

      case "calibrar_sim_nao":
        this.coletaInicio = 0;
        this.coletaAmostras = 0;
        this.aplicar({
          tela: "CALIB_PREPARAR",
          calibracao: {
            ...this.snapshot.calibracao,
            fase: "ESQUERDA",
            alvo: "SIM",
            coletando: false,
            progresso: 0,
            amostras: 0,
            descartadas: 0,
            sucesso: false,
          },
        });
        break;

      case "abrir_perfis":
        this.aplicar({ tela: "SELECIONAR_PERFIL" });
        break;

      case "novo_perfil":
        this.aplicar({ tela: "NOVO_PERFIL", nomeDigitado: "" });
        break;

      case "selecionar_perfil": {
        if (!this.snapshot.perfis.includes(comando.nome)) {
          this.avisar(`Perfil '${comando.nome}' não encontrado.`);
          return;
        }
        this.aplicar({ perfil: comando.nome, perfilAtivo: comando.nome, tela: "MENU" });
        this.recentralizacaoAnterior = null;
        this.aplicar({ podeDesfazerRecentralizacao: false });
        break;
      }

      case "criar_perfil": {
        const nome = comando.nome.trim();
        if (!nome) {
          this.avisar("Digite um nome para o perfil.");
          return;
        }
        if (!/^[A-Za-z0-9_-]{1,20}$/.test(nome)) {
          this.avisar("Use letras, números, '_' ou '-' (máximo 20).");
          return;
        }
        if (this.snapshot.perfis.includes(nome)) {
          this.avisar(`O perfil '${nome}' já existe.`);
          return;
        }
        this.coletaInicio = 0;
        this.coletaAmostras = 0;
        this.recentralizacaoAnterior = null;
        this.aplicar({
          perfis: [...this.snapshot.perfis, nome],
          perfil: nome,
          perfilAtivo: nome,
          nomeDigitado: "",
          tela: "PRANCHA_CALIB_PREPARAR",
          pranchaCalibrada: false,
          pranchaFraca: false,
          podeDesfazerRecentralizacao: false,
          calibracaoSimNao: false,
          calibracaoFraca: false,
          pranchaCalib: {
            ...this.snapshot.pranchaCalib,
            blocoId: BLOCOS[0].id,
            indice: 0,
            total: BLOCOS.length,
            coletando: false,
            aguardando: true,
            progresso: 0,
            amostras: 0,
            descartadas: 0,
            distancia: 0,
            sucesso: false,
            referencias: {},
          },
        });
        break;
      }

      case "modo_cuidador":
        this.aplicar({ tela: "MODO_CUIDADOR" });
        break;

      case "configuracoes":
        this.aplicar({ tela: "CONFIGURACOES" });
        break;

      case "iniciar_coleta":
        this.iniciarColeta(performance.now());
        break;

      case "atualizar_config":
        this.aplicar({
          config: {
            ...comando.config,
            configPath: this.snapshot.config.configPath,
          },
          dwellMs: comando.config.deteccao.dwellMs,
          piscadaHabilitada: comando.config.deteccao.piscadaHabilitada,
        });
        this.avisar("Configurações salvas.");
        break;

      case "recentralizar": {
        const referencias = this.snapshot.pranchaCalib.referencias;
        if (Object.keys(referencias).length < BLOCOS.length) {
          this.avisar("Calibre a prancha antes de recentralizar.");
          return;
        }
        const novas: Record<string, [number, number]> = {};
        for (const [id, [x, y]] of Object.entries(referencias)) {
          const nx = x + comando.dx;
          const ny = y + comando.dy;
          if (nx < 0 || nx > 1 || ny < 0 || ny > 1) {
            this.avisar(
              "Recentralização recusada: o ajuste sairia da área calibrada.",
            );
            return;
          }
          novas[id] = [nx, ny];
        }
        this.recentralizacaoAnterior = Object.fromEntries(
          Object.entries(referencias).map(([id, ponto]) => [
            id,
            [ponto[0], ponto[1]] as [number, number],
          ]),
        );
        this.aplicar({
          podeDesfazerRecentralizacao: true,
          pranchaCalib: { ...this.snapshot.pranchaCalib, referencias: novas },
        });
        this.avisar("Olhar recentralizado.");
        break;
      }

      case "desfazer_recentralizacao": {
        const anterior = this.recentralizacaoAnterior;
        if (!anterior) {
          this.avisar("Nada para desfazer.");
          return;
        }
        this.recentralizacaoAnterior = null;
        this.aplicar({
          podeDesfazerRecentralizacao: false,
          pranchaCalib: {
            ...this.snapshot.pranchaCalib,
            referencias: anterior,
          },
        });
        this.avisar("Recentralização desfeita.");
        break;
      }

      case "voltar":
        this.voltar();
        break;

      case "sair":
        break;
    }
  };

  definirPointer = (id: BlocoId | null): void => {
    this.pointer = id;
    if (id) {
      this.boardPausaAte = 0;
      this.boardAuto = null;
    }
  };

  // -----------------------------------------------------------------
  private aplicar(patch: Partial<SnapshotApp>): void {
    this.snapshot = { ...this.snapshot, ...patch };
    this.notificar();
  }

  private avisar(texto: string): void {
    this.avisoAte = performance.now() + 3200;
    this.aplicar({ aviso: texto });
  }

  private notificar(): void {
    for (const listener of this.listeners) listener();
  }

  private voltar(): void {
    const tela = this.snapshot.tela;
    if (tela === "NOVO_PERFIL") {
      this.aplicar({ tela: "SELECIONAR_PERFIL", nomeDigitado: "" });
      return;
    }
    if (tela === "MENU") return;
    this.resetarBoard();
    this.resetarSimNao();
    this.aplicar({
      tela: "MENU",
      foco: null,
      progresso: 0,
      confirmado: null,
      gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
    });
  }

  private resetarBoard(): void {
    this.boardFase = "ocioso";
    this.boardAlvo = null;
    this.boardAcumulado = 0;
    this.boardConfirmadoEm = 0;
    this.boardPausaAte = 0;
    this.boardAuto = null;
    this.pointer = null;
  }

  private resetarSimNao(): void {
    this.simFase = "ocioso";
    this.simAlvo = null;
    this.simAcumulado = 0;
    this.simConfirmadoEm = 0;
    this.simPausaAte = 0;
  }

  private iniciarColeta(agora: number): void {
    this.coletaInicio = agora;
    this.coletaAmostras = 0;
    if (this.snapshot.tela === "CALIB_PREPARAR") {
      this.aplicar({
        tela: "CALIB_COLETANDO",
        calibracao: {
          ...this.snapshot.calibracao,
          coletando: true,
          progresso: 0,
          amostras: 0,
          descartadas: 0,
        },
      });
    } else if (this.snapshot.tela === "PRANCHA_CALIB_PREPARAR") {
      this.aplicar({
        tela: "PRANCHA_CALIB_COLETANDO",
        pranchaCalib: {
          ...this.snapshot.pranchaCalib,
          coletando: true,
          aguardando: false,
          progresso: 0,
          amostras: 0,
          descartadas: 0,
        },
      });
    }
  }

  private escolherAuto(): BlocoId {
    const opcoes = BLOCOS.filter((b) => b.id !== this.boardUltimo);
    return opcoes[Math.floor(Math.random() * opcoes.length)].id;
  }

  private tick = (ts: number): void => {
    const delta = this.ultimoTs === 0 ? 16 : Math.min(ts - this.ultimoTs, 100);
    this.ultimoTs = ts;

    if (this.snapshot.aviso && ts > this.avisoAte) {
      this.snapshot = { ...this.snapshot, aviso: null };
    }

    switch (this.snapshot.tela) {
      case "PRANCHA_ATIVO":
        this.avancarBoard(delta, ts);
        break;
      case "ATIVO":
        this.avancarSimNao(delta, ts);
        break;
      case "CALIB_COLETANDO":
        this.avancarCalibracao(ts);
        break;
      case "PRANCHA_CALIB_COLETANDO":
        this.avancarCalibracaoPrancha(ts);
        break;
      case "MODO_CUIDADOR":
        this.simularOlharCuidador(ts);
        break;
      default:
        break;
    }

    this.acumuladoEnvio += delta;
    if (this.acumuladoEnvio >= INTERVALO_ENVIO_MS) {
      this.acumuladoEnvio = 0;
      this.notificar();
    }

    requestAnimationFrame(this.tick);
  };

  private simularOlharCuidador(agora: number): void {
    const t = agora / 1000;
    const x = 0.5 + Math.sin(t * 0.55) * 0.24;
    const y = 0.5 + Math.cos(t * 0.41) * 0.2;
    const esq = x + Math.sin(t * 2.1) * 0.012;
    // A cada ~9s a divergência sobe de propósito para demonstrar o filtro.
    const ciclo = t % 9;
    const divergindo = ciclo > 7.4 && ciclo < 8.1;
    const dir = divergindo ? esq + 0.34 : x - Math.sin(t * 2.1) * 0.012;
    const divergencia = Math.abs(esq - dir);

    // Distância informativa com histerese: a cada ~18 s o rosto fica
    // longe, depois perto, para demonstrar o indicador e o aviso.
    const det = this.snapshot.config.deteccao;
    const cicloDist = t % 18;
    const medida = cicloDist > 15 ? 0.44 : cicloDist > 12 ? 0.075 : 0.21;
    let estadoDist: "boa" | "longe" | "perto" | "indefinida" = "indefinida";
    if (det.distanciaHabilitada) {
      estadoDist =
        medida < det.distanciaLongeAbaixo
          ? "longe"
          : medida > det.distanciaPertoAcima
            ? "perto"
            : "boa";
    }
    const foraDaFaixa = estadoDist === "longe" || estadoDist === "perto";
    if (!det.distanciaHabilitada) {
      this.distanciaRuimDesde = 0;
      this.distanciaBoaDesde = 0;
    } else if (foraDaFaixa) {
      this.distanciaBoaDesde = 0;
      if (!this.distanciaRuimDesde) this.distanciaRuimDesde = agora;
    } else {
      this.distanciaRuimDesde = 0;
      if (!this.distanciaBoaDesde) this.distanciaBoaDesde = agora;
    }
    let avisoDist = this.snapshot.distanciaAviso;
    if (
      !avisoDist &&
      this.distanciaRuimDesde &&
      agora - this.distanciaRuimDesde >= det.distanciaEntradaMs
    ) {
      avisoDist = true;
    }
    if (
      avisoDist &&
      this.distanciaBoaDesde &&
      agora - this.distanciaBoaDesde >= det.distanciaSaidaMs
    ) {
      avisoDist = false;
    }
    if (!det.distanciaHabilitada) avisoDist = false;

    this.snapshot = {
      ...this.snapshot,
      cameraOk: true,
      rostoOk: true,
      poseOk: true,
      olhosFechados: false,
      distanciaRosto: det.distanciaHabilitada
        ? Number(medida.toFixed(4))
        : 0,
      distanciaEstado: estadoDist,
      distanciaAviso: avisoDist,
      gaze: {
        x,
        y,
        esq,
        dir,
        valido: true,
        divergencia,
        divergenciaOk: divergencia <= this.snapshot.config.deteccao.divergenciaMax,
      },
    };
  }

  private avancarBoard(delta: number, agora: number): void {
    if (this.boardFase === "confirmado") {
      if (agora - this.boardConfirmadoEm >= CONFIRMA_MS) {
        this.boardFase = "ocioso";
        this.boardAlvo = null;
        this.boardAcumulado = 0;
        this.boardAuto = null;
        this.boardPausaAte = agora + PAUSA_MS;
        this.snapshot = {
          ...this.snapshot,
          foco: null,
          progresso: 0,
          confirmado: null,
          gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
        };
      }
      return;
    }

    let alvo: BlocoId | null = this.pointer;
    if (!alvo && agora >= this.boardPausaAte) {
      if (!this.boardAuto) this.boardAuto = this.escolherAuto();
      alvo = this.boardAuto;
    }

    if (!alvo) {
      this.boardAlvo = null;
      this.boardAcumulado = 0;
      this.snapshot = {
        ...this.snapshot,
        foco: null,
        progresso: 0,
        gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
      };
      return;
    }

    if (alvo !== this.boardAlvo) {
      this.boardAlvo = alvo;
      this.boardAcumulado = 0;
    }
    this.boardFase = "focando";
    this.boardAcumulado += delta;
    const progresso = Math.min(1, this.boardAcumulado / this.snapshot.dwellMs);
    const centro = bloco(alvo).ratio;

    this.snapshot = {
      ...this.snapshot,
      foco: alvo,
      progresso,
      rostoOk: true,
      poseOk: true,
      olhosFechados: false,
      gaze: {
        x: centro.x + (Math.random() - 0.5) * 0.008,
        y: centro.y + (Math.random() - 0.5) * 0.008,
        esq: centro.x,
        dir: centro.x,
        valido: true,
      },
    };

    if (progresso >= 1) {
      this.boardFase = "confirmado";
      this.boardConfirmadoEm = agora;
      this.boardUltimo = alvo;
      this.boardAuto = null;
      this.snapshot = { ...this.snapshot, confirmado: alvo, progresso: 1 };
    }
  }

  private avancarSimNao(delta: number, agora: number): void {
    if (this.simFase === "confirmado") {
      if (agora - this.simConfirmadoEm >= CONFIRMA_MS) {
        this.simFase = "ocioso";
        this.simAlvo = null;
        this.simAcumulado = 0;
        this.simPausaAte = agora + PAUSA_MS;
        this.snapshot = {
          ...this.snapshot,
          foco: null,
          progresso: 0,
          confirmado: null,
          gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
        };
      }
      return;
    }

    if (agora < this.simPausaAte) return;
    if (!this.simAlvo) {
      this.simAlvo = this.simUltimo === "SIM" ? "NAO" : "SIM";
    }
    const alvo = this.simAlvo;
    this.simFase = "focando";
    this.simAcumulado += delta;
    const progresso = Math.min(1, this.simAcumulado / this.snapshot.dwellMs);
    const x = alvo === "SIM" ? 0.25 : 0.85;
    this.snapshot = {
      ...this.snapshot,
      foco: alvo,
      progresso,
      gaze: { x, y: 0.5, esq: x, dir: x, valido: true },
    };
    if (progresso >= 1) {
      this.simFase = "confirmado";
      this.simConfirmadoEm = agora;
      this.simUltimo = alvo;
      this.snapshot = { ...this.snapshot, confirmado: alvo, progresso: 1 };
    }
  }

  private avancarCalibracao(agora: number): void {
    const certa = this.snapshot.calibracao;
    if (!this.coletaInicio) return;
    const decorrido = agora - this.coletaInicio;
    this.coletaAmostras = Math.min(200, this.coletaAmostras + 1);
    const minimo = certa.minimo;
    const progressoTempo = Math.min(1, decorrido / DURACAO_COLETA_MS);
    const progressoAmostras = Math.min(1, this.coletaAmostras / minimo);
    const progresso = Math.min(progressoTempo, progressoAmostras);
    const x = certa.alvo === "SIM" ? 0.25 : 0.8;

    this.snapshot = {
      ...this.snapshot,
      gaze: { x, y: 0.5, esq: x, dir: x, valido: true },
      rostoOk: true,
      poseOk: true,
      calibracao: {
        ...certa,
        coletando: true,
        progresso,
        amostras: this.coletaAmostras,
        descartadas: Math.floor(this.coletaAmostras / 37),
      },
    };

    if (decorrido >= DURACAO_COLETA_MS && this.coletaAmostras >= minimo) {
      if (certa.fase === "ESQUERDA") {
        this.coletaInicio = 0;
        this.coletaAmostras = 0;
        this.snapshot = {
          ...this.snapshot,
          tela: "CALIB_PREPARAR",
          gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
          calibracao: {
            ...certa,
            fase: "DIREITA",
            alvo: "NAO",
            coletando: false,
            progresso: 0,
            amostras: 0,
            descartadas: 0,
            mediaEsq: 0.25,
          },
        };
      } else {
        this.coletaInicio = 0;
        this.snapshot = {
          ...this.snapshot,
          tela: "CALIB_CONCLUIDA",
          calibracaoSimNao: true,
          calibracaoFraca: false,
          gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
          calibracao: {
            ...certa,
            coletando: false,
            progresso: 1,
            amostras: this.coletaAmostras,
            mediaEsq: 0.25,
            mediaDir: 0.8,
            diferenca: 0.55,
            sucesso: true,
          },
        };
      }
    }
  }

  private avancarCalibracaoPrancha(agora: number): void {
    const calib = this.snapshot.pranchaCalib;
    if (!this.coletaInicio || !calib.blocoId) return;
    const decorrido = agora - this.coletaInicio;
    this.coletaAmostras = Math.min(200, this.coletaAmostras + 1);
    const progressoTempo = Math.min(1, decorrido / DURACAO_COLETA_MS);
    const progressoAmostras = Math.min(1, this.coletaAmostras / calib.minimo);
    const progresso = Math.min(progressoTempo, progressoAmostras);
    const alvo = bloco(calib.blocoId).ratio;

    this.snapshot = {
      ...this.snapshot,
      gaze: { x: alvo.x, y: alvo.y, esq: alvo.x, dir: alvo.x, valido: true },
      rostoOk: true,
      poseOk: true,
      pranchaCalib: {
        ...calib,
        progresso,
        amostras: this.coletaAmostras,
        descartadas: Math.floor(this.coletaAmostras / 41),
      },
    };

    if (decorrido < DURACAO_COLETA_MS || this.coletaAmostras < calib.minimo) return;

    const referencias = {
      ...calib.referencias,
      [calib.blocoId]: [alvo.x, alvo.y] as [number, number],
    };
    const indice = calib.indice + 1;
    this.coletaInicio = 0;
    this.coletaAmostras = 0;

    if (indice >= BLOCOS.length) {
      this.snapshot = {
        ...this.snapshot,
        tela: "PRANCHA_CALIB_CONCLUIDA",
        pranchaCalibrada: true,
        pranchaFraca: false,
        gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
        pranchaCalib: {
          ...calib,
          indice,
          blocoId: null,
          coletando: false,
          aguardando: false,
          progresso: 1,
          amostras: this.coletaAmostras,
          distancia: 0.4,
          sucesso: true,
          referencias,
        },
      };
      return;
    }

    this.snapshot = {
      ...this.snapshot,
      tela: "PRANCHA_CALIB_PREPARAR",
      gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: true },
      pranchaCalib: {
        ...calib,
        indice,
        blocoId: BLOCOS[indice].id,
        coletando: false,
        aguardando: true,
        progresso: 0,
        amostras: 0,
        descartadas: 0,
        referencias,
      },
    };
  }
}

export const fakeBackend = new FakeBackend();
