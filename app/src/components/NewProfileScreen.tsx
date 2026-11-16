import { useRef, useEffect } from "react";
import { ScreenHeader } from "./ScreenHeader";

interface Props {
  nome: string;
  onChange: (nome: string) => void;
  onConfirmar: () => void;
  onCancelar: () => void;
}

/** Criação de perfil: nome curto, seguro para virar arquivo em disco. */
export function NewProfileScreen({ nome, onChange, onConfirmar, onCancelar }: Props) {
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => {
    entrada.current?.focus();
  }, []);

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader titulo="Novo perfil" subtitulo="Modo cuidador" />

      <h1 className="absolute left-1/2 top-[170px] w-full -translate-x-1/2 -translate-y-1/2 text-center text-[34px] font-bold tracking-tight text-texto">
        Como devemos chamar este perfil?
      </h1>
      <p className="absolute left-1/2 top-[210px] w-full -translate-x-1/2 -translate-y-1/2 text-center text-[18px] text-apoio">
        Depois de criar, a calibração da prancha começa.
      </p>

      <div className="absolute left-1/2 top-[292px] grid size-[60px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-texto text-[26px] font-bold text-fundo">
        {nome.slice(0, 1).toUpperCase() || "?"}
      </div>

      <div className="absolute left-1/2 top-[350px] h-[72px] w-[500px] -translate-x-1/2 rounded-[16px] border-2 border-texto bg-superficie px-[18px]">
        <input
          ref={entrada}
          value={nome}
          onChange={(e) =>
            onChange(
              e.target.value
                .replace(/[^A-Za-z0-9_-]/g, "")
                .slice(0, 20),
            )
          }
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onConfirmar();
            } else if (e.key === "Escape") {
              e.preventDefault();
              onCancelar();
            }
          }}
          maxLength={20}
          spellCheck={false}
          autoComplete="off"
          aria-label="Nome do perfil"
          placeholder="nome"
          className="h-full w-full bg-transparent text-[30px] font-semibold text-texto outline-none placeholder:text-apoio/40"
        />
      </div>

      <p className="absolute left-1/2 top-[448px] w-[500px] -translate-x-1/2 text-[14px] text-apoio">
        Letras, números, &quot;_&quot; ou &quot;-&quot;. Máximo de 20 caracteres.
      </p>

      <p className="absolute left-1/2 top-[700px] -translate-x-1/2 -translate-y-1/2 text-[15px] text-apoio">
        [ENTER] Confirmar e calibrar · [ESC] Cancelar
      </p>
    </div>
  );
}
