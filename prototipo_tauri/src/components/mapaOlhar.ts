/**
 * Projeção do olhar para o mapa do Modo Cuidador.
 *
 * A calibração guarda o olhar em coordenadas de ratio da íris, que variam
 * pouco entre os cartões (tipicamente 0.34..0.51). Desenhar esses valores
 * direto no quadro 0..1 empilha os quatro cartões no centro.
 *
 * Aqui o olhar bruto é convertido no layout real da prancha -- os quatro
 * cartões nos quadrantes. As quatro referências calibradas formam um
 * quadrilátero; a conversão é a inversa da interpolação bilinear desse
 * quadrilátero:
 *
 * - cada referência cai exatamente no centro do seu cartão;
 * - entre cartões o movimento é linear, então os desvios pequenos do
 *   olhar continuam visíveis (não "grudam" no centro);
 * - o eixo vertical pode estar invertido, sem tratamento especial;
 * - leituras fora da área calibrada param na borda do quadrilátero.
 *
 * A distância numérica usada pelo motor continua em ratio bruto; esta
 * projeção é só para o desenho.
 */

export interface PontoMapa {
  x: number;
  y: number;
}

export interface ProjecaoMapa {
  /** Converte uma leitura bruta do olhar em posição no layout (0..1). */
  projetar: (rawX: number, rawY: number) => PontoMapa;
}

/**
 * Projeção em coordenadas unitárias da grade: ``x = 0`` é a coluna da
 * esquerda, ``x = 1`` a da direita, ``y = 0`` a linha de cima e ``y = 1``
 * a de baixo. Serve para posicionar o olhar sobre cartões desenhados em
 * qualquer tamanho (prancha, calibração), sem depender do esquema 0.3/0.7.
 */
export interface ProjecaoUnidade {
  unidade: (rawX: number, rawY: number) => PontoMapa;
}

/** Centro de cada cartão no layout da prancha, em unidades de (u, v). */
const LAYOUT_ESQ = 0.3;
const LAYOUT_DIR = 0.7;
const LAYOUT_TOPO = 0.3;
const LAYOUT_BASE = 0.7;

const IDS = ["oi", "comer", "beber", "banheiro"] as const;

/** Iterações do ponto fixo. Três já bastam para os perfis reais. */
const ITERACOES = 4;

function limitar(valor: number): number {
  return Math.min(1, Math.max(0, valor));
}

function identidade(rawX: number, rawY: number): PontoMapa {
  return { x: limitar(rawX), y: limitar(rawY) };
}

export function criarProjecaoUnidade(
  referencias: Record<string, [number, number]>,
): ProjecaoUnidade {
  const bruto = IDS.map((id) => referencias[id] ?? null);
  if (bruto.some((ponto) => ponto === null)) {
    return { unidade: identidade };
  }

  const [oi, comer, beber, banheiro] = bruto as Array<[number, number]>;

  return {
    unidade: (rawX, rawY) => {
      // Estimativa inicial no centro da prancha.
      let u = 0.5;
      let v = 0.5;

      for (let i = 0; i < ITERACOES; i += 1) {
        // Para um v fixo, rawX é linear em u entre as colunas.
        const xEsq = (1 - v) * oi[0] + v * beber[0];
        const xDir = (1 - v) * comer[0] + v * banheiro[0];
        const largura = xDir - xEsq;
        if (Math.abs(largura) > 1e-6) {
          u = limitar((rawX - xEsq) / largura);
        }

        // Para um u fixo, rawY é linear em v entre as linhas.
        const yTopo = (1 - u) * oi[1] + u * comer[1];
        const yBase = (1 - u) * beber[1] + u * banheiro[1];
        const altura = yBase - yTopo;
        if (Math.abs(altura) > 1e-6) {
          v = limitar((rawY - yTopo) / altura);
        }
      }

      return { x: u, y: v };
    },
  };
}

/** True quando as quatro referências da prancha estão disponíveis. */
export function referenciasCompletas(
  referencias: Record<string, [number, number]> | undefined,
): boolean {
  return !!referencias && IDS.every((id) => Array.isArray(referencias[id]));
}

export function criarProjecaoMapa(
  referencias: Record<string, [number, number]>,
): ProjecaoMapa {
  const base = criarProjecaoUnidade(referencias);

  return {
    projetar: (rawX, rawY) => {
      const { x: u, y: v } = base.unidade(rawX, rawY);
      return {
        x: LAYOUT_ESQ + (LAYOUT_DIR - LAYOUT_ESQ) * u,
        y: LAYOUT_TOPO + (LAYOUT_BASE - LAYOUT_TOPO) * v,
      };
    },
  };
}
