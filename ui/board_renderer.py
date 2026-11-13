"""
Desenho da prancha de comunicação (grade de cartões) no novo design.

Este módulo só desenha: recebe o bloco focado, o progresso do dwell e o
bloco confirmado, e pinta a tela. Toda a decisão de *qual* bloco está
focado continua em ``core/board.py``; a persistência da calibração, em
``core/board_calibration.py``.

As telas são desenhadas com a Pillow na ``Lona`` de ``ui/design.py`` e
copiadas para o frame BGR usado pelo OpenCV. Nenhum tempo, limiar ou
decisão de seleção é alterado aqui.
"""
from __future__ import annotations

from core import board
from core.board import BLOCOS, Bloco

from .design import (
    ALTURA_BASE,
    BASE_GRADE,
    CORES,
    CORES_CARTAO,
    ESPACAMENTO,
    LARGURA_BASE,
    MARGEM,
    RAIO_CARTAO,
    TOPO_GRADE,
    Lona,
    alerta,
    aplicar,
    cabecalho,
    centro,
    circulo_check,
    desenhar_pictograma,
    misturar,
    rodape,
)


# =====================================================================
# Geometria e cartões
# =====================================================================
def _geometria(
    bloco: Bloco,
    topo: float = TOPO_GRADE,
    base: float = BASE_GRADE,
    margem: float = MARGEM,
    espacamento: float = ESPACAMENTO,
) -> tuple[int, int, int, int]:
    largura_util = LARGURA_BASE - 2 * margem - espacamento
    altura_util = ALTURA_BASE - topo - base - espacamento
    largura_celula = largura_util // 2
    altura_celula = altura_util // 2
    x1 = int(margem + bloco.coluna * (largura_celula + espacamento))
    y1 = int(topo + bloco.linha * (altura_celula + espacamento))
    return x1, y1, x1 + largura_celula, y1 + altura_celula


def _anel(
    lona: Lona,
    caixa: tuple[float, float, float, float],
    raio: float,
    cor: tuple[int, int, int],
) -> None:
    """Halo branco externo + anel interno colorido (funciona no pastel)."""
    x1, y1, x2, y2 = caixa
    lona.retangulo(
        (x1 - 10, y1 - 10, x2 + 10, y2 + 10),
        None,
        raio + 10,
        CORES["superficie"],
        8,
    )
    lona.retangulo((x1 - 3, y1 - 3, x2 + 3, y2 + 3), None, raio + 3, cor, 8)


def _cartao(
    lona: Lona,
    bloco: Bloco,
    *,
    foco: bool = False,
    confirmado: bool = False,
    progresso: float = 0.0,
    mostrar_icone: bool = True,
    cor_fundo: tuple[int, int, int] | None = None,
    rotulo_cor: tuple[int, int, int] | None = None,
    topo: float = TOPO_GRADE,
    base: float = BASE_GRADE,
) -> None:
    x1, y1, x2, y2 = _geometria(bloco, topo=topo, base=base)
    if cor_fundo is None:
        cor_fundo = CORES_CARTAO[bloco.id]

    borda = (
        CORES["borda"]
        if cor_fundo == CORES["superficie"]
        else misturar(cor_fundo, CORES["texto"], 0.10)
    )
    lona.retangulo((x1, y1, x2, y2), cor_fundo, RAIO_CARTAO, borda, 1)

    if mostrar_icone:
        # Ícone centralizado acima do rótulo.
        cx = (x1 + x2) / 2
        tamanho = min(x2 - x1, y2 - y1) * 0.35
        cy_icone = y1 + (y2 - y1) * 0.38
        desenhar_pictograma(
            lona,
            bloco.icone,
            cx,
            cy_icone,
            tamanho,
            CORES["texto"],
        )

        # Rótulo abaixo do ícone.
        cy_rotulo = y1 + (y2 - y1) * 0.72
        lona.texto(
            (cx, cy_rotulo),
            bloco.rotulo,
            40,
            rotulo_cor or CORES["texto"],
            "bold",
            anchor="mm",
        )

    if foco:
        _anel(lona, (x1, y1, x2, y2), RAIO_CARTAO, CORES["foco"])
    if confirmado:
        _anel(lona, (x1, y1, x2, y2), RAIO_CARTAO, CORES["confirmado"])
        circulo_check(lona, x2 - 32, y1 + 32, 20, CORES["confirmado"], preenchido=True)
        texto = "Confirmado"
        largura = lona.largura_texto(texto, 14, "semibold") + 28
        cx = (x1 + x2) / 2
        py1, py2 = y2 - 40, y2 - 12
        lona.retangulo(
            (cx - largura / 2, py1, cx + largura / 2, py2),
            CORES["confirmado"],
            (py2 - py1) / 2,
        )
        centro(lona, cx, (py1 + py2) / 2, texto, 14, CORES["branco"], "semibold")

    if foco and not confirmado and progresso > 0:
        progresso = max(0.0, min(1.0, float(progresso)))
        px1, py1 = x1 + 36, y2 - 34
        px2, py2 = px1 + 220, y2 - 24
        trilho = misturar(cor_fundo, CORES["texto"], 0.14)
        lona.retangulo((px1, py1, px2, py2), trilho, 5)
        preenchido = (px2 - px1) * progresso
        if preenchido > 4:
            lona.retangulo((px1, py1, px1 + preenchido, py2), CORES["texto"], 5)


