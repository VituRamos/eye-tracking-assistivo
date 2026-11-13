"""
Pictogramas dos blocos, a partir dos SVGs fornecidos.

Os arquivos em ``assets/pictogramas`` são silhuetas vetoriais. O
renderizador aplica a tinta do tema por cima de uma máscara rasterizada
no tamanho supersamplificado da ``Lona``; assim o mesmo desenho serve
para os cartões pastel e para o botão escuro da tela de boas-vindas.

Nada aqui é usado pelo aplicativo de produção.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image

from .svg import Desenho, ler_svg, renderizar_mascara
from .tema import Lona

__all__ = ["PICTOGRAMAS", "caminho_do_pictograma", "desenhar_pictograma"]

PICTOGRAMAS = ("oi", "comer", "beber", "banheiro")

_PASTA = Path(__file__).resolve().parent / "assets" / "pictogramas"


def caminho_do_pictograma(nome: str) -> Path:
    """Devolve o SVG de ``nome`` ou levanta ``KeyError``."""
    if nome not in PICTOGRAMAS:
        raise KeyError(f"Pictograma desconhecido: {nome!r}")
    return _PASTA / f"{nome}.svg"


@lru_cache(maxsize=8)
def _desenho(nome: str) -> Desenho:
    return ler_svg(caminho_do_pictograma(nome))


@lru_cache(maxsize=64)
def _mascara(nome: str, lado: int) -> Image.Image:
    return renderizar_mascara(_desenho(nome), lado)


def desenhar_pictograma(
    lona: Lona,
    nome: str,
    cx: float,
    cy: float,
    tamanho: float,
    cor: tuple[int, int, int],
) -> None:
    """
    Desenha o pictograma ``nome`` centrado em ``(cx, cy)``.

    ``tamanho`` é o lado da caixa do ícone, em unidades de layout
    (1280x720). A tinta é sempre passada pelo chamador para permitir
    versões claras sobre fundo escuro.
    """
    lado = max(1, lona.px(tamanho))
    mascara = _mascara(nome, lado)
    camada = Image.new("RGBA", (lado, lado), (*cor, 255))
    x0 = lona.px(cx) - lado // 2
    y0 = lona.px(cy) - lado // 2
    lona.img.paste(camada, (x0, y0), mascara)
