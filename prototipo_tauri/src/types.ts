export type Tela =
  | "MENU"
  | "ESCOLHER_CALIBRACAO"
  | "SELECIONAR_PERFIL"
  | "NOVO_PERFIL"
  | "CALIB_PREPARAR"
  | "CALIB_COLETANDO"
  | "CALIB_CONCLUIDA"
  | "ATIVO"
  | "PRANCHA_CALIB_PREPARAR"
  | "PRANCHA_CALIB_COLETANDO"
  | "PRANCHA_CALIB_CONCLUIDA"
  | "PRANCHA_ATIVO"
  | "MODO_CUIDADOR"
  | "CONFIGURACOES";

export type BlocoId = "oi" | "comer" | "beber" | "banheiro";

export interface BlocoPrancha {
  id: BlocoId;
  rotulo: string;
  cor: string;
  /** Centro do olhar calibrado para este cartão (ratio 0..1). */
  ratio: { x: number; y: number };
}

export const BLOCOS: BlocoPrancha[] = [
  { id: "oi", rotulo: "OI", cor: "#F4C6D3", ratio: { x: 0.30, y: 0.30 } },
  { id: "comer", rotulo: "COMER", cor: "#F6D58C", ratio: { x: 0.70, y: 0.30 } },
  { id: "beber", rotulo: "BEBER", cor: "#A3DDD2", ratio: { x: 0.30, y: 0.70 } },
  { id: "banheiro", rotulo: "BANHEIRO", cor: "#B3CDF3", ratio: { x: 0.70, y: 0.70 } },
];

export function bloco(id: BlocoId): BlocoPrancha {
  return BLOCOS.find((b) => b.id === id) ?? BLOCOS[0];
}

export function rotulo(id: string | null): string {
  if (!id) return "";
  return BLOCOS.find((b) => b.id === id)?.rotulo ?? id;
}

export function ehBloco(id: string | null): id is BlocoId {
  return !!id && BLOCOS.some((b) => b.id === id);
}

export interface Gaze {
  x: number;
  y: number;
  esq: number;
  dir: number;
  valido: boolean;
  /** Diferença absoluta entre os ratios dos dois olhos (0..1). */
  divergencia?: number;
  /** Falso quando os olhos divergem além de deteccao.divergenciaMax. */
  divergenciaOk?: boolean;
}

/** Indicador informativo de distância do rosto até a câmera. */
export type DistanciaEstado = "boa" | "longe" | "perto" | "indefinida";

export interface CalibracaoSimNao {
  fase: "ESQUERDA" | "DIREITA";
  alvo: "SIM" | "NAO";
  coletando: boolean;
  progresso: number;
  amostras: number;
  minimo: number;
  descartadas: number;
  mediaEsq: number;
  mediaDir: number;
  diferenca: number;
  sucesso: boolean;
}

export interface PranchaCalib {
  blocoId: BlocoId | null;
  indice: number;
  total: number;
  coletando: boolean;
  aguardando: boolean;
  progresso: number;
  amostras: number;
  minimo: number;
  descartadas: number;
  distancia: number;
  sucesso: boolean;
  referencias: Record<string, [number, number]>;
}

export interface ConfigResumo {
  deteccao: {
    dwellMs: number;
    toleranciaPerdaMs: number;
    exibicaoConfirmacaoMs: number;
    alphaEma: number;
    tamanhoHistoricoGrafico: number;
    semRostoMs: number;
    divergenciaMax: number;
    compensarYaw: boolean;
    yawSensibilidade: number;
    confiancaMinima: number;
    distanciaHabilitada: boolean;
    distanciaLongeAbaixo: number;
    distanciaPertoAcima: number;
    distanciaEntradaMs: number;
    distanciaSaidaMs: number;
    piscadaHabilitada: boolean;
    limiarEar: number;
    piscadaMs: number;
    focoMinimoMs: number;
  };
  calibracao: {
    duracaoMs: number;
    minAmostras: number;
    maxYawGraus: number;
    maxPitchGraus: number;
    maxRollGraus: number;
    diferencaMinima: number;
  };
  prancha: {
    distanciaMinimaBoa: number;
    raioMax: number;
  };
  camera: {
    indice: number;
    largura: number;
    altura: number;
    fps: number;
    backend: string;
    timeoutInicialMs: number;
  };
  perfis: { validadeDias: number };
  feedback: { som: boolean };
  aparencia: {
    /** Tema visual do aplicativo. */
    tema: "claro" | "escuro";
  };
  janela: {
    /** Resolução desejada da janela: "1280x720" ou "1920x1080". */
    resolucao: string;
    fullscreen: boolean;
  };
  configPath: string;
}

/** Configurações que o usuário pode alterar pela interface. */
export type AjustesConfig = Omit<ConfigResumo, "configPath">;