def _barra(lona: Lona, progresso: float, *, y1: float = 676, y2: float = 686) -> None:
    progresso = max(0.0, min(1.0, float(progresso)))
    x1, x2 = MARGEM, LARGURA_BASE - MARGEM
    lona.retangulo((x1, y1, x2, y2), misturar(CORES["fundo"], CORES["texto"], 0.12), 5)
    if progresso > 0:
        lona.retangulo((x1, y1, x1 + (x2 - x1) * progresso, y2), CORES["texto"], 5)


# =====================================================================
# Telas
# =====================================================================
def desenhar_prancha(
    frame,
    largura: int,
    altura: int,
    foco: str | None = None,
    progresso: float = 0.0,
    confirmado: str | None = None,
    perfil: str | None = None,
) -> None:
    """Tela da prancha no modo de uso (seleção por olhar)."""
    lona = Lona(largura, altura)

    if confirmado:
        cabecalho(
            lona,
            "Prancha",
            f"Perfil: {perfil or 'padrão'}",
        )
        lona.retangulo(
            (MARGEM, 88, LARGURA_BASE - MARGEM, 126),
            CORES["confirmado_fundo"],
            12,
            CORES["confirmado"],
            1.5,
        )
        circulo_check(lona, 84, 107, 11, CORES["confirmado"], preenchido=True)
        lona.texto(
            (106, 107),
            f"Você escolheu: {board.rotulo(confirmado)}",
            18,
            CORES["confirmado"],
            "semibold",
            anchor="lm",
        )
    else:
        instrucao = (
            f"Olhando para {board.rotulo(foco)}."
            if foco
            else "Pronto. Olhe para um cartão."
        )
        cabecalho(
            lona,
            "Prancha",
            f"Perfil: {perfil or 'padrão'}",
            instrucao=instrucao,
        )

    for bloco in BLOCOS:
        _cartao(
            lona,
            bloco,
            foco=(bloco.id == foco),
            confirmado=(bloco.id == confirmado),
            progresso=progresso if bloco.id == foco else 0.0,
        )

    if confirmado:
        esquerda = "A prancha volta ao normal em instantes."
    elif foco:
        esquerda = f"Mantenha o olhar em {board.rotulo(foco)}."
    else:
        esquerda = "Olhe para um cartão e mantenha o olhar."
    lona.texto((MARGEM, 700), esquerda, 15, CORES["apoio"], anchor="lm")
    lona.texto(
        (LARGURA_BASE - MARGEM, 700),
        "[M] Voltar ao menu",
        15,
        CORES["apoio"],
        anchor="rm",
    )
    aplicar(frame, lona.finalizar())


