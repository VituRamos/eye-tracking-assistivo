"""
Telas do novo design (tema claro) para o preview isolado.

Cada função devolve uma ``PIL.Image`` no tamanho pedido. O layout é
calculado em unidades de 1280x720 e escalado pela ``Lona``. Nenhuma
função altera o estado do app, tempos ou calibração: são apenas imagens.
"""
from __future__ import annotations

import math
from collections.abc import Callable

from PIL import Image

from core import board
from core.board import BLOCOS, Bloco

from .icones import desenhar_pictograma
from .tema import (
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
    misturar,
)

Tela = Callable[[int, int], Image.Image]
Caixa = tuple[float, float, float, float]

# =====================================================================
# Componentes básicos
# =====================================================================
def _marca(lona: Lona, x: float = 56, y: float = 34) -> None:
    """Marca da prancha: quatro quadrantes nas cores dos cartões."""
    lado = 11
    gap = 3
    lona.retangulo((x, y, x + lado, y + lado), CORES["texto"], 3)
    lona.retangulo((x + lado + gap, y, x + 2 * lado + gap, y + lado), CORES["oi"], 3)
    lona.retangulo((x, y + lado + gap, x + lado, y + 2 * lado + gap), CORES["beber"], 3)
    lona.retangulo(
        (x + lado + gap, y + lado + gap, x + 2 * lado + gap, y + 2 * lado + gap),
        CORES["comer"],
        3,
    )


