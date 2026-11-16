import { useMemo, useRef } from "react";
import { type BlocoId, type SnapshotApp } from "../types";
import { criarProjecaoUnidade, referenciasCompletas } from "./mapaOlhar";

/**
 * Ponto do olhar desenhado sobre os cartões.
 *
 * Mostra onde a pessoa está olhando (bolinha) e um anel que se fecha no
 * tempo restante para a confirmação: no dwell da prancha o anel acompanha
 * o progresso da seleção; na calibração acompanha a coleta do cartão.
 *
 * A leitura bruta do motor (ratio da íris) passa pela projeção da
 * calibração e cai sobre o ponto do cartão correspondente, então o ponto
 * aparece no mesmo lugar em que a pessoa está olhando na tela. Os pontos
 * de referência são os mesmos alvos usados na calibração.
 */

export interface CentroCartao {
  x: number;
  y: number;
}

interface Props {
  snapshot: SnapshotApp;
  /**
   * Ponto de referência de cada cartão no palco de 1280x720 -- o mesmo
   * alvo usado na calibração (canto externo do cartão).
   */
  centros: Record<BlocoId, CentroCartao>;
  /**
   * Referências usadas na projeção. Por padrão, as da prancha atual;
   * na calibração convém passar as da calibração anterior.
   */
  referencias?: Record<string, [number, number]>;
  /** Progresso do dwell/coleta (0..1). */
  progresso?: number;
}

const RAIO_ANEL = 24;
const CIRCUNFERENCIA = 2 * Math.PI * RAIO_ANEL;
/** Tempo que o último ponto válido fica na tela após uma perda curta. */
const RETENCAO_MS = 500;
/** Opacidade do ponto retido, quando o motor não está lendo o olhar. */
const OPACIDADE_RETIDO = 0.4;

function limitar(valor: number): number {
  return Math.min(1, Math.max(0, valor));
}

function entre(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function OlharCursor({
  snapshot,
  centros,
  referencias,
  progresso = 0,
}: Props) {
  const refs = referencias ?? snapshot.pranchaCalib.referencias;
  const projecao = useMemo(() => criarProjecaoUnidade(refs), [refs]);
  // Último ponto desenhado. Evita o "teleporte" para o centro e mantém o
  // cursor parado quando o detector perde o rosto por um ou dois quadros.
  const ultimo = useRef<{ ponto: { x: number; y: number }; visto: number } | null>(
    null,
  );

  if (!referenciasCompletas(refs)) return null;

  let ponto: { x: number; y: number } | null = null;
  let retido = false;

  if (snapshot.gaze.valido) {
    const { x: u, y: v } = projecao.unidade(snapshot.gaze.x, snapshot.gaze.y);

    // Interpolação bilinear entre os quatro centros reais dos cartões.
    const topo = {
      x: entre(centros.oi.x, centros.comer.x, u),
      y: entre(centros.oi.y, centros.comer.y, u),
    };
    const base = {
      x: entre(centros.beber.x, centros.banheiro.x, u),
      y: entre(centros.beber.y, centros.banheiro.y, u),
    };
    ponto = { x: entre(topo.x, base.x, v), y: entre(topo.y, base.y, v) };
    ultimo.current = { ponto, visto: Date.now() };
  } else if (ultimo.current && Date.now() - ultimo.current.visto <= RETENCAO_MS) {
    ponto = ultimo.current.ponto;
    retido = true;
  }

  if (!ponto) return null;

  const fracao = limitar(progresso);
  const cor = fracao >= 0.999 ? "var(--color-confirmado)" : "var(--color-texto)";
  // Piscada ou olhos divergentes não são olhar válido: o ponto continua
  // no lugar para não "teleportar", mas fica esmaecido até o quadro voltar.
  const instavel =
    snapshot.olhosFechados || snapshot.gaze.divergenciaOk === false;
  const opacidade = instavel ? 0.22 : retido ? OPACIDADE_RETIDO : 1;
  const alvo = ponto;

  return (
    <svg
      className="pointer-events-none absolute inset-0 z-30"
      width={1280}
      height={720}
      viewBox="0 0 1280 720"
      aria-hidden="true"
    >
      <g
        style={{
          transform: `translate(${alvo.x.toFixed(1)}px, ${alvo.y.toFixed(1)}px)`,
          opacity: opacidade,
          filter: "drop-shadow(0 2px 6px rgba(0, 0, 0, 0.18))",
          transition: "transform 140ms linear, opacity 220ms linear",
        }}
      >
        {/* Disco de contraste: o indicador pode cair sobre o pictograma. */}
        <circle r={28} fill="var(--color-superficie)" fillOpacity={0.92} />

        {/* Trilho do anel: indica onde fica o ponto mesmo sem progresso. */}
        <circle
          r={RAIO_ANEL}
          fill="none"
          stroke="var(--color-texto)"
          strokeOpacity={0.18}
          strokeWidth={3}
        />

        {/* Anel de progresso: começa no topo e fecha no sentido horário. */}
        <circle
          r={RAIO_ANEL}
          fill="none"
          stroke={cor}
          strokeWidth={3.5}
          strokeLinecap="round"
          strokeDasharray={CIRCUNFERENCIA}
          strokeDashoffset={CIRCUNFERENCIA * (1 - fracao)}
          transform="rotate(-90)"
          style={{ transition: "stroke-dashoffset 120ms linear, stroke 160ms linear" }}
        />

        <circle
          r={6.5}
          fill={cor}
          stroke="var(--color-superficie)"
          strokeWidth={2}
        />
      </g>
    </svg>
  );
}
