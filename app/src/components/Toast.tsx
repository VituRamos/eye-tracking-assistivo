export function Toast({ texto }: { texto: string }) {
  return (
    <div
      role="status"
      className="toast-in fixed bottom-7 left-1/2 z-50 rounded-full bg-texto px-5 py-2.5 text-[14px] font-medium text-fundo shadow-[0_16px_40px_rgba(16,20,26,0.35)]"
    >
      {texto}
    </div>
  );
}