def _pilula(
    lona: Lona,
    x: float,
    y: float,
    texto: str,
    *,
    tamanho: float = 14,
    altura: float = 30,
    fundo: tuple[int, int, int] = CORES["superficie"],
    cor: tuple[int, int, int] = CORES["apoio"],
    borda: tuple[int, int, int] = CORES["borda"],
    padding: float = 14,
    anchor: str = "left",
    peso: str = "regular",
) -> Caixa:
    largura = lona.largura_texto(texto, tamanho, peso) + 2 * padding
    x1 = x - largura if anchor == "right" else x
    caixa = (x1, y, x1 + largura, y + altura)
    lona.retangulo(caixa, fundo, altura / 2, borda, 1)
    lona.texto(
        ((caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2),
        texto,
        tamanho,
        cor,
        peso,
        anchor="mm",
    )
    return caixa


def _botao(
    lona: Lona,
    caixa: Caixa,
    texto: str,
    *,
    primario: bool = True,
    tamanho: float = 20,
) -> None:
    if primario:
        fundo, cor, borda = CORES["texto"], CORES["branco"], None
    else:
        fundo, cor, borda = CORES["superficie"], CORES["texto"], CORES["borda"]
    lona.retangulo(caixa, fundo, 14, borda, 1.5)
    lona.texto(
        ((caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2),
        texto,
        tamanho,
        cor,
        "semibold",
        anchor="mm",
    )


def _centro(lona: Lona, x: float, y: float, texto: str, tamanho: float,
            cor: tuple[int, int, int] = CORES["texto"], peso: str = "regular") -> None:
    lona.texto((x, y), texto, tamanho, cor, peso, anchor="mm")


def _cabecalho(
    lona: Lona,
    titulo: str,
    subtitulo: str | None = None,
    *,
    instrucao: str | None = None,
    direita_texto: str | None = None,
    direita_tamanho: float = 14,
    direita_peso: str = "regular",
) -> None:
    _marca(lona)
    lona.texto((96, 48), titulo, 22, CORES["texto"], "semibold", anchor="lm")
    if subtitulo:
        lona.texto((96, 72), subtitulo, 14, CORES["apoio"], anchor="lm")
    if direita_texto:
        _pilula(
            lona,
            1224,
            32,
            direita_texto,
            tamanho=direita_tamanho,
            anchor="right",
            peso=direita_peso,
        )
    if instrucao:
        _centro(lona, 640, 100, instrucao, 18, CORES["apoio"])


def _rodape(
    lona: Lona,
    esquerda: str | None = None,
    direita: str | None = "Cuidador: Esc para pausar",
) -> None:
    if esquerda:
        lona.texto((MARGEM, 700), esquerda, 15, CORES["apoio"], anchor="lm")
    if direita:
        lona.texto((LARGURA_BASE - MARGEM, 700), direita, 15, CORES["apoio"], anchor="rm")


def _rodape_centro(lona: Lona, texto: str) -> None:
    _centro(lona, 640, 700, texto, 14, CORES["apoio"])


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


def _linha_arredondada(
    lona: Lona,
    pontos: list[tuple[float, float]],
    cor: tuple[int, int, int],
    largura: float,
) -> None:
    lona.linha(pontos, cor, largura)
    for ponto in pontos:
        lona.circulo(ponto, largura / 2, cor=cor)


def _check(lona: Lona, cx: float, cy: float, raio: float,
           cor: tuple[int, int, int], largura: float) -> None:
    _linha_arredondada(
        lona,
        [
            (cx - raio * 0.46, cy + raio * 0.02),
            (cx - raio * 0.10, cy + raio * 0.38),
            (cx + raio * 0.50, cy - raio * 0.38),
        ],
        cor,
        largura,
    )


def _circulo_check(lona: Lona, cx: float, cy: float, raio: float,
                   cor: tuple[int, int, int], *, preenchido: bool = False) -> None:
    if preenchido:
        lona.circulo((cx, cy), raio, cor=cor)
        _check(lona, cx, cy, raio * 0.72, CORES["branco"], max(3.0, raio * 0.16))
    else:
        lona.circulo((cx, cy), raio, contorno=cor, largura=4)
        _check(lona, cx, cy, raio * 0.72, cor, max(3.5, raio * 0.16))


def _detalhe_com_check(
    lona: Lona,
    cx: float,
    y: float,
    texto: str,
    cor: tuple[int, int, int],
    tamanho: float = 14,
) -> None:
    """Detalhe com um check desenhado (o glifo ✓ não existe no Segoe UI)."""
    largura_texto = lona.largura_texto(texto, tamanho)
    largura_check, gap = 10, 6
    total = largura_check + gap + largura_texto
    x = cx - total / 2
    _check(lona, x + largura_check / 2, y, 5, cor, 2)
    lona.texto((x + largura_check + gap, y), texto, tamanho, cor, anchor="lm")


def _arco(
    lona: Lona,
    cx: float,
    cy: float,
    raio: float,
    inicio: float,
    fim: float,
    cor: tuple[int, int, int],
    largura: float,
    passos: int = 24,
) -> None:
    """Arco aproximado por uma polilinha com pontas arredondadas."""
    pontos = []
    for indice in range(passos + 1):
        angulo = math.radians(inicio + (fim - inicio) * indice / passos)
        pontos.append((cx + raio * math.cos(angulo), cy + raio * math.sin(angulo)))
    _linha_arredondada(lona, pontos, cor, largura)


def _icone_menu(
    lona: Lona,
    nome: str,
    cx: float,
    cy: float,
    cor: tuple[int, int, int],
) -> None:
    """Ícones de 20x20 usados na navegação lateral."""
    esp = 2.2
    if nome == "iniciar":
        lona.poligono(
            [(cx - 4, cy - 7), (cx + 7, cy), (cx - 4, cy + 7)],
            cor=cor,
        )
    elif nome == "perfis":
        lona.circulo((cx, cy - 4.5), 3.6, contorno=cor, largura=esp)
        _arco(lona, cx, cy + 9, 7, 200, 340, cor, esp)
    elif nome == "calibracao":
        lona.circulo((cx, cy), 8, contorno=cor, largura=esp)
        lona.circulo((cx, cy), 4, contorno=cor, largura=esp)
        lona.circulo((cx, cy), 1.5, cor=cor)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            lona.linha(
                [(cx + dx * 8, cy + dy * 8), (cx + dx * 10, cy + dy * 10)],
                cor,
                esp,
            )
    elif nome == "cuidador":
        escudo = [
            (cx, cy - 9),
            (cx - 7, cy - 6),
            (cx - 7, cy + 0.5),
            (cx - 4, cy + 5),
            (cx, cy + 8),
            (cx + 4, cy + 5),
            (cx + 7, cy + 0.5),
            (cx + 7, cy - 6),
            (cx, cy - 9),
        ]
        _linha_arredondada(lona, escudo, cor, esp)
        _check(lona, cx, cy - 0.5, 4.5, cor, 2)
    elif nome == "configuracoes":
        for indice in range(8):
            angulo = math.radians(indice * 45)
            cosseno, seno = math.cos(angulo), math.sin(angulo)
            _linha_arredondada(
                lona,
                [
                    (cx + 5.5 * cosseno, cy + 5.5 * seno),
                    (cx + 8.5 * cosseno, cy + 8.5 * seno),
                ],
                cor,
                esp + 0.6,
            )
        lona.circulo((cx, cy), 5.2, contorno=cor, largura=esp)
        lona.circulo((cx, cy), 1.7, cor=cor)
    elif nome == "sair":
        _arco(lona, cx, cy + 1, 7.5, 300, 600, cor, esp, passos=28)
        _linha_arredondada(lona, [(cx, cy - 8.5), (cx, cy - 1.5)], cor, esp)
    else:
        raise ValueError(f"Ícone de menu desconhecido: {nome!r}")


def _alerta(lona: Lona, cx: float, cy: float, raio: float,
            cor: tuple[int, int, int], *, preenchido: bool = False) -> None:
    if preenchido:
        lona.circulo((cx, cy), raio, cor=cor)
        _centro(lona, cx, cy - 1, "!", raio * 1.45, CORES["branco"], "bold")
    else:
        lona.circulo((cx, cy), raio, contorno=cor, largura=4)
        _centro(lona, cx, cy - 2, "!", raio * 1.25, cor, "bold")


def _pausa_icone(lona: Lona, cx: float, cy: float, raio: float) -> None:
    lona.circulo((cx, cy), raio, contorno=CORES["texto"], largura=4)
    for deslocamento in (-7, 7):
        lona.retangulo(
            (cx + deslocamento - 3, cy - 11, cx + deslocamento + 3, cy + 11),
            CORES["texto"],
            3,
        )


def _icone_rosto(lona: Lona, cx: float, cy: float, cor: tuple[int, int, int]) -> None:
    lona.circulo((cx, cy), 10, contorno=cor, largura=2.5)
    lona.circulo((cx - 3.5, cy - 2), 1.4, cor=cor)
    lona.circulo((cx + 3.5, cy - 2), 1.4, cor=cor)
    lona.linha([(cx - 3.5, cy + 4), (cx + 3.5, cy + 4)], cor, 2)


def _icone_cabeca(lona: Lona, cx: float, cy: float, cor: tuple[int, int, int]) -> None:
    lona.circulo((cx - 4, cy), 9, contorno=cor, largura=2.5)
    lona.circulo((cx - 1, cy - 2), 1.3, cor=cor)
    lona.linha([(cx + 6, cy), (cx + 18, cy)], cor, 2.5)
    lona.linha([(cx + 13, cy - 4), (cx + 18, cy)], cor, 2.5)
    lona.linha([(cx + 13, cy + 4), (cx + 18, cy)], cor, 2.5)


def _banner(lona: Lona, texto: str, *, icone: str, y1: float = 88, y2: float = 130) -> None:
    lona.retangulo(
        (MARGEM, y1, LARGURA_BASE - MARGEM, y2),
        CORES["atencao_fundo"],
        12,
        CORES["atencao"],
        1.5,
    )
    cy = (y1 + y2) / 2
    if icone == "rosto":
        _icone_rosto(lona, 84, cy, CORES["atencao"])
    elif icone == "cabeca":
        _icone_cabeca(lona, 82, cy, CORES["atencao"])
    else:
        _alerta(lona, 84, cy, 11, CORES["atencao"], preenchido=True)
    lona.texto((108, cy), texto, 18, CORES["atencao"], "semibold", anchor="lm")


def _anel(lona: Lona, caixa: Caixa, raio: float, cor: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = caixa
    # Halo branco externo + anel interno colorido. Funciona sobre qualquer pastel.
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

    centro_y = (y1 + y2) / 2
    if mostrar_icone:
        cx_icone = x1 + (x2 - x1) * 0.19
        tamanho = min(x2 - x1, y2 - y1) * 0.40
        desenhar_pictograma(
            lona,
            bloco.icone,
            cx_icone,
            centro_y,
            tamanho,
            CORES["texto"],
        )
        cx_rotulo = x1 + (x2 - x1) * 0.64
        lona.texto(
            (cx_rotulo, centro_y),
            bloco.rotulo,
            50,
            rotulo_cor or CORES["texto"],
            "bold",
            anchor="mm",
        )
    else:
        _centro(
            lona,
            (x1 + x2) / 2,
            centro_y,
            bloco.rotulo,
            44,
            rotulo_cor or CORES["texto"],
            "semibold",
        )

    if foco:
        _anel(lona, (x1, y1, x2, y2), RAIO_CARTAO, CORES["foco"])
    if confirmado:
        _anel(lona, (x1, y1, x2, y2), RAIO_CARTAO, CORES["confirmado"])
        _circulo_check(lona, x2 - 32, y1 + 32, 20, CORES["confirmado"], preenchido=True)
        texto = "Confirmado"
        largura = lona.largura_texto(texto, 14, "semibold") + 28
        cx = (x1 + x2) / 2
        py1, py2 = y2 - 40, y2 - 12
        lona.retangulo((cx - largura / 2, py1, cx + largura / 2, py2),
                       CORES["confirmado"], (py2 - py1) / 2)
        _centro(lona, cx, (py1 + py2) / 2, texto, 14, CORES["branco"], "semibold")

    if foco and not confirmado and progresso > 0:
        progresso = max(0.0, min(1.0, float(progresso)))
        px1, py1 = x1 + 36, y2 - 34
        px2, py2 = px1 + 220, y2 - 24
        trilho = misturar(cor_fundo, CORES["texto"], 0.14)
        lona.retangulo((px1, py1, px2, py2), trilho, 5)
        preenchido = (px2 - px1) * progresso
        if preenchido > 4:
            lona.retangulo((px1, py1, px1 + preenchido, py2), CORES["texto"], 5)


# =====================================================================
# Telas
# =====================================================================
_LARGURA_MENU = 300
_LARGURA_MENU_RECOLHIDA = 88
_Y_TOGGLE_MENU = 612


def _item_menu(
    lona: Lona,
    y: float,
    rotulo: str,
    icone: str,
    *,
    ativo: bool = False,
    cor: tuple[int, int, int] | None = None,
    recolhido: bool = False,
) -> None:
    largura = _LARGURA_MENU_RECOLHIDA if recolhido else _LARGURA_MENU
    margem = 8 if recolhido else 16
    tinta = cor or (CORES["texto"] if ativo else CORES["apoio"])

    if ativo:
        lona.retangulo((margem, y, largura - margem, y + 56), CORES["neutro"], 12)
        if not recolhido:
            lona.retangulo((16, y + 12, 20, y + 44), CORES["texto"], 2)

    centro = largura / 2 if recolhido else 44
    _icone_menu(lona, icone, centro, y + 28, tinta)
    if not recolhido:
        lona.texto(
            (76, y + 28),
            rotulo,
            19 if ativo else 18,
            tinta,
            "semibold" if ativo else "regular",
            anchor="lm",
        )


def _chevron(
    lona: Lona,
    cx: float,
    cy: float,
    cor: tuple[int, int, int],
    *,
    para_esquerda: bool,
) -> None:
    lado = 4.5
    direcao = -1 if para_esquerda else 1
    _linha_arredondada(
        lona,
        [
            (cx - direcao * lado / 2, cy - lado),
            (cx + direcao * lado / 2, cy),
            (cx - direcao * lado / 2, cy + lado),
        ],
        cor,
        2.2,
    )


def _botao_menu(lona: Lona, *, recolhido: bool) -> None:
    """Botão de alternância no rodapé da barra lateral."""
    largura = _LARGURA_MENU_RECOLHIDA if recolhido else _LARGURA_MENU
    lona.retangulo(
        (16, _Y_TOGGLE_MENU, largura - 16, _Y_TOGGLE_MENU + 48),
        None,
        12,
        CORES["borda"],
        1,
    )
    _chevron(
        lona,
        44,
        _Y_TOGGLE_MENU + 24,
        CORES["apoio"],
        para_esquerda=not recolhido,
    )
    if not recolhido:
        lona.texto(
            (76, _Y_TOGGLE_MENU + 24),
            "Recolher menu",
            15,
            CORES["apoio"],
            anchor="lm",
        )


def _tela_inicial(
    largura: int,
    altura: int,
    *,
    calibrado: bool,
    recolhido: bool = False,
) -> Image.Image:
    """Tela inicial: menu lateral, ação principal e resumo do perfil."""
    lona = Lona(largura, altura)
    largura_menu = _LARGURA_MENU_RECOLHIDA if recolhido else _LARGURA_MENU

    # Barra lateral
    lona.retangulo((0, 0, largura_menu, ALTURA_BASE), CORES["superficie"])
    lona.retangulo((largura_menu - 1, 0, largura_menu, ALTURA_BASE), CORES["borda"])
    _marca(lona, 32, 36)
    if not recolhido:
        lona.texto((70, 48), "Prancha", 20, CORES["texto"], "semibold", anchor="lm")
        lona.texto((32, 80), "Comunicação pelo olhar", 13, CORES["apoio"], anchor="lm")

    y = 136
    for rotulo, icone, ativo in (
        ("Iniciar", "iniciar", True),
        ("Perfis", "perfis", False),
        ("Calibração", "calibracao", False),
        ("Modo Cuidador", "cuidador", False),
        ("Configurações", "configuracoes", False),
    ):
        _item_menu(lona, y, rotulo, icone, ativo=ativo, recolhido=recolhido)
        y += 64

    lona.retangulo((16, y + 22, largura_menu - 16, y + 23), CORES["borda"])
    _item_menu(
        lona,
        y + 30,
        "Sair",
        "sair",
        cor=CORES["atencao"],
        recolhido=recolhido,
    )

    _botao_menu(lona, recolhido=recolhido)
    if recolhido:
        lona.texto(
            (largura_menu / 2, 690),
            "v2.1",
            12,
            CORES["apoio"],
            anchor="mm",
        )
    else:
        lona.texto((32, 690), "v2.1", 12, CORES["apoio"], anchor="lm")

    # Conteúdo principal
    x0 = largura_menu + 44
    x1 = LARGURA_BASE - MARGEM
    lona.texto((x0, 44), "Início", 14, CORES["apoio"], anchor="lm")

    texto_camera = "Câmera pronta"
    largura_camera = lona.largura_texto(texto_camera, 14) + 46
    lona.retangulo(
        (x1 - largura_camera, 26, x1, 60),
        CORES["superficie"],
        17,
        CORES["borda"],
        1,
    )
    lona.circulo((x1 - largura_camera + 16, 43), 5, cor=CORES["confirmado"])
    lona.texto((x1 - largura_camera + 30, 43), texto_camera, 14, CORES["apoio"], anchor="lm")

    lona.texto((x0, 110), "Olá, Ana", 42, CORES["texto"], "bold", anchor="lm")
    lona.texto((x0, 152), "O que você quer fazer?", 20, CORES["apoio"], anchor="lm")
    if not calibrado:
        _alerta(lona, x0 + 9, 188, 9, CORES["atencao"])
        lona.texto(
            (x0 + 28, 188),
            "Calibração pendente. O cuidador pode ajudar.",
            15,
            CORES["atencao"],
            anchor="lm",
        )

    # Ação principal
    resumo_x = x1 - 256
    cartao_fim = resumo_x - 24
    lona.retangulo((x0, 214, cartao_fim, 520), CORES["texto"], 30)
    desenhar_pictograma(lona, "oi", x0 + 110, 367, 150, CORES["fundo"])
    lona.texto((x0 + 216, 340), "Iniciar", 54, CORES["fundo"], "bold", anchor="lm")
    lona.texto(
        (x0 + 218, 386),
        "Abrir a prancha de comunicação",
        18,
        (207, 203, 194),
        anchor="lm",
    )
    _linha_arredondada(
        lona,
        [
            (cartao_fim - 60, 347),
            (cartao_fim - 40, 367),
            (cartao_fim - 60, 387),
        ],
        (207, 203, 194),
        4,
    )

    # Resumo do perfil
    lona.retangulo((resumo_x, 214, x1, 520), CORES["superficie"], 22, CORES["borda"], 1)
    lona.texto((resumo_x + 24, 248), "Perfil ativo", 13, CORES["apoio"], anchor="lm")
    lona.texto((resumo_x + 24, 278), "Ana", 26, CORES["texto"], "semibold", anchor="lm")
    lona.retangulo((resumo_x + 24, 304, x1 - 24, 305), CORES["borda"])

    linhas = (
        (
            "Calibração",
            "Concluída há 2 dias" if calibrado else "Pendente",
            CORES["confirmado"] if calibrado else CORES["atencao"],
        ),
        ("Câmera", "Pronta", CORES["confirmado"]),
        ("Modo cuidador", "Tecla F2", CORES["texto"]),
    )
    y = 330
    for rotulo, valor, cor in linhas:
        lona.texto((resumo_x + 24, y), rotulo, 13, CORES["apoio"], anchor="lm")
        lona.texto((resumo_x + 24, y + 24), valor, 15, cor, "semibold", anchor="lm")
        y += 58

    _centro(
        lona,
        (x0 + x1) / 2,
        690,
        "Olhe para uma opção e mantenha o olhar para escolher.",
        14,
        CORES["apoio"],
    )
    return lona.finalizar()


def tela_boas_vindas(largura: int, altura: int) -> Image.Image:
    """Tela inicial com o perfil já calibrado."""
    return _tela_inicial(largura, altura, calibrado=True)


def tela_boas_vindas_recolhida(largura: int, altura: int) -> Image.Image:
    """Tela inicial com a barra lateral recolhida (apenas ícones)."""
    return _tela_inicial(largura, altura, calibrado=True, recolhido=True)


def tela_boas_vindas_sem_calibracao(largura: int, altura: int) -> Image.Image:
    """Tela inicial com aviso de calibração pendente."""
    return _tela_inicial(largura, altura, calibrado=False)


def tela_prancha(
    largura: int,
    altura: int,
    *,
    foco: str | None = None,
    progresso: float = 0.0,
    confirmado: str | None = None,
    perfil: str = "Ana",
) -> Image.Image:
    """Prancha em repouso, com foco/progresso ou com confirmação."""
    lona = Lona(largura, altura)
    if confirmado:
        _cabecalho(lona, perfil)
        lona.retangulo(
            (MARGEM, 78, LARGURA_BASE - MARGEM, 118),
            CORES["confirmado_fundo"],
            12,
            CORES["confirmado"],
            1.5,
        )
        _circulo_check(lona, 82, 98, 11, CORES["confirmado"], preenchido=True)
        lona.texto(
            (104, 98),
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
        _cabecalho(lona, perfil, "Prancha · comunicação pelo olhar", instrucao=instrucao)

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
    _rodape(lona, esquerda)
    return lona.finalizar()


def tela_calibracao_intro(largura: int, altura: int) -> Image.Image:
    """Introdução da calibração, em linguagem de cuidador."""
    lona = Lona(largura, altura)
    _cabecalho(lona, "Modo cuidador · Perfil Ana", "Prancha · calibração")
    _centro(lona, 640, 178, "Vamos calibrar o olhar", 40, CORES["texto"], "bold")
    _centro(lona, 640, 220, "O sistema aprende onde fica cada cartão.",
            20, CORES["apoio"])

    itens = (
        ("4 cartões", "um de cada vez"),
        ("Olhe firme", "não precisa piscar"),
        ("Cerca de 30 s", "sem pressa"),
    )
    largura_cartao, gap = 260, 20
    inicio = 640 - (3 * largura_cartao + 2 * gap) / 2
    for indice, (titulo, detalhe) in enumerate(itens):
        x1 = inicio + indice * (largura_cartao + gap)
        y1, y2 = 278, 388
        lona.retangulo((x1, y1, x1 + largura_cartao, y2),
                       CORES["superficie"], 18, CORES["borda"], 1)
        _centro(lona, x1 + largura_cartao / 2, y1 + 40, titulo, 19, CORES["texto"], "semibold")
        _centro(lona, x1 + largura_cartao / 2, y1 + 72, detalhe, 15, CORES["apoio"])

    _botao(lona, (530, 442, 750, 500), "Iniciar", primario=True, tamanho=22)
    _rodape_centro(lona, "Cuidador: Enter para iniciar · Esc para voltar")
    return lona.finalizar()


def tela_calibracao_coleta(
    largura: int,
    altura: int,
    *,
    bloco_id: str = "oi",
    indice: int = 0,
    total: int = 4,
    progresso: float = 0.63,
    amostras: int = 38,
    minimo: int = 60,
) -> Image.Image:
    """Coleta: um cartão em foco, os outros neutros, barra no rodapé."""
    lona = Lona(largura, altura)
    _cabecalho(
        lona,
        f"Bloco {indice + 1} de {total}: olhe para {board.rotulo(bloco_id)}",
        "Prancha · calibração",
        direita_texto=f"Cuidador: {amostras} de {minimo} amostras",
        direita_tamanho=13,
    )

    topo, base = 124, 66
    for bloco in board.BLOCOS:
        if bloco.id == bloco_id:
            _cartao(lona, bloco, foco=True, cor_fundo=CORES_CARTAO[bloco.id],
                    topo=topo, base=base)
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

    progresso = max(0.0, min(1.0, float(progresso)))
    x1, x2 = MARGEM, LARGURA_BASE - MARGEM
    y1, y2 = 682, 692
    lona.retangulo((x1, y1, x2, y2), misturar(CORES["fundo"], CORES["texto"], 0.12), 5)
    if progresso > 0:
        lona.retangulo((x1, y1, x1 + (x2 - x1) * progresso, y2), CORES["texto"], 5)
    return lona.finalizar()


def tela_calibracao_sucesso(largura: int, altura: int) -> Image.Image:
    """Resultado bom: qualidade e próximo passo."""
    lona = Lona(largura, altura)
    _cabecalho(lona, "Modo cuidador · Perfil Ana", "Prancha · calibração")
    _circulo_check(lona, 640, 234, 28, CORES["confirmado"])
    _centro(lona, 640, 302, "Calibração concluída", 40, CORES["texto"], "bold")
    _centro(lona, 640, 342, "Qualidade boa. A prancha já está pronta.",
            20, CORES["apoio"])

    pontos = (("OI", "60 pontos"), ("COMER", "58 pontos"),
              ("BEBER", "60 pontos"), ("BANHEIRO", "57 pontos"))
    largura_chip, gap = 170, 14
    inicio = 640 - (4 * largura_chip + 3 * gap) / 2
    for indice, (rotulo, detalhe) in enumerate(pontos):
        x1 = inicio + indice * (largura_chip + gap)
        y1, y2 = 386, 456
        lona.retangulo((x1, y1, x1 + largura_chip, y2),
                       CORES["superficie"], 16, CORES["borda"], 1)
        _centro(lona, x1 + largura_chip / 2, y1 + 24, rotulo, 16, CORES["texto"], "semibold")
        _detalhe_com_check(
            lona,
            x1 + largura_chip / 2,
            y1 + 48,
            detalhe,
            CORES["confirmado"],
        )

    _botao(lona, (432, 508, 672, 564), "Ir para a prancha", primario=True, tamanho=19)
    _botao(lona, (688, 508, 848, 564), "Refazer", primario=False, tamanho=19)
    _rodape_centro(lona, "Cuidador: Enter continua · R refaz a calibração")
    return lona.finalizar()


def tela_calibracao_fraca(largura: int, altura: int) -> Image.Image:
    """Resultado fraco: explica sem culpar e oferece refazer."""
    lona = Lona(largura, altura)
    _cabecalho(lona, "Modo cuidador · Perfil Ana", "Prancha · calibração")
    _alerta(lona, 640, 230, 28, CORES["atencao"])
    _centro(lona, 640, 294, "Os cartões ficaram muito próximos", 36,
            CORES["texto"], "bold")
    _centro(lona, 640, 334, "Vamos tentar de novo.", 20, CORES["apoio"])

    pontos = (
        ("OI", "✓ bom", CORES["confirmado"]),
        ("COMER", "! repetir", CORES["atencao"]),
        ("BEBER", "! repetir", CORES["atencao"]),
        ("BANHEIRO", "✓ bom", CORES["confirmado"]),
    )
    largura_chip, gap = 170, 14
    inicio = 640 - (4 * largura_chip + 3 * gap) / 2
    for indice, (rotulo, detalhe, cor) in enumerate(pontos):
        x1 = inicio + indice * (largura_chip + gap)
        y1, y2 = 376, 446
        lona.retangulo((x1, y1, x1 + largura_chip, y2),
                       CORES["superficie"], 16, CORES["borda"], 1)
        _centro(lona, x1 + largura_chip / 2, y1 + 24, rotulo, 16, CORES["texto"], "semibold")
        if detalhe.startswith("✓"):
            _detalhe_com_check(
                lona,
                x1 + largura_chip / 2,
                y1 + 48,
                detalhe.lstrip("✓ ").strip(),
                cor,
            )
        else:
            _centro(lona, x1 + largura_chip / 2, y1 + 48, detalhe, 14, cor)

    _centro(lona, 640, 474, "COMER e BEBER ainda estão no mesmo ponto de olhar.",
            15, CORES["apoio"])
    _botao(lona, (377, 510, 677, 566), "Refazer COMER e BEBER", primario=True, tamanho=18)
    _botao(lona, (693, 510, 903, 566), "Ajustar posição", primario=False, tamanho=18)
    _rodape_centro(lona, "Cuidador: R refaz · Esc volta")
    return lona.finalizar()


def tela_pausa(largura: int, altura: int) -> Image.Image:
    """Pausa: o olhar não seleciona nada."""
    lona = Lona(largura, altura)
    _cabecalho(lona, "Modo cuidador · Perfil Ana", "Prancha · pausa")
    _pausa_icone(lona, 640, 250, 30)
    _centro(lona, 640, 322, "Prancha em pausa", 40, CORES["texto"], "bold")
    _centro(lona, 640, 364, "O olhar não escolhe nada enquanto a pausa estiver ativa.",
            20, CORES["apoio"])
    _botao(lona, (417, 426, 617, 482), "Continuar", primario=True, tamanho=20)
    _botao(lona, (633, 426, 863, 482), "Voltar ao perfil", primario=False, tamanho=19)
    _rodape_centro(lona, "Cuidador: Enter continua · C calibra · Configurações · Sair do app")
    return lona.finalizar()


def tela_camera_ausente(largura: int, altura: int) -> Image.Image:
    """Câmera indisponível, com instruções para o cuidador."""
    lona = Lona(largura, altura)
    _cabecalho(lona, "Ana", "Prancha · comunicação pelo olhar")
    _banner(lona, "A câmera não está disponível. Peça ajuda ao cuidador.",
            icone="alerta")
    lona.retangulo((MARGEM, 158, LARGURA_BASE - MARGEM, 600),
                   CORES["superficie"], 24, CORES["borda"], 1)
    lona.texto((100, 208), "Para o cuidador", 28, CORES["texto"], "semibold", anchor="lm")

    passos = (
        "Confira se o cabo da câmera está encaixado.",
        "Feche outros programas que usam a câmera.",
        "Aguarde alguns segundos. O app tenta de novo sozinho.",
        "Se continuar, reinicie o computador.",
    )
    for indice, passo in enumerate(passos, start=1):
        y = 262 + (indice - 1) * 50
        lona.circulo((112, y), 13, cor=CORES["neutro"])
        _centro(lona, 112, y, str(indice), 13, CORES["texto"], "semibold")
        lona.texto((146, y), passo, 18, CORES["apoio"], anchor="lm")

    _botao(lona, (980, 512, 1180, 566), "Tentar agora", primario=True, tamanho=19)
    _rodape_centro(lona, "A prancha volta sozinha quando a câmera responder.")
    return lona.finalizar()


def tela_rosto_perdido(largura: int, altura: int) -> Image.Image:
    """Aviso suave: rosto fora do enquadramento, prancha continua."""
    lona = Lona(largura, altura)
    _banner(lona, "Aproxime o rosto da câmera. A prancha continua aqui.",
            icone="rosto", y1=22, y2=64)
    topo, base = 88, 50
    for bloco in BLOCOS:
        _cartao(
            lona,
            bloco,
            mostrar_icone=False,
            topo=topo,
            base=base,
        )
    _centro(lona, 640, 692, "Assim que o rosto aparecer, a prancha volta sozinha.",
            15, CORES["apoio"])
    return lona.finalizar()


def tela_cabeca_virada(largura: int, altura: int) -> Image.Image:
    """Aviso suave: cabeça muito virada, sem bloquear a prancha."""
    lona = Lona(largura, altura)
    _banner(lona, "Olhe para a tela.", icone="cabeca", y1=22, y2=64)
    topo, base = 88, 50
    for bloco in BLOCOS:
        _cartao(
            lona,
            bloco,
            mostrar_icone=False,
            topo=topo,
            base=base,
        )
    _centro(lona, 640, 692, "A prancha continua disponível.", 15, CORES["apoio"])
    return lona.finalizar()


def tela_modo_cuidador(largura: int, altura: int) -> Image.Image:
    """Área separada do cuidador: perfis, calibração e configurações."""
    lona = Lona(largura, altura)
    lona.retangulo((0, 0, 260, ALTURA_BASE), CORES["superficie"])
    lona.retangulo((259, 0, 260, ALTURA_BASE), CORES["borda"])

    _marca(lona, 32, 36)
    lona.texto((70, 48), "Prancha", 20, CORES["texto"], "semibold", anchor="lm")
    lona.texto((32, 76), "Modo cuidador", 13, CORES["apoio"], anchor="lm")

    itens = (
        ("Perfis", True),
        ("Calibração", False),
        ("Configurações", False),
        ("Diagnóstico", False),
        ("Sair", False),
    )
    y = 120
    for rotulo, ativo in itens:
        if ativo:
            lona.retangulo((20, y, 240, y + 38), CORES["neutro"], 10)
            lona.retangulo((20, y + 9, 24, y + 29), CORES["texto"], 2)
        cor = CORES["texto"] if ativo else CORES["apoio"]
        if rotulo == "Sair":
            cor = CORES["atencao"]
        lona.texto((40, y + 19), rotulo, 16, cor, "semibold" if ativo else "regular",
                   anchor="lm")
        y += 52

    lona.texto((300, 40), "Modo cuidador", 15, CORES["apoio"], anchor="lm")
    _botao(lona, (1034, 26, 1224, 66), "Voltar à prancha", primario=False, tamanho=15)
    lona.texto((300, 110), "Perfis", 36, CORES["texto"], "bold", anchor="lm")
    lona.texto((300, 152), "Escolha quem vai usar a prancha.", 18, CORES["apoio"],
               anchor="lm")
    _botao(lona, (1044, 104, 1224, 144), "Novo perfil", primario=True, tamanho=16)

    perfis = (
        ("A", "Ana", "Calibrada há 2 dias", True, None),
        ("L", "Lucas", "Calibração pendente", False, CORES["atencao"]),
    )
    for indice, (inicial, nome, status, ativo, cor_status) in enumerate(perfis):
        x1 = 300 + indice * 300
        x2 = x1 + 280
        y1, y2 = 196, 346
        lona.retangulo(
            (x1, y1, x2, y2),
            CORES["superficie"],
            20,
            CORES["texto"] if ativo else CORES["borda"],
            2.5 if ativo else 1,
        )
        lona.circulo((x1 + 44, y1 + 54), 26,
                     cor=CORES["texto"] if ativo else CORES["neutro"])
        _centro(lona, x1 + 44, y1 + 54, inicial, 22,
                CORES["branco"] if ativo else CORES["texto"], "bold")
        lona.texto((x1 + 88, y1 + 42), nome, 22, CORES["texto"], "semibold", anchor="lm")
        if ativo:
            lona.circulo((x1 + 92, y1 + 72), 4, cor=CORES["confirmado"])
            lona.texto((x1 + 104, y1 + 72), status, 14, CORES["apoio"], anchor="lm")
            _pilula(lona, x2 - 20, y1 + 20, "Ativo", tamanho=12, altura=24,
                    fundo=CORES["confirmado_fundo"], cor=CORES["confirmado"],
                    borda=CORES["confirmado_fundo"], padding=10, anchor="right")
        else:
            lona.circulo((x1 + 92, y1 + 72), 4, cor=cor_status or CORES["apoio"])
            lona.texto((x1 + 104, y1 + 72), status, 14, cor_status or CORES["apoio"],
                       anchor="lm")

    lona.retangulo((300, 376, 1224, 600), CORES["superficie"], 20, CORES["borda"], 1)
    lona.texto((332, 416), "Detalhes do perfil", 20, CORES["texto"], "semibold",
               anchor="lm")
    linhas = (
        ("Calibração da prancha", "Concluída há 2 dias"),
        ("Qualidade", "Boa"),
        ("Validade", "7 dias"),
    )
    y = 462
    for rotulo, valor in linhas:
        lona.texto((332, y), rotulo, 16, CORES["apoio"], anchor="lm")
        lona.texto((1192, y), valor, 16, CORES["texto"], "semibold", anchor="rm")
        lona.retangulo((332, y + 22, 1192, y + 23), CORES["borda"])
        y += 44

    lona.texto((300, 690), "Acesso ao modo cuidador apenas pelo teclado (F2).",
               14, CORES["apoio"], anchor="lm")
    return lona.finalizar()


# =====================================================================
# Catálogo de telas para o renderizador
# =====================================================================
TELAS: tuple[tuple[str, str, Tela], ...] = (
    ("01_boas_vindas", "Início — menu principal", tela_boas_vindas),
    ("01b_boas_vindas_recolhida", "Início — menu recolhido",
     tela_boas_vindas_recolhida),
    ("02_boas_vindas_sem_calibracao", "Início — calibração pendente",
     tela_boas_vindas_sem_calibracao),
    ("03_prancha", "Prancha — repouso", lambda w, h: tela_prancha(w, h)),
    ("04_prancha_foco", "Prancha — foco e progresso",
     lambda w, h: tela_prancha(w, h, foco="comer", progresso=0.62)),
    ("05_prancha_confirmacao", "Prancha — confirmação",
     lambda w, h: tela_prancha(w, h, confirmado="beber")),
    ("06_calibracao_intro", "Calibração — introdução", tela_calibracao_intro),
    ("07_calibracao_coleta", "Calibração — coleta",
     lambda w, h: tela_calibracao_coleta(w, h)),
    ("08_calibracao_sucesso", "Calibração — concluída", tela_calibracao_sucesso),
    ("09_calibracao_fraca", "Calibração — repetir", tela_calibracao_fraca),
    ("10_pausa", "Pausa", tela_pausa),
    ("11_camera_ausente", "Câmera indisponível", tela_camera_ausente),
    ("12_rosto_perdido", "Rosto não detectado", tela_rosto_perdido),
    ("13_cabeca_virada", "Cabeça virada", tela_cabeca_virada),
    ("14_modo_cuidador", "Modo cuidador", tela_modo_cuidador),
)
