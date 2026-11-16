import { ArrowLeft, ArrowLeftRight, ChevronLeft, Crosshair } from "lucide-react";
import type { ComponentType } from "react";
import type { SnapshotApp } from "../types";
import { ScreenHeader } from "./ScreenHeader";
import { StatusPill } from "./StatusPill";

interface Props {
  snapshot: SnapshotApp;
  onPrancha: () => void;
  onSimNao: () => void;
  onVoltar: () => void;
}

/** Escolha entre a calibração da prancha (4 cartões) e a de SIM/NÃO. */
export function CalibrationChoiceScreen({
  snapshot,
  onPrancha,
  onSimNao,
  onVoltar,
}: Props) {
  const prancha = snapshot.pranchaCalibrada
    ? { texto: "Calibrada", cor: "text-confirmado" }
    : snapshot.pranchaFraca
      ? { texto: "Calibração fraca", cor: "text-atencao" }
      : { texto: "Ainda não calibrada", cor: "text-atencao" };

  const simNao = snapshot.calibracaoSimNao
    ? { texto: "Calibrado", cor: "text-confirmado" }
    : snapshot.calibracaoFraca
      ? { texto: "Calibração fraca", cor: "text-atencao" }
      : { texto: "Ainda não calibrado", cor: "text-atencao" };

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader
        titulo="Calibração"
        subtitulo="Escolha qual calibração deseja fazer"
        direita={
          <StatusPill
            ativo={snapshot.cameraOk}
            texto={snapshot.cameraOk ? "Câmera pronta" : "Sem câmera"}
          />
        }
      />

      <button
        onClick={onVoltar}
        className="absolute left-[56px] top-[128px] inline-flex items-center gap-1 rounded-lg py-1 pr-2 text-[15px] text-apoio transition hover:bg-neutro"
      >
        <ChevronLeft size={19} strokeWidth={2.2} />
        Voltar ao menu
      </button>

      <h1 className="absolute left-[56px] top-[186px] -translate-y-1/2 text-[32px] font-bold tracking-tight text-texto">
        O que você quer calibrar?
      </h1>
      <p className="absolute left-[56px] top-[222px] -translate-y-1/2 text-[16px] text-apoio">
        Cada calibração é salva no perfil ativo: {snapshot.perfil || "padrão"}.
      </p>

      <div className="absolute left-[56px] top-[264px] flex gap-[20px]">
        <Cartao
          titulo="Prancha"
          descricao="Ensina o olhar para os 4 cartões: OI, COMER, BEBER e BANHEIRO."
          status={prancha}
          atalho="[1]"
          Icone={Crosshair}
          corIcone="bg-oi"
          onClick={onPrancha}
        />
        <Cartao
          titulo="SIM / NÃO"
          descricao="Ensina o olhar para os dois lados usados nas respostas de SIM e NÃO."
          status={simNao}
          atalho="[2]"
          Icone={ArrowLeftRight}
          corIcone="bg-beber"
          onClick={onSimNao}
        />
      </div>

      <button
        onClick={onVoltar}
        className="absolute left-1/2 top-[672px] inline-flex -translate-x-1/2 items-center gap-2 rounded-lg px-2 py-1 text-[15px] text-apoio transition hover:bg-neutro"
      >
        <ArrowLeft size={16} strokeWidth={2.2} />
        [ESC] voltar ao menu
      </button>
    </div>
  );
}

function Cartao({
  titulo,
  descricao,
  status,
  atalho,
  Icone,
  corIcone,
  onClick,
}: {
  titulo: string;
  descricao: string;
  status: { texto: string; cor: string };
  atalho: string;
  Icone: ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  corIcone: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group relative h-[342px] w-[574px] overflow-hidden rounded-[26px] border border-borda bg-superficie px-[32px] py-[30px] text-left transition duration-200 hover:-translate-y-[1px] hover:border-apoio/40 hover:shadow-[0_18px_44px_rgba(27,36,48,0.12)] active:translate-y-0"
    >
      <span
        className={`inline-flex size-[64px] items-center justify-center rounded-[18px] ${corIcone}`}
      >
        <Icone size={30} strokeWidth={2} className="text-texto" />
      </span>

      <span className="mt-[22px] block text-[30px] font-bold leading-none tracking-tight text-texto">
        {titulo}
      </span>
      <span className="mt-[12px] block max-w-[430px] text-[16px] leading-snug text-apoio">
        {descricao}
      </span>

      <span className="mt-[22px] flex items-center gap-2">
        <span className={`size-[9px] rounded-full bg-current ${status.cor}`} />
        <span className={`text-[14px] font-semibold ${status.cor}`}>
          {status.texto}
        </span>
      </span>

      <span className="absolute bottom-[26px] right-[28px] inline-flex h-[38px] items-center gap-2 rounded-full bg-neutro px-[18px] text-[14px] font-semibold text-texto transition group-hover:bg-texto group-hover:text-fundo">
        Calibrar
        <span className="text-[12px] opacity-70">{atalho}</span>
      </span>
    </button>
  );
}
