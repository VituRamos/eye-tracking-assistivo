interface Props {
  onContinuar: () => void;
  onSair: () => void;
}

/**
 * Confirmação de saída do aplicativo.
 *
 * Só é aberta pelo teclado do cuidador (tecla Q) ou pelo botão "Sair".
 * Nenhum cartão de olhar fica ativo aqui, então o olhar nunca confirma
 * esta tela por acidente.
 */
export function ExitConfirmScreen({ onContinuar, onSair }: Props) {
  return (
    <div className="absolute inset-0 z-50 grid place-items-center bg-black/45 backdrop-blur-[2px]">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-sair"
        aria-describedby="texto-sair"
        className="w-[620px] rounded-[26px] border border-borda bg-superficie px-[48px] py-[38px] shadow-[0_30px_90px_rgba(0,0,0,0.35)]"
      >
        <h2
          id="titulo-sair"
          className="text-center text-[40px] font-bold leading-none tracking-tight text-texto"
        >
          Sair do app?
        </h2>
        <p
          id="texto-sair"
          className="mt-[14px] text-center text-[17px] leading-snug text-apoio"
        >
          O perfil e a calibração ficam salvos neste computador.
        </p>

        <div className="mt-[30px] flex justify-center gap-[14px]">
          <button
            autoFocus
            onClick={onContinuar}
            className="h-[56px] rounded-[12px] bg-texto px-[30px] text-[17px] font-semibold text-fundo transition hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-apoio"
          >
            Continuar usando
          </button>
          <button
            onClick={onSair}
            className="h-[56px] rounded-[12px] border border-borda px-[38px] text-[17px] font-semibold text-texto transition hover:bg-neutro focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-apoio"
          >
            Sair
          </button>
        </div>

        <p className="mt-[26px] text-center text-[13px] leading-snug text-apoio">
          Só abre pelo teclado do cuidador. O olhar nunca aciona esta tela.
        </p>
      </div>
    </div>
  );
}
