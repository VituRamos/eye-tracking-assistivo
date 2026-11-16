import { useEffect, useMemo, useState } from "react";
import { BLOCOS, type SnapshotApp } from "../types";
import { criarProjecaoMapa } from "./mapaOlhar";

/**
 * Mapa do olhar do Modo Cuidador.
 *
 * Mostra os alvos calibrados nos quadrantes reais da prancha, a trilha
 * recente do olhar e a posição atual. Como a calibração guarda o olhar em
 * coordenadas de ratio da íris (comprimidas em torno do centro), o ponto
 * do olhar passa pela projeção de `mapaOlhar` antes de ser desenhado --
 * caso contrário os quatro cartões ficam empilhados no meio.
 *
 * Também resume a divergência entre os olhos -- quando ela passa do
 * limite configurado, o quadro é ignorado pelo motor e o painel avisa.
 */

const LARGURA = 330;
const ALTURA = 190;
const MARGEM = 14;
const UTIL_X = LARGURA - MARGEM * 2;
const UTIL_Y = ALTURA - MARGEM * 2;
const MAX_TRILHA = 48;

interface Ponto {
  x: number;
  y: number;
}

interface Alvo {
  id: string;
  rotulo: string;
  cor: string;
  calibrado: boolean;
  /** Centro do cartão no layout da prancha (sempre nos quadrantes). */
  cartao: Ponto;
}

function limitar(valor: number): number {
  return Math.min(1, Math.max(0, valor));
}