export interface SnapshotApp {
  tela: Tela;
  perfil: string | null;
  perfilAtivo: string | null;
  perfis: string[];
  nomeDigitado: string;
  cameraOk: boolean;
  backend: string;
  semSinal: boolean;
  segundosSemFrame: number | null;
  rostoOk: boolean;
  poseOk: boolean;
  olhosFechados: boolean;
  avisoSemRosto: boolean;
  avisoCabeca: boolean;
  /** Medida relativa do rosto (0..1); 0 quando indisponível. */
  distanciaRosto: number;
  distanciaEstado: DistanciaEstado;
  /** Aviso de distância já passou pela histerese (só informativo). */
  distanciaAviso: boolean;
  /** Há uma recentralização que pode ser desfeita nesta sessão. */
  podeDesfazerRecentralizacao: boolean;
  gaze: Gaze;
  foco: string | null;
  progresso: number;
  confirmado: string | null;
  aviso: string | null;
  pranchaCalibrada: boolean;
  pranchaFraca: boolean;
  calibracaoSimNao: boolean;
  calibracaoFraca: boolean;
  dwellMs: number;
  piscadaHabilitada: boolean;
  versao: string;
  simulacao: boolean;
  calibracao: CalibracaoSimNao;
  pranchaCalib: PranchaCalib;
  historico: { esq: number[]; dir: number[] };
  config: ConfigResumo;
  /** Preenchido pelo cliente (não vem necessariamente do motor). */
  conectado: boolean;
  bootTexto: string | null;
  erroMotor: string | null;
}

export const CONFIG_PADRAO: ConfigResumo = {
  deteccao: {
    dwellMs: 700,
    toleranciaPerdaMs: 180,
    exibicaoConfirmacaoMs: 1500,
    alphaEma: 0.35,
    tamanhoHistoricoGrafico: 200,
    semRostoMs: 2000,
    divergenciaMax: 0.25,
    compensarYaw: false,
    yawSensibilidade: 0.004,
    confiancaMinima: 0.5,
    distanciaHabilitada: true,
    distanciaLongeAbaixo: 0.11,
    distanciaPertoAcima: 0.34,
    distanciaEntradaMs: 800,
    distanciaSaidaMs: 600,
    piscadaHabilitada: true,
    limiarEar: 0.15,
    piscadaMs: 350,
    focoMinimoMs: 150,
  },
  calibracao: {
    duracaoMs: 3000,
    minAmostras: 30,
    maxYawGraus: 25,
    maxPitchGraus: 25,
    maxRollGraus: 30,
    diferencaMinima: 0.03,
  },
  prancha: { distanciaMinimaBoa: 0.02, raioMax: 0.55 },
  camera: {
    indice: 0,
    largura: 1280,
    altura: 720,
    fps: 30,
    backend: "auto",
    timeoutInicialMs: 6000,
  },
  perfis: { validadeDias: 7 },
  feedback: { som: true },
  aparencia: { tema: "claro" },
  janela: { resolucao: "1920x1080", fullscreen: true },
  configPath: "",
};

export const SNAPSHOT_INICIAL: SnapshotApp = {
  tela: "MENU",
  perfil: null,
  perfilAtivo: null,
  perfis: [],
  nomeDigitado: "",
  cameraOk: false,
  backend: "nenhum",
  semSinal: false,
  segundosSemFrame: null,
  rostoOk: false,
  poseOk: true,
  olhosFechados: false,
  avisoSemRosto: false,
  avisoCabeca: false,
  distanciaRosto: 0,
  distanciaEstado: "indefinida",
  distanciaAviso: false,
  podeDesfazerRecentralizacao: false,
  gaze: { x: 0.5, y: 0.5, esq: 0.5, dir: 0.5, valido: false },
  foco: null,
  progresso: 0,
  confirmado: null,
  aviso: null,
  pranchaCalibrada: false,
  pranchaFraca: false,
  calibracaoSimNao: false,
  calibracaoFraca: false,
  dwellMs: 700,
  piscadaHabilitada: true,
  versao: "2.2.4",
  simulacao: false,
  calibracao: {
    fase: "ESQUERDA",
    alvo: "SIM",
    coletando: false,
    progresso: 0,
    amostras: 0,
    minimo: 30,
    descartadas: 0,
    mediaEsq: 0.35,
    mediaDir: 0.65,
    diferenca: 0.3,
    sucesso: false,
  },
  pranchaCalib: {
    blocoId: null,
    indice: 0,
    total: 4,
    coletando: false,
    aguardando: false,
    progresso: 0,
    amostras: 0,
    minimo: 30,
    descartadas: 0,
    distancia: 0,
    sucesso: false,
    referencias: {},
  },
  historico: { esq: [], dir: [] },
  config: CONFIG_PADRAO,
  conectado: false,
  bootTexto: "Conectando ao motor de rastreamento...",
  erroMotor: null,
};

export type Comando =
  | { tipo: "abrir_prancha" }
  | { tipo: "abrir_sim_nao" }
  | { tipo: "abrir_calibracao" }
  | { tipo: "calibrar_prancha" }
  | { tipo: "calibrar_sim_nao" }
  | { tipo: "abrir_perfis" }
  | { tipo: "novo_perfil"; nome?: string }
  | { tipo: "selecionar_perfil"; nome: string }
  | { tipo: "criar_perfil"; nome: string }
  | { tipo: "modo_cuidador" }
  | { tipo: "configuracoes" }
  | { tipo: "iniciar_coleta" }
  | { tipo: "atualizar_config"; config: AjustesConfig }
  | { tipo: "recentralizar"; dx: number; dy: number }
  | { tipo: "desfazer_recentralizacao" }
  | { tipo: "voltar" }
  | { tipo: "sair" };

export type AcaoMenu = "perfis" | "calibracao" | "cuidador" | "config";
