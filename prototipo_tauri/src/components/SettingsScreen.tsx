import { RotateCcw, Save, Undo2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import {
  CONFIG_PADRAO,
  type AjustesConfig,
  type ConfigResumo,
  type SnapshotApp,
} from "../types";
import { ScreenHeader } from "./ScreenHeader";

interface Props {
  snapshot: SnapshotApp;
  onSalvar: (config: AjustesConfig) => void;
  onVoltar: () => void;
}

const ENTRADA =
  "h-[42px] w-full rounded-[10px] border border-borda bg-superficie px-3 text-[15px] font-semibold text-texto outline-none transition focus:border-apoio focus:ring-2 focus:ring-neutro";

const ABAS = [
  { id: "deteccao", rotulo: "Detecção" },
  { id: "distancia", rotulo: "Distância" },
  { id: "piscada", rotulo: "Piscada" },
  { id: "calibracao", rotulo: "Calibração" },
  { id: "prancha", rotulo: "Prancha" },
  { id: "camera", rotulo: "Câmera" },
  { id: "sistema", rotulo: "Sistema" },
] as const;

type AbaId = (typeof ABAS)[number]["id"];
type Secao = keyof AjustesConfig;
type ValorCampo = number | string | boolean;

function extrairAjustes(config: ConfigResumo): AjustesConfig {
  const copia = JSON.parse(JSON.stringify(config)) as AjustesConfig & {
    configPath?: string;
  };
  delete copia.configPath;
  return copia;
}

export function SettingsScreen({ snapshot, onSalvar, onVoltar }: Props) {
  const [aba, setAba] = useState<AbaId>("deteccao");
  const [rascunho, setRascunho] = useState<AjustesConfig>(() =>
    extrairAjustes(snapshot.config),
  );

  // Pré-visualiza o tema enquanto o cuidador alterna; ao sair sem salvar,
  // o tema salvo volta a valer.
  const temaRascunho = rascunho.aparencia.tema;
  const temaSalvo = snapshot.config.aparencia.tema;
  useEffect(() => {
    document.documentElement.dataset.tema = temaRascunho;
    return () => {
      document.documentElement.dataset.tema = temaSalvo;
    };
  }, [temaRascunho, temaSalvo]);

  const original = extrairAjustes(snapshot.config);
  const alterado = JSON.stringify(rascunho) !== JSON.stringify(original);

  const atualizar = (secao: Secao, campo: string, valor: ValorCampo) => {
    setRascunho(
      (prev) =>
        ({
          ...prev,
          [secao]: { ...(prev[secao] as Record<string, unknown>), [campo]: valor },
        }) as AjustesConfig,
    );
  };

  const descartar = () => setRascunho(extrairAjustes(snapshot.config));
  const restaurarPadroes = () => setRascunho(extrairAjustes(CONFIG_PADRAO));

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader
        titulo="Configurações"
        subtitulo="Ajuste o aplicativo sem editar arquivos"
      />

      <aside className="absolute left-[56px] top-[132px] w-[214px]">
        <p className="mb-[10px] text-[12px] font-semibold uppercase tracking-[0.12em] text-apoio">
          Categorias
        </p>
        <div className="space-y-[6px]">
          {ABAS.map((item) => (
            <button
              key={item.id}
              onClick={() => setAba(item.id)}
              className={`h-[44px] w-full rounded-[11px] px-4 text-left text-[16px] transition ${
                aba === item.id
                  ? "bg-texto font-semibold text-fundo"
                  : "text-apoio hover:bg-neutro/70"
              }`}
            >
              {item.rotulo}
            </button>
          ))}
        </div>

        <div className="mt-[20px] rounded-[14px] border border-borda bg-superficie px-[16px] py-[14px]">
          <p className="text-[13px] font-semibold text-texto">Privado e local</p>
          <p className="mt-1 text-[12px] leading-snug text-apoio">
            Tudo fica salvo neste computador. Nada é enviado para a internet.
          </p>
        </div>
      </aside>

      <section className="absolute left-[296px] top-[132px] h-[490px] w-[928px] rounded-[20px] border border-borda bg-superficie px-[28px] py-[22px]">
        <h2 className="text-[21px] font-semibold text-texto">
          {ABAS.find((item) => item.id === aba)?.rotulo}
        </h2>
        <p className="mt-1 text-[13px] text-apoio">{AJUDA_ABA[aba]}</p>

        <div className="mt-[18px] grid grid-cols-2 gap-x-[24px] gap-y-[14px]">
          {aba === "deteccao" && (
            <>
              <CampoNumero
                rotulo="Olhar fixo (dwell)"
                ajuda="Tempo de olhar contínuo para confirmar uma opção."
                valor={rascunho.deteccao.dwellMs}
                onChange={(v) => atualizar("deteccao", "dwellMs", v)}
                min={100}
                max={5000}
                step={50}
                sufixo="ms"
              />
              <CampoNumero
                rotulo="Tolerância de perda"
                ajuda="Perda curta de foco tolerada sem zerar o progresso."
                valor={rascunho.deteccao.toleranciaPerdaMs}
                onChange={(v) => atualizar("deteccao", "toleranciaPerdaMs", v)}
                min={0}
                max={2000}
                step={10}
                sufixo="ms"
              />
              <CampoNumero
                rotulo="Confirmação na tela"
                ajuda="Quanto tempo a mensagem de seleção permanece visível."
                valor={rascunho.deteccao.exibicaoConfirmacaoMs}
                onChange={(v) => atualizar("deteccao", "exibicaoConfirmacaoMs", v)}
                min={200}
                max={10000}
                step={100}
                sufixo="ms"
              />
              <CampoNumero
                rotulo="Suavização do olhar"
                ajuda="Perto de 1 reage mais rápido; perto de 0 fica mais estável."
                valor={rascunho.deteccao.alphaEma}
                onChange={(v) => atualizar("deteccao", "alphaEma", v)}
                min={0.05}
                max={1}
                step={0.05}
              />
              <CampoNumero
                rotulo="Histórico do gráfico"
                ajuda="Quantidade de amostras mantidas para o histórico."
                valor={rascunho.deteccao.tamanhoHistoricoGrafico}
                onChange={(v) => atualizar("deteccao", "tamanhoHistoricoGrafico", v)}
                min={20}
                max={2000}
                step={10}
                sufixo="amostras"
              />
              <CampoNumero
                rotulo="Aviso sem rosto"
                ajuda="Frames sem rosto antes de pedir para reposicionar."
                valor={rascunho.deteccao.limiteFramesSemRosto}
                onChange={(v) => atualizar("deteccao", "limiteFramesSemRosto", v)}
                min={1}
                max={600}
                step={1}
                sufixo="frames"
              />
              <CampoNumero
                rotulo="Divergência entre olhos"
                ajuda="Acima deste valor o quadro é ignorado. Aumente para quem tem estrabismo."
                valor={rascunho.deteccao.divergenciaMax}
                onChange={(v) => atualizar("deteccao", "divergenciaMax", v)}
                min={0.02}
                max={1}
                step={0.01}
              />
            </>
          )}

          {aba === "distancia" && (
            <>
              <Alternador
                rotulo="Indicador de distância"
                ajuda="Avisa quando o rosto fica longe ou perto demais. Não bloqueia seleção nem calibração."
                valor={rascunho.deteccao.distanciaHabilitada}
                onChange={(v) => atualizar("deteccao", "distanciaHabilitada", v)}
              />
              <CampoNumero
                rotulo="Limite de rosto longe"
                ajuda="Abaixo desta medida, o rosto é considerado longe da câmera."
                valor={rascunho.deteccao.distanciaLongeAbaixo}
                onChange={(v) => atualizar("deteccao", "distanciaLongeAbaixo", v)}
                min={0.02}
                max={Math.max(0.03, rascunho.deteccao.distanciaPertoAcima - 0.01)}
                step={0.01}
              />
              <CampoNumero
                rotulo="Limite de rosto perto"
                ajuda="Acima desta medida, o rosto é considerado perto demais."
                valor={rascunho.deteccao.distanciaPertoAcima}
                onChange={(v) => atualizar("deteccao", "distanciaPertoAcima", v)}
                min={rascunho.deteccao.distanciaLongeAbaixo + 0.01}
                max={0.9}
                step={0.01}
              />
              <CampoNumero
                rotulo="Tempo para avisar"
                ajuda="Tempo contínuo fora da faixa antes de mostrar o aviso."
                valor={rascunho.deteccao.distanciaEntradaMs}
                onChange={(v) => atualizar("deteccao", "distanciaEntradaMs", v)}
                min={0}
                max={5000}
                step={50}
                sufixo="ms"
              />
              <CampoNumero
                rotulo="Tempo para sumir"
                ajuda="Tempo contínuo de volta à faixa boa para o aviso desaparecer."
                valor={rascunho.deteccao.distanciaSaidaMs}
                onChange={(v) => atualizar("deteccao", "distanciaSaidaMs", v)}
                min={0}
                max={5000}
                step={50}
                sufixo="ms"
              />
              <p className="col-span-2 mt-1 rounded-[10px] bg-neutro px-3 py-2 text-[13px] text-apoio">
                O aviso é só informativo: a seleção, o tempo de olhar e a
                calibração continuam funcionando normalmente. A medida é
                relativa e pode variar entre câmeras.
              </p>
            </>
          )}

          {aba === "piscada" && (
            <>
              <Alternador
                rotulo="Confirmar com piscada"
                ajuda="Além do olhar fixo, uma piscada também confirma."
                valor={rascunho.deteccao.piscadaHabilitada}
                onChange={(v) => atualizar("deteccao", "piscadaHabilitada", v)}
              />
              <CampoNumero
                rotulo="Limiar de olho fechado"
                ajuda="Abaixo deste valor, o olho é considerado fechado."
                valor={rascunho.deteccao.limiarEar}
                onChange={(v) => atualizar("deteccao", "limiarEar", v)}
                min={0.05}
                max={0.5}
                step={0.01}
              />
              <CampoNumero
                rotulo="Duração da piscada"
                ajuda="Tempo mínimo de olho fechado para confirmar."
                valor={rascunho.deteccao.piscadaMs}
                onChange={(v) => atualizar("deteccao", "piscadaMs", v)}
                min={100}
                max={2000}
                step={10}
                sufixo="ms"
              />
              <CampoNumero
                rotulo="Foco mínimo"
                ajuda="Tempo de foco antes de aceitar a confirmação por piscada."
                valor={rascunho.deteccao.focoMinimoMs}
                onChange={(v) => atualizar("deteccao", "focoMinimoMs", v)}
                min={0}
                max={1000}
                step={10}
                sufixo="ms"
              />
            </>
          )}

          {aba === "calibracao" && (
            <>
              <CampoNumero
                rotulo="Duração por etapa"
                ajuda="Tempo de coleta em cada lado ou cartão."
                valor={rascunho.calibracao.duracaoMs}
                onChange={(v) => atualizar("calibracao", "duracaoMs", v)}
                min={500}
                max={15000}
                step={100}
                sufixo="ms"
              />
              <CampoNumero
                rotulo="Amostras mínimas"
                ajuda="Amostras válidas necessárias para concluir."
                valor={rascunho.calibracao.minAmostras}
                onChange={(v) => atualizar("calibracao", "minAmostras", v)}
                min={1}
                max={300}
                step={1}
                sufixo="amostras"
              />
              <CampoNumero
                rotulo="Ângulo máximo da cabeça"
                ajuda="Acima disso, a cabeça está virada demais e a amostra é ignorada."
                valor={rascunho.calibracao.maxYawGraus}
                onChange={(v) => atualizar("calibracao", "maxYawGraus", v)}
                min={5}
                max={90}
                step={1}
                sufixo="°"
              />
              <CampoNumero
                rotulo="Separação mínima"
                ajuda="Distância mínima entre os pontos para a calibração ser boa."
                valor={rascunho.calibracao.diferencaMinima}
                onChange={(v) => atualizar("calibracao", "diferencaMinima", v)}
                min={0.005}
                max={1}
                step={0.005}
              />
            </>
          )}

          {aba === "prancha" && (
            <>
              <CampoNumero
                rotulo="Distância mínima entre cartões"
                ajuda="Abaixo disso, dois cartões ficam no mesmo lugar e a prancha é fraca."
                valor={rascunho.prancha.distanciaMinimaBoa}
                onChange={(v) => atualizar("prancha", "distanciaMinimaBoa", v)}
                min={0.001}
                max={1}
                step={0.001}
              />
              <CampoNumero
                rotulo="Raio de alcance"
                ajuda="Distância máxima do olhar até o cartão para ainda considerá-lo."
                valor={rascunho.prancha.raioMax}
                onChange={(v) => atualizar("prancha", "raioMax", v)}
                min={0.06}
                max={2}
                step={0.01}
              />
            </>
          )}

          {aba === "camera" && (
            <>
              <CampoNumero
                rotulo="Índice da câmera"
                ajuda="0 é a webcam padrão; use 1, 2… para outras câmeras."
                valor={rascunho.camera.indice}
                onChange={(v) => atualizar("camera", "indice", v)}
                min={0}
                max={10}
                step={1}
              />
              <CampoNumero
                rotulo="Largura da captura"
                ajuda="Resolução usada pela câmera (a interface não muda)."
                valor={rascunho.camera.largura}
                onChange={(v) => atualizar("camera", "largura", v)}
                min={320}
                max={3840}
                step={160}
                sufixo="px"
              />
              <CampoNumero
                rotulo="Altura da captura"
                ajuda="Resolução usada pela câmera (a interface não muda)."
                valor={rascunho.camera.altura}
                onChange={(v) => atualizar("camera", "altura", v)}
                min={240}
                max={2160}
                step={120}
                sufixo="px"
              />
              <CampoNumero
                rotulo="Quadros por segundo"
                ajuda="FPS pedido à câmera."
                valor={rascunho.camera.fps}
                onChange={(v) => atualizar("camera", "fps", v)}
                min={1}
                max={120}
                step={1}
                sufixo="fps"
              />
              <CampoSelecao
                rotulo="Backend da câmera"
                ajuda="Auto tenta MSMF, DirectShow e o padrão do sistema."
                valor={rascunho.camera.backend}
                onChange={(v) => atualizar("camera", "backend", v)}
                opcoes={[
                  ["auto", "Automático"],
                  ["msmf", "MSMF"],
                  ["dshow", "DirectShow"],
                  ["any", "Qualquer"],
                ]}
              />
              <CampoNumero
                rotulo="Tempo de abertura"
                ajuda="Quanto esperar pelo primeiro frame da câmera."
                valor={rascunho.camera.timeoutInicialMs}
                onChange={(v) => atualizar("camera", "timeoutInicialMs", v)}
                min={1000}
                max={30000}
                step={500}
                sufixo="ms"
              />
              <p className="col-span-2 mt-1 rounded-[10px] bg-atencao-fundo px-3 py-2 text-[13px] text-atencao">
                As mudanças de câmera passam a valer depois de reiniciar o aplicativo.
              </p>
            </>
          )}

          {aba === "sistema" && (
            <>
              <CampoSelecao
                rotulo="Resolução da tela"
                ajuda="Usada quando a tela cheia está desligada. Se não couber, a janela reduz proporcionalmente."
                valor={rascunho.janela.resolucao}
                onChange={(v) => atualizar("janela", "resolucao", v)}
                opcoes={[
                  ["1280x720", "1280 x 720"],
                  ["1920x1080", "1920 x 1080"],
                ]}
              />
              <Alternador
                rotulo="Abrir em tela cheia"
                ajuda="Padrão do aplicativo. A tecla F11 também alterna a qualquer momento."
                valor={rascunho.janela.fullscreen}
                onChange={(v) => atualizar("janela", "fullscreen", v)}
              />
              <Alternador
                rotulo="Modo escuro"
                ajuda="Fundo escuro para ambientes com pouca luz. A prévia é imediata."
                valor={rascunho.aparencia.tema === "escuro"}
                onChange={(v) =>
                  atualizar("aparencia", "tema", v ? "escuro" : "claro")
                }
              />
              <CampoNumero
                rotulo="Validade do perfil"
                ajuda="Depois deste prazo, o app sugere recalibrar."
                valor={rascunho.perfis.validadeDias}
                onChange={(v) => atualizar("perfis", "validadeDias", v)}
                min={1}
                max={365}
                step={1}
                sufixo="dias"
              />
              <Alternador
                rotulo="Som de confirmação"
                ajuda="Bipe curto quando uma opção é selecionada."
                valor={rascunho.feedback.som}
                onChange={(v) => atualizar("feedback", "som", v)}
              />
            </>
          )}
        </div>
      </section>

      <footer className="absolute left-[296px] top-[638px] flex h-[52px] w-[928px] items-center justify-between">
        <p className={`text-[14px] ${alterado ? "text-atencao" : "text-apoio"}`}>
          {alterado ? "Há alterações não salvas." : "As configurações estão atualizadas."}
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={restaurarPadroes}
            className="inline-flex h-[44px] items-center gap-2 rounded-full px-4 text-[14px] text-apoio transition hover:bg-neutro"
          >
            <RotateCcw size={16} strokeWidth={2.2} />
            Restaurar padrões
          </button>
          <button
            onClick={descartar}
            disabled={!alterado}
            className="inline-flex h-[44px] items-center gap-2 rounded-full px-4 text-[14px] text-apoio transition hover:bg-neutro disabled:opacity-40"
          >
            <Undo2 size={16} strokeWidth={2.2} />
            Descartar
          </button>
          <button
            onClick={() => onSalvar(rascunho)}
            disabled={!alterado}
            className="inline-flex h-[44px] items-center gap-2 rounded-full bg-texto px-[22px] text-[15px] font-semibold text-fundo transition hover:opacity-90 disabled:opacity-40"
          >
            <Save size={17} strokeWidth={2.3} />
            Salvar alterações
          </button>
        </div>
      </footer>

      <button
        onClick={onVoltar}
        className="absolute left-1/2 top-[700px] -translate-y-1/2 rounded-lg px-2 py-1 text-[14px] text-apoio transition hover:bg-neutro"
      >
        [F3] ou [ESC] voltar ao menu
      </button>
    </div>
  );
}

