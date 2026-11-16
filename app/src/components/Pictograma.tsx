import type { CSSProperties } from "react";
import banheiro from "../assets/pictogramas/banheiro.svg";
import beber from "../assets/pictogramas/beber.svg";
import comer from "../assets/pictogramas/comer.svg";
import oi from "../assets/pictogramas/oi.svg";
import type { BlocoId } from "../types";

const IMAGENS: Record<BlocoId, string> = { oi, comer, beber, banheiro };

/**
 * O Vite embute SVGs pequenos como `data:` URI com aspas simples e parênteses
 * (transform/scale) nas propriedades do XML. `url(...)` sem aspas não aceita
 * esses caracteres: o valor inteiro é descartado pelo CSS e o pictograma vira
 * um quadrado. Percent-encoding resolve sem desligar o inline de assets.
 */
function urlMascara(url: string): string {
  return url
    .replace(/['"]/g, "%22")
    .replace(/\s/g, "%20")
    .replace(/\(/g, "%28")
    .replace(/\)/g, "%29");
}

interface Props {
  id: BlocoId;
  tamanho: number;
  cor: string;
  className?: string;
}

/**
 * Usa o SVG original do _v2 como máscara para poder tingir com qualquer cor.
 *
 * A URL vai numa custom property (`--pictograma`) e a regra `.pictograma` em
 * `index.css` aplica a máscara.
 */
export function Pictograma({ id, tamanho, cor, className }: Props) {
  const estilo = {
    width: tamanho,
    height: tamanho,
    backgroundColor: cor,
    "--pictograma": `url(${urlMascara(IMAGENS[id])})`,
  } as CSSProperties;

  return (
    <span
      aria-hidden
      className={`pictograma ${className ?? ""}`}
      style={estilo}
    />
  );
}
