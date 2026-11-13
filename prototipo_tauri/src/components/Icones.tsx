interface Props {
  size?: number;
  strokeWidth?: number;
  className?: string;
}

/**
 * Ícone da prancha: quadrado dividido em quatro partes, como a grade 2x2
 * de cartões (OI, COMER, BEBER, BANHEIRO).
 */
export function IconePrancha({
  size = 22,
  strokeWidth = 2.1,
  className,
}: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={className}
      aria-hidden
    >
      <rect x="3" y="3" width="18" height="18" />
      <path d="M3 12h18" />
      <path d="M12 3v18" />
    </svg>
  );
}

/**
 * Ícone do SIM / NÃO: quadrado com uma linha vertical no centro,
 * separando os dois lados da resposta.
 */
export function IconeSimNao({
  size = 22,
  strokeWidth = 2.1,
  className,
}: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={className}
      aria-hidden
    >
      <rect x="3" y="3" width="18" height="18" />
      <path d="M12 3v18" />
    </svg>
  );
}