const AJUDA_ABA: Record<AbaId, string> = {
  deteccao: "Como o aplicativo entende o olhar e confirma uma escolha.",
  distancia: "Aviso informativo quando o rosto fica longe ou perto da câmera.",
  piscada: "Confirmação alternativa para quem prefere não esperar o olhar fixo.",
  calibracao: "Tempo e qualidade mínima das calibrações.",
  prancha: "Sensibilidade da prancha de comunicação.",
  camera: "Origem e formato das imagens da webcam.",
  sistema: "Perfis, som, tema, janela e privacidade.",
};

function Campo({
  rotulo,
  ajuda,
  children,
}: {
  rotulo: string;
  ajuda: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-[14px] font-semibold leading-none text-texto">
        {rotulo}
      </span>
      <span className="mt-[5px] block text-[12px] leading-snug text-apoio">{ajuda}</span>
      <span className="mt-[7px] block">{children}</span>
    </label>
  );
}

function CampoNumero({
  rotulo,
  ajuda,
  valor,
  onChange,
  min,
  max,
  step,
  sufixo,
}: {
  rotulo: string;
  ajuda: string;
  valor: number;
  onChange: (valor: number) => void;
  min: number;
  max: number;
  step: number;
  sufixo?: string;
}) {
  return (
    <Campo rotulo={rotulo} ajuda={ajuda}>
      <span className="relative block">
        <input
          type="number"
          className={`${ENTRADA} ${sufixo ? "pr-16" : ""}`}
          value={valor}
          min={min}
          max={max}
          step={step}
          onChange={(e) => {
            const bruto = Number(e.target.value);
            if (!Number.isFinite(bruto)) return;
            onChange(Math.min(max, Math.max(min, bruto)));
          }}
        />
        {sufixo && (
          <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-apoio">
            {sufixo}
          </span>
        )}
      </span>
    </Campo>
  );
}

