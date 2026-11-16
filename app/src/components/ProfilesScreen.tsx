import { Plus } from "lucide-react";
import type { SnapshotApp } from "../types";
import { ScreenHeader } from "./ScreenHeader";

interface Props {
  snapshot: SnapshotApp;
  onSelecionar: (nome: string) => void;
  onNovo: () => void;
  onVoltar: () => void;
}

/** Escolha de perfil: lista numerada, atalhos [1]–[9] e [N] novo. */
export function ProfilesScreen({ snapshot, onSelecionar, onNovo, onVoltar }: Props) {
  const perfis = snapshot.perfis.slice(0, 9);

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader
        titulo="Perfis"
        subtitulo="Escolha quem vai usar a prancha"
        direita={
          <button
            onClick={onNovo}
            className="inline-flex h-[38px] items-center gap-2 rounded-full bg-texto px-[18px] text-[14px] font-semibold text-fundo transition hover:opacity-90"
          >
            <Plus size={18} strokeWidth={2.4} />
            [N] Novo perfil
          </button>
        }
      />

      {perfis.length === 0 ? (
        <div className="absolute left-[56px] right-[56px] top-[150px] h-[150px] rounded-[20px] border border-borda bg-superficie">
          <p className="mt-[42px] text-center text-[24px] font-semibold text-texto">
            Nenhum perfil salvo ainda.
          </p>
          <p className="mt-2 text-center text-[16px] text-apoio">
            Pressione [N] para criar o primeiro perfil.
          </p>
        </div>
      ) : (
        <div className="absolute left-[56px] right-[56px] top-[150px] space-y-[12px]">
          {perfis.map((nome, indice) => {
            const ativo = nome === snapshot.perfilAtivo;
            return (
              <button
                key={nome}
                onClick={() => onSelecionar(nome)}
                className={`flex h-[64px] w-full items-center rounded-[16px] border-2 bg-superficie px-0 text-left transition hover:-translate-y-[1px] hover:shadow-[0_10px_26px_rgba(27,36,48,0.08)] ${
                  ativo ? "border-texto" : "border-borda"
                }`}
              >
                <span
                  className={`ml-[20px] grid size-[40px] place-items-center rounded-full text-[18px] font-bold ${
                    ativo ? "bg-texto text-fundo" : "bg-neutro text-texto"
                  }`}
                >
                  {nome.slice(0, 1).toUpperCase()}
                </span>
                <span className="ml-[16px] text-[20px] font-semibold text-texto">
                  {nome}
                </span>
                {ativo && (
                  <span className="ml-4 rounded-full bg-confirmado-fundo px-[10px] py-[3px] text-[12px] font-semibold text-confirmado">
                    Ativo
                  </span>
                )}
                <span className="ml-auto mr-[20px] text-[14px] text-apoio">
                  [{indice + 1}]
                </span>
              </button>
            );
          })}
          {snapshot.perfis.length > 9 && (
            <p className="pl-1 text-[14px] text-apoio">
              (mostrando 9 de {snapshot.perfis.length} perfis)
            </p>
          )}
        </div>
      )}

      <button
        onClick={onVoltar}
        className="absolute left-[56px] top-[700px] -translate-y-1/2 rounded-lg px-2 py-1 text-[15px] text-apoio transition hover:bg-neutro"
      >
        [M] Voltar ao menu · [N] Novo perfil
      </button>
      <p className="absolute right-[56px] top-[700px] -translate-y-1/2 text-[15px] text-apoio">
        [1]–[{Math.min(9, Math.max(1, perfis.length))}] escolher perfil
      </p>
    </div>
  );
}
