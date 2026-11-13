import type { ReactNode } from "react";
import { Marca } from "./Marca";

interface Props {
  titulo: string;
  subtitulo?: string | null;
  instrucao?: string | null;
  direita?: ReactNode;
}

/** Cabeçalho padrão de todas as telas (mesmas medidas do ui/design.py). */
export function ScreenHeader({ titulo, subtitulo, instrucao, direita }: Props) {
  return (
    <>
      <Marca x={56} y={28} />
      <h1 className="absolute left-[92px] top-[39px] -translate-y-1/2 text-[21px] font-semibold leading-none tracking-tight text-texto">
        {titulo}
      </h1>
      {subtitulo && (
        <p className="absolute left-[92px] top-[62px] -translate-y-1/2 text-[13px] text-apoio">
          {subtitulo}
        </p>
      )}
      {instrucao && (
        <p className="absolute left-[92px] top-[92px] -translate-y-1/2 text-[15px] text-apoio">
          {instrucao}
        </p>
      )}
      {direita && (
        <div className="absolute right-[56px] top-[24px] flex items-center gap-2">
          {direita}
        </div>
      )}
    </>
  );
}
