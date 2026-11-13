import type { SnapshotApp } from "../types";
import { ScreenHeader } from "./ScreenHeader";
import { WarningBanner } from "./WarningBanner";

interface Props {
  snapshot: SnapshotApp;
  onVoltar: () => void;
}

/** Aviso de câmera indisponível, sobreposto a qualquer tela. */
export function NoSignalScreen({ snapshot, onVoltar }: Props) {
  const segundos = snapshot.segundosSemFrame;
  const detalhe =
    segundos === null
      ? "A câmera não entregou nenhuma imagem desde a abertura."
      : segundos < 1
        ? "Última imagem recebida há menos de 1 segundo."
        : `Última imagem recebida há ${Math.round(segundos)} segundos.`;

  const passos = [
    "Confira se o cabo da câmera está encaixado.",
    "Feche outros programas que usam a câmera.",
    "Aguarde alguns segundos. O app tenta de novo sozinho.",
    "Se continuar, reinicie o computador.",
  ];

  return (
    <div className="anim-entrada absolute inset-0 z-30 bg-fundo">
      <ScreenHeader titulo="Câmera" subtitulo="Comunicação pelo olhar" />
      <WarningBanner texto="A câmera não está disponível. Peça ajuda ao cuidador." />

      <section className="absolute left-[56px] right-[56px] top-[158px] h-[442px] rounded-[24px] border border-borda bg-superficie">
        <h2 className="absolute left-[44px] top-[50px] -translate-y-1/2 text-[28px] font-semibold text-texto">
          Para o cuidador
        </h2>
        <p className="absolute left-[44px] top-[88px] -translate-y-1/2 text-[16px] text-apoio">
          {detalhe}
        </p>

        {passos.map((passo, indice) => (
          <div
            key={passo}
            className="absolute left-[44px] flex items-center gap-4"
            style={{ top: 130 + indice * 50 }}
          >
            <span className="grid size-[26px] place-items-center rounded-full bg-neutro text-[13px] font-semibold text-texto">
              {indice + 1}
            </span>
            <span className="text-[18px] text-apoio">{passo}</span>
          </div>
        ))}

        <p className="absolute bottom-[36px] left-[44px] text-[15px] text-apoio">
          A prancha volta sozinha quando a câmera responder.
        </p>
        {snapshot.backend && snapshot.backend !== "nenhum" && (
          <span className="absolute bottom-[30px] right-[24px] inline-flex h-[30px] items-center rounded-full border border-borda px-[12px] text-[13px] text-apoio">
            Backend: {snapshot.backend}
          </span>
        )}
      </section>

      <button
        onClick={onVoltar}
        className="absolute left-1/2 top-[648px] -translate-x-1/2 rounded-lg px-3 py-1 text-[15px] text-apoio transition hover:bg-neutro"
      >
        [M] Voltar ao menu
      </button>
    </div>
  );
}
