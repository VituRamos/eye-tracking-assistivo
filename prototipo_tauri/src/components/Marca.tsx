/** Marca da prancha: quatro quadrantes nas cores dos cartões. */
export function Marca({ x, y }: { x: number; y: number }) {
  const lado = 11;
  const gap = 3;
  return (
    <div
      aria-hidden
      className="absolute"
      style={{ left: x, top: y, width: lado * 2 + gap, height: lado * 2 + gap }}
    >
      <span
        className="absolute rounded-[3px] bg-texto"
        style={{ left: 0, top: 0, width: lado, height: lado }}
      />
      <span
        className="absolute rounded-[3px] bg-oi"
        style={{ left: lado + gap, top: 0, width: lado, height: lado }}
      />
      <span
        className="absolute rounded-[3px] bg-beber"
        style={{ left: 0, top: lado + gap, width: lado, height: lado }}
      />
      <span
        className="absolute rounded-[3px] bg-comer"
        style={{ left: lado + gap, top: lado + gap, width: lado, height: lado }}
      />
    </div>
  );
}
