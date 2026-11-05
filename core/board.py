"""
Prancha de comunicação: definição dos blocos e geometria da grade.

Uma "prancha" é uma grade de cartões (estilo PECS) que o usuário escolhe
com o olhar. Esta versão traz 4 blocos iniciais -- OI, COMER, BEBER e
BANHEIRO -- mas a lista é só um dado: acrescentar itens não exige mexer
na lógica de seleção.

Aqui ficam apenas funções puras (geometria e classificação por vizinho
mais próximo). O desenho está em ``ui/board_renderer.py`` e a
persistência da calibração em ``core/board_calibration.py``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Bloco:
    """Um cartão da prancha."""

    id: str
    rotulo: str
    linha: int
    coluna: int
    cor: tuple[int, int, int]  # BGR, cor de fundo do cartão
    icone: str  # nome do pictograma desenhado pelo renderizador


# Ordem de leitura: esquerda->direita, cima->baixo.
BLOCOS: tuple[Bloco, ...] = (
    Bloco("oi", "OI", 0, 0, (196, 186, 250), "oi"),
    Bloco("comer", "COMER", 0, 1, (86, 222, 250), "comer"),
    Bloco("beber", "BEBER", 1, 0, (126, 208, 126), "beber"),
    Bloco("banheiro", "BANHEIRO", 1, 1, (86, 172, 244), "banheiro"),
)

IDS_BLOCOS: tuple[str, ...] = tuple(b.id for b in BLOCOS)


def obter(bloco_id: str) -> Bloco:
    for bloco in BLOCOS:
        if bloco.id == bloco_id:
            return bloco
    raise KeyError(f"Bloco desconhecido: {bloco_id!r}")


def rotulo(bloco_id: str | None) -> str:
    if bloco_id is None:
        return ""
    return obter(bloco_id).rotulo


# =====================================================================
# Geometria
# =====================================================================
def retangulo(
    bloco: Bloco,
    largura: int,
    altura: int,
    margem: int = 28,
    espacamento: int = 18,
    topo: int = 104,
    base: int = 44,
) -> tuple[int, int, int, int]:
    """Retângulo (x1, y1, x2, y2) do cartão na tela."""
    largura_util = largura - 2 * margem - espacamento
    altura_util = altura - topo - base - espacamento
    largura_celula = largura_util // 2
    altura_celula = altura_util // 2

    x1 = margem + bloco.coluna * (largura_celula + espacamento)
    y1 = topo + bloco.linha * (altura_celula + espacamento)
    return x1, y1, x1 + largura_celula, y1 + altura_celula


def centro_do_bloco(
    bloco: Bloco,
    largura: int,
    altura: int,
    margem: int = 28,
    espacamento: int = 18,
    topo: int = 104,
    base: int = 44,
) -> tuple[int, int]:
    x1, y1, x2, y2 = retangulo(bloco, largura, altura, margem, espacamento, topo, base)
    return (x1 + x2) // 2, (y1 + y2) // 2


# =====================================================================
# Classificação por vizinho mais próximo
# =====================================================================
def classificar(
    ratio_x: float,
    ratio_y: float,
    referencias: dict[str, tuple[float, float]],
    raio_max: float = 0.55,
) -> str | None:
    """
    Devolve o id do bloco calibrado mais próximo do olhar.

    ``raio_max`` evita escolher um bloco quando o olhar está longe de
    todos os pontos calibrados (ex.: usuário olhando para o centro da
    tela ou para fora). Sem esse limite, *qualquer* posição escolheria
    algo.
    """
    if not referencias:
        return None

    melhor_id: str | None = None
    melhor_distancia = math.inf
    for bloco_id, (rx, ry) in referencias.items():
        distancia = math.hypot(ratio_x - rx, ratio_y - ry)
        if distancia < melhor_distancia:
            melhor_distancia = distancia
            melhor_id = bloco_id

    if melhor_distancia > raio_max:
        return None
    return melhor_id


def distancia_minima_entre_pontos(referencias: dict[str, tuple[float, float]]) -> float:
    """
    Menor distância entre dois pontos calibrados.

    Serve de medida de qualidade: se dois blocos ficam praticamente no
    mesmo ponto de olhar, a prancha não é utilizável.
    """
    pontos = list(referencias.values())
    menor = math.inf
    for i in range(len(pontos)):
        for j in range(i + 1, len(pontos)):
            menor = min(menor, math.hypot(pontos[i][0] - pontos[j][0],
                                          pontos[i][1] - pontos[j][1]))
    return 0.0 if menor is math.inf else menor
