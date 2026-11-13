interface Props {
  ativo: boolean;
  texto: string;
  tom?: "ok" | "alerta" | "neutro";
}

const CORES = {
  ok: "var(--color-confirmado)",
  alerta: "var(--color-atencao)",
  neutro: "var(--color-apoio)",
};

export function StatusPill({ ativo, texto, tom = "ok" }: Props) {
  const cor = ativo ? CORES[tom === "neutro" ? "neutro" : "ok"] : CORES.alerta;
  return (
    <span className="inline-flex h-[34px] items-center gap-2 rounded-full border border-borda bg-superficie px-[15px] text-[14px] text-apoio">
      <span
        className="size-[9px] rounded-full"
        style={{ backgroundColor: cor }}
      />
      {texto}
    </span>
  );
}
