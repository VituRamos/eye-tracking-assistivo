import { useEffect, useState, type ReactNode } from "react";

/**
 * Palco fixo de 1280x720 escalado para caber na janela.
 *
 * A UI do _v2 é desenhada em 1280x720 e ampliada para 1920x1080. No
 * protótipo usamos o mesmo espaço de coordenadas para manter fidelidade
 * de proporções, tipografia e posições.
 */
export function Stage({ children }: { children: ReactNode }) {
  const [escala, setEscala] = useState(1);

  useEffect(() => {
    const atualizar = () => {
      const nova = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
      setEscala(Math.max(0.2, nova));
    };
    atualizar();
    window.addEventListener("resize", atualizar);
    return () => window.removeEventListener("resize", atualizar);
  }, []);

  return (
    <div className="fixed inset-0 flex items-center overflow-hidden bg-fundo">
      <div
        className="relative shrink-0 origin-left overflow-hidden bg-fundo"
        style={{
          width: 1280,
          height: 720,
          transform: `scale(${escala})`,
        }}
      >
        {children}
      </div>
    </div>
  );
}
