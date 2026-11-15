import { Activity, Check, Camera } from "lucide-react";
import {
  BLOCOS,
  rotulo,
  type BlocoId,
  type BlocoPrancha,
  type SnapshotApp,
} from "../types";
import { OlharCursor, type CentroCartao } from "./OlharCursor";
import { Pictograma } from "./Pictograma";
import { ScreenHeader } from "./ScreenHeader";
import { StatusPill } from "./StatusPill";

interface Props {
  snapshot: SnapshotApp;
  onVoltar: () => void;
  onPointer?: (id: BlocoId | null) => void;
}

const GRADE_ESQ = 56;
const GRADE_TOPO = 126;
const GRADE_LARGURA = 1168;
const GRADE_ALTURA = 550;
const VAO = 22;
const CELULA_L = (GRADE_LARGURA - VAO) / 2;
const CELULA_A = (GRADE_ALTURA - VAO) / 2;

function centroCartao(coluna: number, linha: number): CentroCartao {
  return {
    x: GRADE_ESQ + coluna * (CELULA_L + VAO) + CELULA_L / 2,
    y: GRADE_TOPO + linha * (CELULA_A + VAO) + CELULA_A / 2,
  };
}

/** Centros reais dos cartões no palco, usados pelo ponto do olhar. */
const CENTROS: Record<BlocoId, CentroCartao> = {
  oi: centroCartao(0, 0),
  comer: centroCartao(1, 0),
  beber: centroCartao(0, 1),
  banheiro: centroCartao(1, 1),
};

export function BoardScreen({ snapshot, onVoltar, onPointer }: Props) {
  const { confirmado, foco, progresso } = snapshot;  const instrucao = confirmado
    ? null
    : foco
      ? `Olhando para ${rotulo(foco)}.`
      : "Pronto. Olhe para um cartão.";

  const rodapeEsquerda = confirmado
    ? "A prancha volta ao normal em instantes."
    : foco
      ? `Mantenha o olhar em ${rotulo(foco)}.`
      : "Olhe para um cartão e mantenha o olhar.";

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader
        titulo="Prancha"
        subtitulo={`Perfil: ${snapshot.perfil || "padrão"}`}
        instrucao={instrucao}
        direita={
          <>
            <StatusPill
              ativo={snapshot.cameraOk}
              texto={snapshot.cameraOk ? "Câmera pronta" : "Sem câmera"}
            />
            <StatusPill
              ativo={snapshot.rostoOk && !snapshot.olhosFechados}
              texto={
                snapshot.olhosFechados
                  ? "Olhos fechados"
                  : snapshot.rostoOk
                    ? "Rosto detectado"
                    : "Sem rosto"
              }
            />
            <span className="inline-flex h-[34px] items-center gap-2 rounded-full border border-borda bg-neutro px-[15px] text-[13px] text-apoio">
              {snapshot.simulacao ? (
                <Activity size={15} strokeWidth={2.2} className="text-apoio" />
              ) : (
                <Camera size={15} strokeWidth={2.2} className="text-apoio" />
              )}
              {snapshot.simulacao ? "Simulação" : "Câmera real"}
            </span>
          </>
        }
      />

      {confirmado && (
        <div className="absolute left-[56px] top-[88px] z-20 flex h-[38px] w-[1168px] items-center gap-3 rounded-[12px] border-[1.5px] border-confirmado bg-confirmado-fundo px-[22px]">
          <span className="grid size-[22px] place-items-center rounded-full bg-confirmado text-fundo">
            <Check size={14} strokeWidth={3.2} />
          </span>
          <span className="text-[18px] font-semibold text-confirmado">
            Você escolheu: {rotulo(confirmado)}
          </span>
        </div>
      )}

      <div
        className="absolute left-[56px] top-[126px] grid grid-cols-2 grid-rows-2 gap-[22px]"
        style={{ width: 1168, height: 550 }}
        onMouseLeave={() => onPointer?.(null)}
      >
        {BLOCOS.map((b) => (
          <BoardCard
            key={b.id}
            bloco={b}
            foco={foco === b.id}
            confirmado={confirmado === b.id}
            progresso={foco === b.id ? progresso : 0}
            onHover={() => onPointer?.(b.id)}
            onSelect={() => onPointer?.(b.id)}
          />
        ))}
      </div>

      <p className="absolute left-[56px] top-[700px] -translate-y-1/2 text-[15px] text-apoio">
        {rodapeEsquerda}
      </p>
      <OlharCursor
        snapshot={snapshot}
        centros={CENTROS}
        progresso={foco ? progresso : 0}
      />
      <button
        onClick={onVoltar}
        className="absolute right-[56px] top-[700px] -translate-y-1/2 rounded-lg px-2 py-1 text-[15px] text-apoio transition hover:bg-neutro"
      >
        [M] Voltar ao menu
      </button>
      <span className="absolute bottom-[4px] left-1/2 -translate-x-1/2 text-[9px] font-semibold uppercase tracking-[0.14em] text-apoio/80">
        Comunicação pelo olhar · v{snapshot.versao}
      </span>
    </div>
  );
}

interface CardProps {
  bloco: BlocoPrancha;
  foco: boolean;
  confirmado: boolean;
  progresso: number;
  onHover: () => void;
  onSelect: () => void;
}

function BoardCard({
  bloco: b,
  foco,
  confirmado,
  progresso,
  onHover,
  onSelect,
}: CardProps) {
  const anel = confirmado
    ? "0 0 0 6px var(--color-confirmado), 0 0 0 13px var(--cor-anel-externo)"
    : foco
      ? "0 0 0 6px var(--color-texto), 0 0 0 13px var(--cor-anel-externo)"
      : undefined;

  return (
    <button
      onMouseEnter={onHover}
      onClick={onSelect}
      aria-label={`Selecionar ${b.rotulo}`}
      className={`relative overflow-hidden rounded-[28px] text-left transition-[transform,box-shadow] duration-150 hover:-translate-y-[2px] ${
        foco || confirmado ? "z-10" : ""
      }`}
      style={{
        backgroundColor: b.cor,
        border: `1px solid color-mix(in srgb, ${b.cor} 88%, #1B2430)`,
        boxShadow: anel,
      }}
    >
      <Pictograma
        id={b.id}
        tamanho={118}
        cor="#1B2430"
        className="absolute left-1/2 top-[40%] -translate-x-1/2 -translate-y-1/2"
      />
      <span className="absolute left-1/2 top-[80%] -translate-x-1/2 -translate-y-1/2 text-[46px] font-bold leading-none tracking-tight text-[#1B2430]">
        {b.rotulo}
      </span>

      {confirmado && (
        <>
          <span className="absolute right-[12px] top-[12px] grid size-[40px] place-items-center rounded-full bg-confirmado text-fundo">
            <Check size={22} strokeWidth={3.2} />
          </span>
          <span className="absolute bottom-[12px] left-1/2 h-[28px] -translate-x-1/2 rounded-full bg-confirmado px-[14px] text-[14px] font-semibold leading-[28px] text-fundo">
            Confirmado
          </span>
        </>
      )}

      {foco && !confirmado && progresso > 0 && (
        <span
          className="absolute bottom-[24px] left-[36px] h-[10px] w-[220px] overflow-hidden rounded-full"
          style={{
            backgroundColor: `color-mix(in srgb, ${b.cor} 82%, #1B2430)`,
          }}
        >
          <span
            className="block h-full rounded-full bg-[#1B2430] transition-[width] duration-75"
            style={{ width: `${Math.min(100, Math.max(0, progresso * 100))}%` }}
          />
        </span>
      )}
    </button>
  );
}
