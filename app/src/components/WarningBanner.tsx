import { AlertTriangle, EyeOff, ScanFace } from "lucide-react";

interface Props {
  texto: string;
  icone?: "alerta" | "rosto" | "cabeca";
  deslocado?: boolean;
}

/** Faixa de aviso sobre a tela, no mesmo estilo do renderer do _v2. */
export function WarningBanner({ texto, icone = "alerta", deslocado }: Props) {
  const Icone = icone === "rosto" ? ScanFace : icone === "cabeca" ? EyeOff : AlertTriangle;
  return (
    <div
      role="status"
      className={`absolute top-[88px] z-20 flex h-[42px] items-center gap-3 rounded-[12px] border-[1.5px] border-atencao bg-atencao-fundo px-[22px] text-atencao ${
        deslocado ? "left-[240px] right-[56px]" : "left-[56px] right-[56px]"
      }`}
    >
      <Icone size={22} strokeWidth={2.2} />
      <span className="text-[18px] font-semibold">{texto}</span>
    </div>
  );
}