function CampoSelecao({
  rotulo,
  ajuda,
  valor,
  onChange,
  opcoes,
}: {
  rotulo: string;
  ajuda: string;
  valor: string;
  onChange: (valor: string) => void;
  opcoes: [string, string][];
}) {
  return (
    <Campo rotulo={rotulo} ajuda={ajuda}>
      <select
        className={ENTRADA}
        value={valor}
        onChange={(e) => onChange(e.target.value)}
      >
        {opcoes.map(([id, texto]) => (
          <option key={id} value={id}>
            {texto}
          </option>
        ))}
      </select>
    </Campo>
  );
}

function Alternador({
  rotulo,
  ajuda,
  valor,
  onChange,
}: {
  rotulo: string;
  ajuda: string;
  valor: boolean;
  onChange: (valor: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[12px] border border-borda bg-fundo px-[14px] py-[10px]">
      <div>
        <p className="text-[14px] font-semibold leading-none text-texto">{rotulo}</p>
        <p className="mt-[5px] text-[12px] leading-snug text-apoio">{ajuda}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={valor}
        aria-label={rotulo}
        onClick={() => onChange(!valor)}
        className={`relative h-[28px] w-[50px] shrink-0 rounded-full transition ${
          valor ? "bg-confirmado" : "bg-borda"
        }`}
      >
        <span
          className={`absolute top-[3px] size-[22px] rounded-full bg-superficie shadow transition-all ${
            valor ? "left-[25px]" : "left-[3px]"
          }`}
        />
      </button>
    </div>
  );
}
