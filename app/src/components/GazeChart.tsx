import type { Historico } from "./tiposGrafico";

const LARGURA = 280;
const ALTURA = 150;
const MARGEM_X = 12;
const TOPO = 36;
const BASE = 128;

function limitar(valor: number): number {
  return Math.min(1, Math.max(0, valor));
}

function y(valor: number): number {
  return BASE - limitar(valor) * (BASE - TOPO);
}

function caminho(valores: number[]): string {
  if (valores.length < 2) return "";
  return valores
    .map((valor, indice) => {
      const x =
        MARGEM_X +
        (indice / Math.max(1, valores.length - 1)) * (LARGURA - MARGEM_X * 2);
      return `${indice === 0 ? "M" : "L"} ${x.toFixed(2)} ${y(valor).toFixed(2)}`;
    })
    .join(" ");
}

interface Props {
  historico: Historico;
  mediaEsq: number;
  mediaDir: number;
}

/** Sinal temporal da íris durante a calibração SIM/NÃO. */
export function GazeChart({ historico, mediaEsq, mediaDir }: Props) {
  const serieEsq = caminho(historico.esq.slice(-80));
  const serieDir = caminho(historico.dir.slice(-80));

  return (
    <div className="absolute right-[20px] top-[530px] h-[150px] w-[280px] rounded-[14px] border border-borda bg-superficie/95 p-3 shadow-[0_8px_24px_rgba(27,36,48,0.06)]">
      <p className="text-[12px] font-semibold text-texto">Sinal temporal (ratio_x)</p>
      <svg
        aria-hidden
        viewBox={`0 0 ${LARGURA} ${ALTURA}`}
        className="mt-1 h-[104px] w-full overflow-visible"
      >
        <line
          x1={MARGEM_X}
          x2={LARGURA - MARGEM_X}
          y1={y(mediaEsq)}
          y2={y(mediaEsq)}
          stroke="var(--color-confirmado)"
          strokeWidth={1}
        />
        <line
          x1={MARGEM_X}
          x2={LARGURA - MARGEM_X}
          y1={y(mediaDir)}
          y2={y(mediaDir)}
          stroke="var(--color-atencao)"
          strokeWidth={1}
        />
        {serieEsq && (
          <path d={serieEsq} fill="none" stroke="var(--color-texto)" strokeWidth={1.6} />
        )}
        {serieDir && (
          <path d={serieDir} fill="none" stroke="var(--cor-serie-dir)" strokeWidth={1.6} />
        )}
      </svg>
      <div className="flex gap-4 text-[10px] text-apoio">
        <span className="flex items-center gap-1">
          <span className="size-1.5 rounded-full bg-texto" /> olho esq.
        </span>
        <span className="flex items-center gap-1">
          <span
            className="size-1.5 rounded-full"
            style={{ backgroundColor: "var(--cor-serie-dir)" }}
          />{" "}
          olho dir.
        </span>
      </div>
    </div>
  );
}