def desenhar_calibracao_prancha(
    frame,
    largura: int,
    altura: int,
    bloco_id: str,
    indice: int,
    total: int,
    progresso: float = 0.0,
    amostras: int = 0,
    minimo_amostras: int = 0,
    descartadas: int = 0,
    aguardando: bool = False,
) -> None:
    """Calibração da prancha: destaca o bloco alvo e mostra a coleta."""
    lona = Lona(largura, altura)
    cabecalho(
        lona,
        f"Bloco {indice + 1} de {total}: olhe para {board.rotulo(bloco_id)}",
        "Calibração da prancha",
        direita_texto=f"Cuidador: {amostras} de {minimo_amostras} amostras",
        direita_tamanho=13,
    )

    topo, base = 124, 66
    for bloco in BLOCOS:
        if bloco.id == bloco_id:
            _cartao(
                lona,
                bloco,
                foco=True,
                cor_fundo=CORES_CARTAO[bloco.id],
                topo=topo,
                base=base,
            )
        else:
            _cartao(
                lona,
                bloco,
                mostrar_icone=False,
                cor_fundo=CORES["neutro"],
                rotulo_cor=CORES["apoio"],
                topo=topo,
                base=base,
            )

    _barra(lona, progresso)
    if aguardando:
        texto = "Aperte ESPAÇO para começar a coleta   ·   [M] Voltar ao menu"
    else:
        texto = (
            f"{amostras}/{minimo_amostras} amostras válidas"
            f"   ·   {descartadas} descartadas (piscada/pose)"
            "   ·   [M] Cancelar"
        )
    centro(lona, LARGURA_BASE / 2, 703, texto, 14, CORES["apoio"])
    aplicar(frame, lona.finalizar())


def _chip_status(
    lona: Lona,
    x1: float,
    x2: float,
    y1: float,
    y2: float,
    rotulo: str,
    detalhe: str,
    cor: tuple[int, int, int],
) -> None:
    lona.retangulo((x1, y1, x2, y2), CORES["superficie"], 16, CORES["borda"], 1)
    centro(
        lona, (x1 + x2) / 2, y1 + 24, rotulo, 16, CORES["texto"], "semibold"
    )
    centro(lona, (x1 + x2) / 2, y1 + 50, detalhe, 14, cor, "semibold")


def desenhar_prancha_concluida(
    frame,
    largura: int,
    altura: int,
    sucesso: bool,
    referencias: dict[str, tuple[float, float]],
    distancia_minima: float,
) -> None:
    """Tela final da calibração da prancha."""
    lona = Lona(largura, altura)
    cabecalho(lona, "Calibração da prancha", "Modo cuidador")

    if sucesso:
        circulo_check(lona, LARGURA_BASE / 2, 218, 28, CORES["confirmado"])
        centro(lona, LARGURA_BASE / 2, 286, "Calibração concluída", 40,
               CORES["texto"], "bold")
        centro(
            lona,
            LARGURA_BASE / 2,
            326,
            "Qualidade boa. A prancha já está pronta.",
            20,
            CORES["apoio"],
        )
    else:
        alerta(lona, LARGURA_BASE / 2, 218, 28, CORES["atencao"])
        centro(lona, LARGURA_BASE / 2, 286, "Calibração fraca", 40,
               CORES["texto"], "bold")
        centro(
            lona,
            LARGURA_BASE / 2,
            326,
            "Os cartões ficaram muito próximos. Repita olhando bem para cada um.",
            19,
            CORES["apoio"],
        )

    largura_chip, gap = 176, 14
    inicio = LARGURA_BASE / 2 - (4 * largura_chip + 3 * gap) / 2
    for indice, bloco in enumerate(BLOCOS):
        x1 = inicio + indice * (largura_chip + gap)
        ponto = referencias.get(bloco.id)
        if ponto is None:
            detalhe, cor = "não coletado", CORES["atencao"]
        else:
            detalhe = f"x={ponto[0]:.2f}  y={ponto[1]:.2f}"
            cor = CORES["confirmado"] if sucesso else CORES["atencao"]
        _chip_status(lona, x1, x1 + largura_chip, 374, 446, bloco.rotulo, detalhe, cor)

    centro(
        lona,
        LARGURA_BASE / 2,
        486,
        f"Separação mínima entre cartões: {distancia_minima:.3f}",
        15,
        CORES["apoio"],
    )
    rodape(lona, "Cuidador: [ENTER] para voltar ao menu", y=572)
    aplicar(frame, lona.finalizar())
