import { Check } from "lucide-react";
import type { SnapshotApp } from "../types";

interface Props {
  snapshot: SnapshotApp;
  onVoltar: () => void;
}

/**
 * Modo SIM/NÃO (recurso legado): duas metades coloridas, com o lado do
 * olhar destacado, barra de dwell e confirmação. Mesmo layout de
 * `desenhar_painel_sim_nao` / `desenhar_progresso_sim_nao` do _v2.
 */
export function SimNaoScreen({ snapshot, onVoltar }: Props) {
  const { foco, progresso, confirmado } = snapshot;
  const metade = 640;

  return (
    <div className="anim-entrada absolute inset-0 overflow-hidden">
      <div className="absolute inset-y-0 left-0 w-[640px] bg-confirmado-fundo" />
      <div className="absolute inset-y-0 left-[640px] w-[640px] bg-atencao-fundo" />

      <span
        className="absolute top-[317px] -translate-y-1/2 text-[110px] font-bold leading-none tracking-tight transition-colors duration-200"
        style={{
          left: metade / 2,
          transform: "translate(-50%, -50%)",
          color: foco === "SIM"
            ? "var(--color-confirmado)"
            : confirmado === "SIM"
              ? "var(--color-confirmado)"
              : "color-mix(in srgb, var(--color-confirmado) 55%, var(--color-fundo))",
        }}
      >
        SIM
      </span>
      <span
        className="absolute top-[317px] text-[110px] font-bold leading-none tracking-tight transition-colors duration-200"
        style={{
          left: metade + metade / 2,
          transform: "translate(-50%, -50%)",
          color: foco === "NAO"
            ? "var(--color-atencao)"
            : confirmado === "NAO"
              ? "var(--color-atencao)"
              : "color-mix(in srgb, var(--color-atencao) 55%, var(--color-fundo))",
        }}
      >
        NÃO
      </span>

      {foco === "SIM" && !confirmado && (
        <span className="absolute left-[320px] top-[410px] -translate-x-1/2 text-[18px] text-apoio">
          olhe para este lado
        </span>
      )}
      {foco === "NAO" && !confirmado && (
        <span className="absolute left-[960px] top-[410px] -translate-x-1/2 text-[18px] text-apoio">
          olhe para este lado
        </span>
      )}

      <div className="absolute inset-y-0 left-[639px] w-[2px] bg-borda" />

      <button
        onClick={onVoltar}
        className="absolute left-[12px] top-[70px] h-[32px] rounded-[10px] border border-borda bg-superficie/90 px-[14px] text-[13px] leading-[30px] text-apoio transition hover:bg-superficie"
      >
        [M] Voltar ao menu
      </button>
      <span className="absolute left-[12px] top-[112px] text-[12px] text-apoio">
        Perfil: {snapshot.perfil || "padrão"} · SIM / NÃO
      </span>

      {confirmado && (
        <div className="absolute right-[56px] top-[34px] z-20 flex h-[42px] items-center gap-3 rounded-[12px] border-[1.5px] border-confirmado bg-confirmado-fundo px-[22px]">
          <span className="grid size-[22px] place-items-center rounded-full bg-confirmado text-fundo">
            <Check size={14} strokeWidth={3.2} />
          </span>
          <span className="text-[16px] font-semibold text-confirmado">
            Selecionado: {confirmado === "NAO" ? "NÃO" : confirmado}
          </span>
        </div>
      )}

      {foco && !confirmado && progresso > 0 && (
        <>
          <span
            className="absolute bottom-[12px] h-[12px] overflow-hidden rounded-full"
            style={{
              left: foco === "SIM" ? 56 : 1280 - 56 - 528,
              width: 528,
              backgroundColor:
                foco === "SIM"
                  ? "color-mix(in srgb, var(--color-confirmado) 22%, transparent)"
                  : "color-mix(in srgb, var(--color-atencao) 22%, transparent)",
            }}
          >
            <span
              className="block h-full rounded-full"
              style={{
                width: `${Math.min(100, Math.max(0, progresso * 100))}%`,
                backgroundColor:
                  foco === "SIM"
                    ? "var(--color-confirmado)"
                    : "var(--color-atencao)",
              }}
            />
          </span>
        </>
      )}

      <span className="absolute bottom-[26px] left-1/2 -translate-x-1/2 text-[13px] text-apoio">
        Olhe para o lado desejado e mantenha o olhar.
      </span>
    </div>
  );
}