export function GazeMap({ snapshot }: { snapshot: SnapshotApp }) {
  const gaze = snapshot.gaze;
  const limite = snapshot.config.deteccao.divergenciaMax;

  const divergencia = gaze.divergencia ?? Math.abs(gaze.esq - gaze.dir);
  const divergenciaOk = gaze.divergenciaOk ?? divergencia <= limite;

  const distanciaHabilitada = snapshot.config.deteccao.distanciaHabilitada;
  const distanciaAlerta =
    distanciaHabilitada &&
    snapshot.distanciaAviso &&
    (snapshot.distanciaEstado === "longe" ||
      snapshot.distanciaEstado === "perto");

  // Trilha local: o motor só envia o histórico horizontal (esq/dir),
  // então as posições 2D recentes são acumuladas aqui mesmo.
  const [trilha, setTrilha] = useState<Ponto[]>([]);
  useEffect(() => {
    if (!gaze.valido) return;
    setTrilha((anterior) =>
      [...anterior, { x: gaze.x, y: gaze.y }].slice(-MAX_TRILHA),
    );
  }, [gaze.valido, gaze.x, gaze.y]);

  const alvos = useMemo<Alvo[]>(() => {
    const referencias = snapshot.pranchaCalib.referencias;
    return BLOCOS.map((bloco) => ({
      id: bloco.id,
      rotulo: bloco.rotulo,
      cor: bloco.cor,
      cartao: bloco.ratio,
      calibrado: Boolean(referencias[bloco.id]),
    }));
  }, [snapshot.pranchaCalib.referencias]);

  const temReferencias = alvos.every((alvo) => alvo.calibrado);
  // O cartão atual vem do motor (quadrante + histerese); o mapa só desenha.
  const alvoAtual =
    gaze.valido && gaze.bloco
      ? (alvos.find((alvo) => alvo.id === gaze.bloco) ?? null)
      : null;
  const foraDosCartoes = Boolean(gaze.valido && temReferencias && !alvoAtual);

  const estado = !snapshot.cameraOk
    ? { texto: "Sem sinal", cor: "text-atencao", ponto: "var(--color-atencao)" }
    : !snapshot.rostoOk
      ? { texto: "Sem rosto", cor: "text-atencao", ponto: "var(--color-atencao)" }
      : !snapshot.poseOk
        ? {
            texto: "Cabeça virada",
            cor: "text-atencao",
            ponto: "var(--color-atencao)",
          }
        : !divergenciaOk
          ? {
              texto: "Olhos divergentes",
              cor: "text-atencao",
              ponto: "var(--color-atencao)",
            }
          : distanciaAlerta && snapshot.distanciaEstado === "longe"
            ? {
                texto: "Rosto longe",
                cor: "text-atencao",
                ponto: "var(--color-atencao)",
              }
            : distanciaAlerta && snapshot.distanciaEstado === "perto"
              ? {
                  texto: "Rosto perto",
                  cor: "text-atencao",
                  ponto: "var(--color-atencao)",
                }
              : {
                  texto: "Ao vivo",
                  cor: "text-confirmado",
                  ponto: "var(--color-confirmado)",
                };

  const dica = !snapshot.cameraOk
    ? "Verifique a câmera e reabra o aplicativo."
    : !snapshot.rostoOk
      ? "Posicione o rosto em frente à câmera."
      : !snapshot.poseOk
        ? "Peça para olhar de frente para a tela."
        : !divergenciaOk
          ? "Peça para piscar e olhar novamente."
          : distanciaAlerta && snapshot.distanciaEstado === "longe"
            ? "Aproxime um pouco o rosto da câmera."
            : distanciaAlerta && snapshot.distanciaEstado === "perto"
              ? "Afaste um pouco o rosto da câmera."
              : "Mantenha o olhar no cartão para escolher.";

  const corPonto =
    divergenciaOk && snapshot.poseOk
      ? "var(--color-confirmado)"
      : "var(--color-atencao)";

  // Cartões sempre nos quadrantes da prancha; o olhar é projetado pela
  // calibração do usuário para cair no quadrante correspondente.
  const projecao = useMemo(
    () => criarProjecaoMapa(snapshot.pranchaCalib.referencias),
    [snapshot.pranchaCalib.referencias],
  );
  const paraPixelX = (valor: number) => MARGEM + limitar(valor) * UTIL_X;
  const paraPixelY = (valor: number) => MARGEM + limitar(valor) * UTIL_Y;
  const pixelOlhar = (rawX: number, rawY: number) => {
    const ponto = projecao.projetar(rawX, rawY);
    return { x: paraPixelX(ponto.x), y: paraPixelY(ponto.y) };
  };
  const olharPixel = gaze.valido ? pixelOlhar(gaze.x, gaze.y) : null;

  return (
    <section className="absolute left-[652px] top-[386px] h-[252px] w-[572px] rounded-[20px] border border-borda bg-superficie px-[18px] py-[14px]">
      <div className="flex items-center justify-between">
        <h2 className="text-[20px] font-semibold text-texto">Mapa do olhar</h2>
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <span
            className="size-[8px] rounded-full"
            style={{ backgroundColor: estado.ponto }}
          />
          <span className={estado.cor}>{estado.texto}</span>
        </span>
      </div>

      <div className="mt-[6px] flex items-start gap-[16px]">
        <svg
          viewBox={`0 0 ${LARGURA} ${ALTURA}`}
          className="h-[190px] w-[330px] shrink-0"
          role="img"
          aria-label="Mapa do olhar sobre os cartões da prancha"
        >
          <rect
            x="1"
            y="1"
            width={LARGURA - 2}
            height={ALTURA - 2}
            rx="14"
            fill="var(--color-fundo)"
            stroke="var(--color-borda)"
          />
          <line
            x1={MARGEM}
            x2={LARGURA - MARGEM}
            y1={ALTURA / 2}
            y2={ALTURA / 2}
            stroke="var(--color-borda)"
            strokeDasharray="3 5"
          />
          <line
            x1={LARGURA / 2}
            x2={LARGURA / 2}
            y1={MARGEM}
            y2={ALTURA - MARGEM}
            stroke="var(--color-borda)"
            strokeDasharray="3 5"
          />

          {alvos.map((alvo) => (
            <circle
              key={alvo.id}
              cx={paraPixelX(alvo.cartao.x)}
              cy={paraPixelY(alvo.cartao.y)}
              r={alvo.id === alvoAtual?.id ? 20 : 17}
              fill={alvo.cor}
              fillOpacity={alvo.calibrado ? 0.9 : 0.35}
              stroke={
                alvo.id === alvoAtual?.id
                  ? "var(--color-texto)"
                  : "var(--color-borda)"
              }
              strokeWidth={alvo.id === alvoAtual?.id ? 2.5 : 1}
              strokeDasharray={alvo.calibrado ? undefined : "3 3"}
            >
              <title>{alvo.rotulo}</title>
            </circle>
          ))}

          {trilha.length > 1 && (
            <polyline
              fill="none"
              stroke="var(--color-texto)"
              strokeOpacity={0.3}
              strokeWidth={1.6}
              strokeLinejoin="round"
              strokeLinecap="round"
              points={trilha
                .map((ponto) => {
                  const q = pixelOlhar(ponto.x, ponto.y);
                  return `${q.x.toFixed(1)},${q.y.toFixed(1)}`;
                })
                .join(" ")}
            />
          )}

          {gaze.valido && olharPixel && (
            <>
              <circle
                cx={olharPixel.x}
                cy={olharPixel.y}
                r={12}
                fill={corPonto}
                fillOpacity={0.2}
              />
              <circle
                cx={olharPixel.x}
                cy={olharPixel.y}
                r={5.5}
                fill={corPonto}
                stroke="var(--color-superficie)"
                strokeWidth={1.5}
              />
            </>
          )}
        </svg>

        <div className="min-w-0 flex-1 pt-[2px]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-apoio">
            Cartão em foco
          </p>
          <div className="mt-[4px] flex items-center gap-2">
            {alvoAtual && gaze.valido && (
              <span
                className="size-[10px] shrink-0 rounded-full"
                style={{ backgroundColor: alvoAtual.cor }}
              />
            )}
            <p className="truncate text-[21px] font-semibold leading-tight text-texto">
              {!gaze.valido
                ? "Sem leitura"
                : !temReferencias
                  ? "Não calibrada"
                  : foraDosCartoes
                    ? "Fora dos cartões"
                    : (alvoAtual?.rotulo ?? "Zona neutra")}
            </p>
          </div>
          <p className="mt-[4px] text-[12px] leading-snug text-apoio">
            {!gaze.valido
              ? "Aguardando o rosto aparecer"
              : !temReferencias
                ? "Calibre a prancha para começar"
                : alvoAtual
                  ? "Dentro do cartão calibrado"
                  : "Zona neutra entre os cartões"}
          </p>

          <div className="my-[9px] h-px bg-borda" />

          <p className="text-[12px] leading-snug text-texto">{dica}</p>
          {!snapshot.pranchaCalibrada && (
            <p className="mt-[6px] text-[11.5px] font-semibold leading-snug text-atencao">
              Prancha não calibrada: pressione [C].
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
