import { useEffect, useMemo, useState } from "react";
import { BLOCOS, type SnapshotApp } from "../types";

/**
 * Mapa do olhar do Modo Cuidador.
 *
 * Mostra, em espaço de ratio (0..1), os alvos calibrados da prancha, a
 * trilha recente do olhar e a posição atual. Também resume a divergência
 * entre os olhos -- quando ela passa do limite configurado, o quadro é
 * ignorado pelo motor e o painel avisa.
 */

const TAM = 200;
const MARGEM = 18;
const UTIL = TAM - MARGEM * 2;
const MAX_TRILHA = 48;

interface Ponto {
  x: number;
  y: number;
}

interface Alvo extends Ponto {
  id: string;
  rotulo: string;
  cor: string;
  calibrado: boolean;
  distancia: number;
}

function limitar(valor: number): number {
  return Math.min(1, Math.max(0, valor));
}

function px(valor: number): number {
  return MARGEM + limitar(valor) * UTIL;
}

function porcentagem(valor: number): string {
  return `${Math.round(limitar(valor) * 100)}%`;
}

export function GazeMap({ snapshot }: { snapshot: SnapshotApp }) {
  const gaze = snapshot.gaze;
  const limite = snapshot.config.deteccao.divergenciaMax;
  const raioMax = snapshot.config.prancha.raioMax;

  const divergencia = gaze.divergencia ?? Math.abs(gaze.esq - gaze.dir);
  const divergenciaOk = gaze.divergenciaOk ?? divergencia <= limite;

  const distanciaHabilitada = snapshot.config.deteccao.distanciaHabilitada;
  const distanciaAlerta =
    distanciaHabilitada &&
    snapshot.distanciaAviso &&
    (snapshot.distanciaEstado === "longe" ||
      snapshot.distanciaEstado === "perto");
  const distanciaIndefinida =
    !distanciaHabilitada || snapshot.distanciaEstado === "indefinida";
  const textoDistancia = !distanciaHabilitada
    ? "Desligada"
    : snapshot.distanciaEstado === "indefinida"
      ? "—"
      : `${snapshot.distanciaEstado === "boa" ? "Boa" : snapshot.distanciaEstado === "longe" ? "Longe" : "Perto"} · ${porcentagem(snapshot.distanciaRosto)}`;
  const corDistancia = distanciaAlerta
    ? "text-atencao"
    : distanciaIndefinida
      ? "text-apoio"
      : "text-texto";

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
    return BLOCOS.map((bloco) => {
      const referencia = referencias[bloco.id];
      const x = referencia ? referencia[0] : bloco.ratio.x;
      const y = referencia ? referencia[1] : bloco.ratio.y;
      return {
        id: bloco.id,
        rotulo: bloco.rotulo,
        cor: bloco.cor,
        x,
        y,
        calibrado: Boolean(referencia),
        distancia: Math.hypot(gaze.x - x, gaze.y - y),
      };
    });
  }, [snapshot.pranchaCalib.referencias, gaze.x, gaze.y]);

  const calibrados = alvos.filter((alvo) => alvo.calibrado);
  const maisProximo =
    calibrados.length > 0
      ? calibrados.reduce((melhor, alvo) =>
          alvo.distancia < melhor.distancia ? alvo : melhor,
        )
      : null;
  const foraDosCartoes =
    !maisProximo || maisProximo.distancia > raioMax || !gaze.valido;

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

  const nota = !snapshot.pranchaCalibrada
    ? "Prancha não calibrada — alvos na posição padrão."
    : !divergenciaOk && snapshot.rostoOk && snapshot.poseOk
      ? "Quadro ignorado: os olhos divergem além do limite."
      : distanciaAlerta && snapshot.distanciaEstado === "longe"
        ? "Rosto um pouco longe: aproxime-se da câmera."
        : distanciaAlerta && snapshot.distanciaEstado === "perto"
          ? "Rosto muito perto: afaste-se um pouco da câmera."
          : "O ponto mostra para onde o usuário está olhando.";

  const corPonto =
    divergenciaOk && snapshot.poseOk
      ? "var(--color-confirmado)"
      : "var(--color-atencao)";

  return (
    <section className="absolute left-[652px] top-[386px] h-[252px] w-[572px] rounded-[20px] border border-borda bg-superficie px-[24px] py-[18px]">
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

      <div className="mt-[8px] flex items-start gap-[18px]">
        <svg
          viewBox={`0 0 ${TAM} ${TAM}`}
          className="h-[160px] w-[160px] shrink-0"
          role="img"
          aria-label="Mapa do olhar sobre os cartões da prancha"
        >
          <rect
            x="1"
            y="1"
            width={TAM - 2}
            height={TAM - 2}
            rx="14"
            fill="var(--color-fundo)"
            stroke="var(--color-borda)"
          />
          <line
            x1={MARGEM}
            x2={TAM - MARGEM}
            y1={TAM / 2}
            y2={TAM / 2}
            stroke="var(--color-borda)"
            strokeDasharray="3 5"
          />
          <line
            x1={TAM / 2}
            x2={TAM / 2}
            y1={MARGEM}
            y2={TAM - MARGEM}
            stroke="var(--color-borda)"
            strokeDasharray="3 5"
          />

          {alvos.map((alvo) => (
            <circle
              key={alvo.id}
              cx={px(alvo.x)}
              cy={px(alvo.y)}
              r={alvo.id === maisProximo?.id ? 16 : 13}
              fill={alvo.cor}
              fillOpacity={alvo.calibrado ? 0.9 : 0.35}
              stroke={
                alvo.id === maisProximo?.id
                  ? "var(--color-texto)"
                  : "var(--color-borda)"
              }
              strokeWidth={alvo.id === maisProximo?.id ? 2.5 : 1}
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
                .map((ponto) => `${px(ponto.x).toFixed(1)},${px(ponto.y).toFixed(1)}`)
                .join(" ")}
            />
          )}

          {gaze.valido && (
            <>
              <circle
                cx={px(gaze.x)}
                cy={px(gaze.y)}
                r={10}
                fill={corPonto}
                fillOpacity={0.2}
              />
              <circle
                cx={px(gaze.x)}
                cy={px(gaze.y)}
                r={4.5}
                fill={corPonto}
                stroke="var(--color-superficie)"
                strokeWidth={1.5}
              />
            </>
          )}
        </svg>

        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-apoio">
            Cartão mais próximo
          </p>
          <div className="mt-[3px] flex items-center gap-2">
            {maisProximo && gaze.valido && (
              <span
                className="size-[10px] shrink-0 rounded-full"
                style={{ backgroundColor: maisProximo.cor }}
              />
            )}
            <p className="truncate text-[19px] font-semibold leading-tight text-texto">
              {!gaze.valido
                ? "Sem leitura"
                : !maisProximo
                  ? "Não calibrada"
                  : foraDosCartoes
                    ? "Fora dos cartões"
                    : maisProximo.rotulo}
            </p>
          </div>
          <p className="mt-[2px] text-[12px] text-apoio">
            {!gaze.valido
              ? "Aguardando um quadro válido do rosto"
              : maisProximo
                ? `Distância ${maisProximo.distancia.toFixed(2)} · limite ${raioMax.toFixed(2)}`
                : `Sem referências calibradas · limite ${raioMax.toFixed(2)}`}
          </p>

          <div className="mt-[10px] grid grid-cols-3 gap-x-[12px] border-t border-borda pt-[8px]">
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-apoio">
                Divergência
              </p>
              <p
                className={`mt-[1px] text-[15px] font-semibold ${
                  divergenciaOk ? "text-texto" : "text-atencao"
                }`}
              >
                {porcentagem(divergencia)}{" "}
                <span className="text-[11px] font-normal text-apoio">
                  / {porcentagem(limite)}
                </span>
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-apoio">
                Olhos E / D
              </p>
              <p className="mt-[1px] text-[15px] font-semibold text-texto">
                {porcentagem(gaze.esq)} / {porcentagem(gaze.dir)}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-apoio">
                Distância
              </p>
              <p
                className={`mt-[1px] text-[15px] font-semibold ${corDistancia}`}
              >
                {textoDistancia}
              </p>
            </div>
          </div>

          <p className="mt-[8px] text-[11px] leading-snug text-apoio">{nota}</p>
        </div>
      </div>
    </section>
  );
}
