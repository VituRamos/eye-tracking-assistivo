import { AlertTriangle } from "lucide-react";

/** Marca grande da tela de abertura. */
function MarcaGrande() {
  const lado = 22;
  const gap = 6;
  return (
    <div
      aria-hidden
      className="relative"
      style={{ width: lado * 2 + gap, height: lado * 2 + gap }}
    >
      <span
        className="absolute rounded-[6px] bg-texto"
        style={{ left: 0, top: 0, width: lado, height: lado }}
      />
      <span
        className="absolute rounded-[6px] bg-oi"
        style={{ left: lado + gap, top: 0, width: lado, height: lado }}
      />
      <span
        className="absolute rounded-[6px] bg-beber"
        style={{ left: 0, top: lado + gap, width: lado, height: lado }}
      />
      <span
        className="absolute rounded-[6px] bg-comer"
        style={{ left: lado + gap, top: lado + gap, width: lado, height: lado }}
      />
    </div>
  );
}

export function BootScreen({ texto }: { texto: string }) {
  return (
    <div className="absolute inset-0 z-40 grid place-items-center bg-fundo">
      <div className="flex flex-col items-center">
        <MarcaGrande />
        <h1 className="mt-8 text-[30px] font-bold tracking-tight text-texto">Prancha</h1>
        <p className="mt-1 text-[14px] text-apoio">Comunicação pelo olhar</p>

        <div className="mt-10 flex items-center gap-3 rounded-full border border-borda bg-superficie px-5 py-3">
          <span className="pulso size-[10px] rounded-full bg-texto" />
          <span className="text-[15px] text-apoio">{texto}</span>
        </div>

        <p className="mt-6 text-[12px] text-apoio/80">
          Tudo acontece neste computador. Nenhum dado é enviado pela internet.
        </p>
      </div>
    </div>
  );
}

interface ErroProps {
  texto: string;
  onFechar: () => void;
}

export function ErrorScreen({ texto, onFechar }: ErroProps) {
  return (
    <div className="absolute inset-0 z-40 grid place-items-center bg-fundo px-[120px]">
      <div className="w-full max-w-[860px] rounded-[24px] border border-borda bg-superficie p-10 shadow-[0_30px_90px_rgba(16,20,26,0.18)]">
        <div className="flex items-start gap-4">
          <span className="grid size-[52px] shrink-0 place-items-center rounded-full bg-atencao-fundo text-atencao">
            <AlertTriangle size={28} strokeWidth={2.2} />
          </span>
          <div>
            <h1 className="text-[28px] font-bold tracking-tight text-texto">
              Não foi possível iniciar o motor
            </h1>
            <p className="mt-1 text-[15px] text-apoio">
              O aplicativo precisa do motor local de rastreamento para funcionar.
            </p>
          </div>
        </div>

        <pre className="mt-6 max-h-[240px] overflow-auto whitespace-pre-wrap rounded-[14px] bg-neutro p-4 text-[13px] leading-relaxed text-texto">
          {texto}
        </pre>

        <div className="mt-6 flex items-center gap-3">
          <button
            onClick={onFechar}
            className="rounded-full bg-texto px-6 py-2.5 text-[15px] font-semibold text-fundo transition hover:opacity-90"
          >
            Fechar aplicativo
          </button>
          <button
            onClick={() => void navigator.clipboard?.writeText(texto)}
            className="rounded-full border border-borda px-5 py-2.5 text-[15px] text-apoio transition hover:bg-neutro"
          >
            Copiar detalhes
          </button>
          <span className="ml-auto text-[12px] text-apoio">
            Os detalhes também estão em logs/ na pasta de dados.
          </span>
        </div>
      </div>
    </div>
  );
}
