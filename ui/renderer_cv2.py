"""
Camada de apresentação (novo design, tema claro).

Tudo que desenha na tela mora aqui. Nada neste arquivo calcula gaze ou
decide transição de estado -- ele só recebe números/estado já prontos e
pinta o frame. A lógica continua em ``core/`` e em ``main.py``.

As telas usam a Pillow através de ``ui/design.py``; o resultado é copiado
para o frame BGR exibido pelo OpenCV.
"""
from __future__ import annotations

import time

import cv2
import numpy as np

from core import paths

from .design import (
    ALTURA_BASE,
    CORES,
    LARGURA_BASE,
    MARGEM,
    Lona,
    alerta,
    aplicar,
    arco,
    banner,
    cabecalho,
    centro,
    circulo_check,
    desenhar_pictograma,
    linha_arredondada,
    marca,
    misturar,
    pilula,
    sobrepor,
)

# Telas completas que não mudam a cada quadro (painel SIM/NÃO, menu, etc.).
# Guardar o RGB pronto evita redesenhar texto e curvas 30 vezes por segundo.
_TELAS_ESTATICAS: dict[tuple, object] = {}
_MAXIMO_TELAS_ESTATICAS = 12


def _guardar_tela(chave: tuple, imagem) -> None:
    if len(_TELAS_ESTATICAS) >= _MAXIMO_TELAS_ESTATICAS:
        _TELAS_ESTATICAS.clear()
    _TELAS_ESTATICAS[chave] = imagem


# O gráfico temporal muda a cada quadro, mas 8 atualizações por segundo já
# parecem contínuas. Entre uma atualização e outra, recompomos a última
# imagem (barato) em vez de redesenhar centenas de pontos.
_GRAFICOS: dict[tuple, tuple[float, object]] = {}
_INTERVALO_GRAFICO = 0.15


# =====================================================================
# Frame e depuração
# =====================================================================
def preparar_frame(frame, largura: int, altura: int):
    """
    Garante um canvas no tamanho de projeto (ex.: 1280x720).

    Se a câmera entregar outra resolução, redimensiona preservando a
    proporção e adiciona barras pretas. Assim o layout (que usa
    coordenadas fixas) nunca "estoura" a tela em webcams 640x480.
    """
    altura_atual, largura_atual = frame.shape[:2]
    if (largura_atual, altura_atual) == (largura, altura):
        return frame

    escala = min(largura / largura_atual, altura / altura_atual)
    nova_largura = max(1, round(largura_atual * escala))
    nova_altura = max(1, round(altura_atual * escala))
    redimensionado = cv2.resize(frame, (nova_largura, nova_altura), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((altura, largura, 3), dtype=frame.dtype)
    x = (largura - nova_largura) // 2
    y = (altura - nova_altura) // 2
    canvas[y:y + nova_altura, x:x + nova_largura] = redimensionado
    return canvas


def extrair_roi_do_olho(frame, landmarks, indices_cantos, indices_iris, largura, altura):
    """
    Monta um recorte (ROI) da região do olho para exibição de debug,
    com um marcador verde na posição estimada da íris.
    """
    p1 = landmarks[indices_cantos[0]]
    p2 = landmarks[indices_cantos[1]]
    x1_px, y1_px = p1.x * largura, p1.y * altura
    x2_px, y2_px = p2.x * largura, p2.y * altura

    xs_iris = [landmarks[i].x * largura for i in indices_iris]
    ys_iris = [landmarks[i].y * altura for i in indices_iris]
    iris_cx = float(np.mean(xs_iris))
    iris_cy = float(np.mean(ys_iris))

    x_esq, x_dir = min(x1_px, x2_px), max(x1_px, x2_px)
    largura_olho = max(x_dir - x_esq, 1e-3)
    cy_medio = (y1_px + y2_px) / 2
    margem_y = largura_olho * 0.7
    margem_x = largura_olho * 0.2

    x1c = int(max(0, x_esq - margem_x))
    x2c = int(min(largura, x_dir + margem_x))
    y1c = int(max(0, cy_medio - margem_y))
    y2c = int(min(altura, cy_medio + margem_y))

    roi = frame[y1c:y2c, x1c:x2c].copy()
    if roi.size > 0:
        px = int(min(max(iris_cx - x1c, 0), roi.shape[1] - 1))
        py = int(min(max(iris_cy - y1c, 0), roi.shape[0] - 1))
        cv2.circle(roi, (px, py), 2, (0, 255, 0), -1)
    return roi


def desenhar_recortes_debug(frame, roi_esq, roi_dir):
    if frame.shape[0] < 110 or frame.shape[1] < 310:
        return
    if roi_esq.size > 0:
        frame[20:110, 20:160] = cv2.resize(roi_esq, (140, 90))
        cv2.rectangle(frame, (20, 20), (160, 110), (255, 255, 255), 1)
    if roi_dir.size > 0:
        frame[20:110, 170:310] = cv2.resize(roi_dir, (140, 90))
        cv2.rectangle(frame, (170, 20), (310, 110), (255, 255, 255), 1)


def desenhar_debug_gaze(frame, largura: int, altura: int, texto: str) -> None:
    """Leitura discreta de ratio_x/ratio_y no canto inferior esquerdo."""
    lona = Lona(largura, altura, fundo=None)
    largura_texto = lona.largura_texto(texto, 13) + 20
    y1, y2 = ALTURA_BASE - 68, ALTURA_BASE - 44
    lona.retangulo((12, y1, 12 + largura_texto, y2), (*CORES["superficie"], 230), 8)
    lona.texto((22, (y1 + y2) / 2), texto, 13, CORES["apoio"], anchor="lm")
    sobrepor(frame, lona.finalizar_rgba())


def desenhar_grafico_temporal(
    frame,
    hist_esq,
    hist_dir,
    media_esq,
    media_dir,
    largura_grafico,
    altura_grafico,
    x,
    y,
    tamanho_historico,
):
    """Sinal temporal da íris, em um cartão claro sobre a tela."""
    altura_frame, largura_frame = frame.shape[:2]
    chave = (
        "grafico",
        altura_frame,
        largura_frame,
        int(x),
        int(y),
        int(largura_grafico),
        int(altura_grafico),
        int(tamanho_historico),
    )
    agora = time.monotonic()
    guardado = _GRAFICOS.get(chave)
    if guardado is not None and agora - guardado[0] < _INTERVALO_GRAFICO:
        sobrepor(frame, guardado[1])
        return

    lona = Lona(largura_frame, altura_frame, fundo=None)
    k = largura_frame / LARGURA_BASE
    gx = x / k
    gy = y / k
    gw = largura_grafico / k
    gh = altura_grafico / k

    lona.retangulo((gx, gy, gx + gw, gy + gh), (*CORES["superficie"], 245), 14)
    lona.retangulo((gx, gy, gx + gw, gy + gh), None, 14, CORES["borda"], 1)
    lona.texto((gx + 12, gy + 14), "Sinal temporal (ratio_x)", 12, CORES["texto"],
               "semibold", anchor="lm")

    topo = gy + 36
    base = gy + gh - 22
    altura_util = base - topo

    def valor_para_y(v):
        v = min(max(float(v), 0.0), 1.0)
        return base - v * altura_util

    lona.linha([(gx + 12, valor_para_y(media_esq)), (gx + gw - 12, valor_para_y(media_esq))],
               CORES["confirmado"], 1)
    lona.linha([(gx + 12, valor_para_y(media_dir)), (gx + gw - 12, valor_para_y(media_dir))],
               CORES["atencao"], 1)

    def serie(historico, cor):
        pontos = list(historico)
        n = len(pontos)
        if n < 2:
            return
        caminho = []
        for i, valor in enumerate(pontos):
            px = gx + 12 + (i / max(1, tamanho_historico - 1)) * (gw - 24)
            caminho.append((px, valor_para_y(valor)))
        lona.linha(caminho, cor, 1.6)

    serie(hist_esq, CORES["texto"])
    serie(hist_dir, (196, 98, 26))

    lona.texto((gx + 12, gy + gh - 10), "olho esq.", 10, CORES["apoio"], anchor="lm")
    lona.texto((gx + 72, gy + gh - 10), "olho dir.", 10, (196, 98, 26), anchor="lm")
    imagem = lona.finalizar_rgba()
    if len(_GRAFICOS) >= 4:
        _GRAFICOS.clear()
    _GRAFICOS[chave] = (agora, imagem)
    sobrepor(frame, imagem)


# =====================================================================
# Avisos e sobreposições
# =====================================================================
def _faixa_aviso(frame, largura: int, altura: int, texto: str, *, icone: str = "alerta",
                 y1: float = 20, y2: float = 62, x1: float = 56) -> None:
    lona = Lona(largura, altura, fundo=None)
    banner(lona, texto, y1=y1, y2=y2, icone=icone, x1=x1)
    sobrepor(frame, lona.finalizar_rgba())


def desenhar_aviso_sem_rosto(frame, largura, altura):
    """Aviso suave: rosto fora do enquadramento (a prancha continua)."""
    _faixa_aviso(
        frame,
        largura,
        altura,
        "Aproxime o rosto da câmera. A prancha continua aqui.",
        icone="rosto",
        x1=240,
    )


def desenhar_aviso_cabeca(frame, largura, altura, *, deslocado: bool = False):
    """Aviso de cabeça muito virada. ``deslocado`` protege o cabeçalho da prancha."""
    _faixa_aviso(
        frame,
        largura,
        altura,
        "Olhe para a tela.",
        icone="cabeca",
        x1=240 if deslocado else 56,
    )


def desenhar_aviso(frame, largura, altura, texto):
    """Faixa de aviso temporário (ex.: calibração fraca, perfil inválido)."""
    lona = Lona(largura, altura, fundo=None)
    largura_texto = lona.largura_texto(texto, 15, "semibold") + 56
    x1 = max(12, LARGURA_BASE / 2 - largura_texto / 2)
    x2 = min(LARGURA_BASE - 12, LARGURA_BASE / 2 + largura_texto / 2)
    y1, y2 = ALTURA_BASE - 92, ALTURA_BASE - 48
    lona.retangulo((x1, y1, x2, y2), (*CORES["atencao_fundo"], 250), 14)
    lona.retangulo((x1, y1, x2, y2), None, 14, CORES["atencao"], 1.5)
    alerta(lona, x1 + 26, (y1 + y2) / 2, 9, CORES["atencao"], preenchido=True)
    lona.texto((x1 + 44, (y1 + y2) / 2), texto, 15, CORES["atencao"], "semibold", anchor="lm")
    sobrepor(frame, lona.finalizar_rgba())


def desenhar_sem_sinal(frame, largura, altura, segundos: float, backend: str = ""):
    """Tela cheia de aviso quando a câmera parou de entregar imagens."""
    lona = Lona(largura, altura)
    cabecalho(lona, "Câmera", "Comunicação pelo olhar")
    banner(lona, "A câmera não está disponível. Peça ajuda ao cuidador.",
           icone="alerta", y1=88, y2=130)

    lona.retangulo((MARGEM, 158, LARGURA_BASE - MARGEM, 600),
                   CORES["superficie"], 24, CORES["borda"], 1)
    lona.texto((100, 208), "Para o cuidador", 28, CORES["texto"], "semibold", anchor="lm")

    if segundos == float("inf"):
        detalhe = "A câmera não entregou nenhuma imagem desde a abertura."
    else:
        decorrido = "menos de 1 segundo" if segundos < 1 else f"{segundos:.0f} segundos"
        detalhe = f"Última imagem recebida há {decorrido}."
    lona.texto((100, 246), detalhe, 16, CORES["apoio"], anchor="lm")

    passos = (
        "Confira se o cabo da câmera está encaixado.",
        "Feche outros programas que usam a câmera.",
        "Aguarde alguns segundos. O app tenta de novo sozinho.",
        "Se continuar, reinicie o computador.",
    )
    for indice, passo in enumerate(passos, start=1):
        y = 306 + (indice - 1) * 50
        lona.circulo((112, y), 13, cor=CORES["neutro"])
        centro(lona, 112, y, str(indice), 13, CORES["texto"], "semibold")
        lona.texto((146, y), passo, 18, CORES["apoio"], anchor="lm")

    if backend:
        pilula(lona, LARGURA_BASE - MARGEM, 544, f"Backend: {backend}",
               tamanho=13, anchor="right")
    lona.texto((100, 544), "A prancha volta sozinha quando a câmera responder.",
               15, CORES["apoio"], anchor="lm")
    aplicar(frame, lona.finalizar())


def desenhar_selecionado(frame, largura, altura, opcao_confirmada):
    texto = f"Selecionado: {opcao_confirmada}"
    lona = Lona(largura, altura, fundo=None)
    largura_texto = lona.largura_texto(texto, 16, "semibold") + 52
    x2 = LARGURA_BASE - MARGEM
    x1 = x2 - largura_texto
    y1, y2 = 34, 76
    lona.retangulo((x1, y1, x2, y2), (*CORES["confirmado_fundo"], 250), 12)
    lona.retangulo((x1, y1, x2, y2), None, 12, CORES["confirmado"], 1.5)
    circulo_check(lona, x1 + 24, (y1 + y2) / 2, 9, CORES["confirmado"], preenchido=True)
    lona.texto((x1 + 42, (y1 + y2) / 2), texto, 16, CORES["confirmado"], "semibold",
               anchor="lm")
    sobrepor(frame, lona.finalizar_rgba())


# =====================================================================
# Menu inicial (barra lateral)
# =====================================================================
_LARGURA_MENU = 300
_Y_TOGGLE_MENU = 612


def _item_menu(
    lona: Lona,
    y: float,
    rotulo: str,
    icone: str,
    atalho: str,
    *,
    ativo: bool = False,
    cor: tuple[int, int, int] | None = None,
) -> None:
    if ativo:
        lona.retangulo((16, y, _LARGURA_MENU - 16, y + 56), CORES["neutro"], 12)
        lona.retangulo((16, y + 12, 20, y + 44), CORES["texto"], 2)
    tinta = cor or (CORES["texto"] if ativo else CORES["apoio"])
    _icone_menu(lona, icone, 44, y + 28, tinta)
    lona.texto((76, y + 28), rotulo, 19 if ativo else 18, tinta,
               "semibold" if ativo else "regular", anchor="lm")
    lona.texto((_LARGURA_MENU - 24, y + 28), atalho, 12, CORES["apoio"], anchor="rm")


def _icone_menu(
    lona: Lona,
    nome: str,
    cx: float,
    cy: float,
    cor: tuple[int, int, int],
) -> None:
    esp = 2.2
    if nome == "iniciar":
        lona.poligono([(cx - 4, cy - 7), (cx + 7, cy), (cx - 4, cy + 7)], cor=cor)
    elif nome == "perfis":
        lona.circulo((cx, cy - 4.5), 3.6, contorno=cor, largura=esp)
        arco(lona, cx, cy + 9, 7, 200, 340, cor, esp)
    elif nome == "calibracao":
        lona.circulo((cx, cy), 8, contorno=cor, largura=esp)
        lona.circulo((cx, cy), 4, contorno=cor, largura=esp)
        lona.circulo((cx, cy), 1.5, cor=cor)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            lona.linha([(cx + dx * 8, cy + dy * 8), (cx + dx * 10, cy + dy * 10)],
                       cor, esp)
    elif nome == "cuidador":
        escudo = [
            (cx, cy - 9), (cx - 7, cy - 6), (cx - 7, cy + 0.5), (cx - 4, cy + 5),
            (cx, cy + 8), (cx + 4, cy + 5), (cx + 7, cy + 0.5), (cx + 7, cy - 6),
            (cx, cy - 9),
        ]
        linha_arredondada(lona, escudo, cor, esp)
        linha_arredondada(lona, [(cx - 3, cy), (cx - 1, cy + 3), (cx + 4, cy - 3)],
                          cor, 2)
    elif nome == "configuracoes":
        for indice in range(8):
            angulo = np.deg2rad(indice * 45)
            cosseno, seno = float(np.cos(angulo)), float(np.sin(angulo))
            linha_arredondada(
                lona,
                [(cx + 5.5 * cosseno, cy + 5.5 * seno),
                 (cx + 8.5 * cosseno, cy + 8.5 * seno)],
                cor,
                esp + 0.6,
            )
        lona.circulo((cx, cy), 5.2, contorno=cor, largura=esp)
        lona.circulo((cx, cy), 1.7, cor=cor)
    elif nome == "sair":
        arco(lona, cx, cy + 1, 7.5, 300, 600, cor, esp, passos=28)
        linha_arredondada(lona, [(cx, cy - 8.5), (cx, cy - 1.5)], cor, esp)
    else:
        raise ValueError(f"Ícone de menu desconhecido: {nome!r}")


def _barra_menu(lona: Lona) -> None:
    lona.retangulo((0, 0, _LARGURA_MENU, ALTURA_BASE), CORES["superficie"])
    lona.retangulo((_LARGURA_MENU - 1, 0, _LARGURA_MENU, ALTURA_BASE), CORES["borda"])
    marca(lona, 32, 36)
    lona.texto((70, 48), "Prancha", 20, CORES["texto"], "semibold", anchor="lm")
    lona.texto((32, 80), "Comunicação pelo olhar", 13, CORES["apoio"], anchor="lm")

    y = 136
    for rotulo, icone, atalho, ativo in (
        ("Iniciar", "iniciar", "[I]", True),
        ("Perfis", "perfis", "[P]", False),
        ("Calibração", "calibracao", "[C]", False),
        ("Modo Cuidador", "cuidador", "[F2]", False),
        ("Configurações", "configuracoes", "[F3]", False),
    ):
        _item_menu(lona, y, rotulo, icone, atalho, ativo=ativo)
        y += 64

    lona.retangulo((16, y + 22, _LARGURA_MENU - 16, y + 23), CORES["borda"])
    _item_menu(lona, y + 30, "Sair", "sair", "[Q]", cor=CORES["atencao"])
    lona.texto((32, 690), "v2.1 · novo design", 12, CORES["apoio"], anchor="lm")


def desenhar_menu(
    frame,
    largura,
    altura,
    calibracao_valida,
    media_esq,
    media_dir,
    perfil=None,
    diferenca_minima=0.03,
    prancha_valida=False,
    prancha_fraca=False,
    camera_ok=True,
):
    """Tela inicial: menu lateral, ação principal e resumo do perfil."""
    lona = Lona(largura, altura)
    _barra_menu(lona)

    x0 = _LARGURA_MENU + 44
    x1 = LARGURA_BASE - MARGEM
    lona.texto((x0, 44), "Início", 14, CORES["apoio"], anchor="lm")

    texto_camera = "Câmera pronta" if camera_ok else "Sem câmera"
    largura_camera = lona.largura_texto(texto_camera, 14) + 46
    lona.retangulo((x1 - largura_camera, 26, x1, 60), CORES["superficie"], 17,
                   CORES["borda"], 1)
    lona.circulo((x1 - largura_camera + 16, 43), 5,
                 cor=CORES["confirmado"] if camera_ok else CORES["atencao"])
    lona.texto((x1 - largura_camera + 30, 43), texto_camera, 14, CORES["apoio"], anchor="lm")

    nome = perfil or "sem perfil"
    lona.texto((x0, 110), f"Olá, {nome}", 42, CORES["texto"], "bold", anchor="lm")
    lona.texto((x0, 152), "O que você quer fazer?", 20, CORES["apoio"], anchor="lm")

    if not prancha_valida:
        if prancha_fraca:
            aviso = "Calibração fraca. Pressione [C] para refazer."
        else:
            aviso = "Prancha sem calibração. Pressione [C] para calibrar."
        alerta(lona, x0 + 9, 188, 9, CORES["atencao"])
        lona.texto((x0 + 28, 188), aviso, 15, CORES["atencao"], anchor="lm")

    # Ação principal
    resumo_x = x1 - 256
    cartao_fim = resumo_x - 24
    lona.retangulo((x0, 214, cartao_fim, 520), CORES["texto"], 30)
    desenhar_pictograma(lona, "oi", x0 + 110, 367, 150, CORES["fundo"])
    lona.texto((x0 + 216, 340), "Iniciar", 54, CORES["fundo"], "bold", anchor="lm")
    subtitulo = (
        "Abrir a prancha de comunicação"
        if prancha_valida
        else "Calibre a prancha para começar"
    )
    lona.texto((x0 + 218, 386), subtitulo, 18, (207, 203, 194), anchor="lm")
    linha_arredondada(
        lona,
        [(cartao_fim - 60, 347), (cartao_fim - 40, 367), (cartao_fim - 60, 387)],
        (207, 203, 194),
        4,
    )

    # Resumo do perfil
    lona.retangulo((resumo_x, 214, x1, 520), CORES["superficie"], 22, CORES["borda"], 1)
    lona.texto((resumo_x + 24, 248), "Perfil ativo", 13, CORES["apoio"], anchor="lm")
    lona.texto((resumo_x + 24, 278), perfil or "Nenhum", 26, CORES["texto"],
               "semibold", anchor="lm")
    lona.retangulo((resumo_x + 24, 304, x1 - 24, 305), CORES["borda"])

    if prancha_valida:
        estado_prancha = ("Concluída", CORES["confirmado"])
    elif prancha_fraca:
        estado_prancha = ("Fraca", CORES["atencao"])
    else:
        estado_prancha = ("Pendente", CORES["atencao"])
    estado_sim = (
        ("Calibrado", CORES["confirmado"])
        if calibracao_valida
        else ("Pendente", CORES["atencao"])
    )

    linhas = (
        ("Prancha", *estado_prancha),
        ("SIM / NÃO", *estado_sim),
        ("Câmera", "Pronta" if camera_ok else "Sem sinal",
         CORES["confirmado"] if camera_ok else CORES["atencao"]),
        ("Dwell", "0,7 s", CORES["texto"]),
    )
    y = 328
    for rotulo, valor, cor in linhas:
        lona.texto((resumo_x + 24, y), rotulo, 13, CORES["apoio"], anchor="lm")
        lona.texto((resumo_x + 24, y + 24), valor, 15, cor, "semibold", anchor="lm")
        y += 54

    centro(lona, (x0 + x1) / 2, 690,
           "Use as teclas indicadas para escolher uma opção.", 14, CORES["apoio"])
    aplicar(frame, lona.finalizar())


# =====================================================================
# Perfis
# =====================================================================
def desenhar_selecao_perfil(frame, largura, altura, perfis: list[str],
                            perfil_ativo: str | None = None):
    lona = Lona(largura, altura)
    cabecalho(lona, "Perfis", "Escolha quem vai usar a prancha")
    pilula(lona, LARGURA_BASE - MARGEM, 92, "[N] Novo perfil", tamanho=14,
           anchor="right", fundo=CORES["texto"], cor=CORES["fundo"],
           borda=CORES["texto"], peso="semibold")

    if not perfis:
        lona.retangulo((MARGEM, 150, LARGURA_BASE - MARGEM, 300),
                       CORES["superficie"], 20, CORES["borda"], 1)
        centro(lona, LARGURA_BASE / 2, 205, "Nenhum perfil salvo ainda.", 24,
               CORES["texto"], "semibold")
        centro(lona, LARGURA_BASE / 2, 242,
               "Pressione [N] para criar o primeiro perfil.", 16, CORES["apoio"])
    else:
        y = 150
        for indice, nome in enumerate(perfis[:9]):
            ativo = nome == perfil_ativo
            lona.retangulo((MARGEM, y, LARGURA_BASE - MARGEM, y + 64),
                           CORES["superficie"], 16,
                           CORES["texto"] if ativo else CORES["borda"],
                           2 if ativo else 1)
            lona.circulo((MARGEM + 40, y + 32), 20,
                         cor=CORES["texto"] if ativo else CORES["neutro"])
            centro(lona, MARGEM + 40, y + 32, nome[:1].upper(), 18,
                   CORES["branco"] if ativo else CORES["texto"], "bold")
            lona.texto((MARGEM + 76, y + 32), nome, 20, CORES["texto"],
                       "semibold", anchor="lm")
            if ativo:
                pilula(lona, LARGURA_BASE - MARGEM - 68, y + 20, "Ativo", tamanho=12,
                       altura=24, fundo=CORES["confirmado_fundo"],
                       cor=CORES["confirmado"], borda=CORES["confirmado_fundo"],
                       padding=10, anchor="right")
            lona.texto((LARGURA_BASE - MARGEM - 20, y + 32), f"[{indice + 1}]", 14,
                       CORES["apoio"], anchor="rm")
            y += 76
        if len(perfis) > 9:
            lona.texto((MARGEM, y + 10),
                       f"(mostrando 9 de {len(perfis)} perfis)", 14, CORES["apoio"],
                       anchor="lm")

    lona.texto((MARGEM, 700), "[M] Voltar ao menu · [N] Novo perfil", 15,
               CORES["apoio"], anchor="lm")
    lona.texto((LARGURA_BASE - MARGEM, 700),
               f"[1]–[{min(9, max(1, len(perfis)))}] escolher perfil", 15,
               CORES["apoio"], anchor="rm")
    aplicar(frame, lona.finalizar())


def desenhar_novo_perfil(frame, largura, altura, nome_digitado: str):
    lona = Lona(largura, altura)
    cabecalho(lona, "Novo perfil", "Modo cuidador")
    centro(lona, LARGURA_BASE / 2, 170, "Como devemos chamar este perfil?", 34,
           CORES["texto"], "bold")
    centro(lona, LARGURA_BASE / 2, 210,
           "Depois de criar, a calibração da prancha começa.", 18, CORES["apoio"])

    cx = LARGURA_BASE / 2
    lona.circulo((cx, 292), 30, cor=CORES["texto"])
    inicial = nome_digitado[:1].upper() if nome_digitado else "?"
    centro(lona, cx, 292, inicial, 26, CORES["branco"], "bold")

    lona.retangulo((cx - 250, 350, cx + 250, 422), CORES["superficie"], 16,
                   CORES["texto"], 2)
    lona.texto((cx - 232, 386), f"{nome_digitado}_", 30, CORES["texto"], "semibold",
               anchor="lm")
    lona.texto((cx - 250, 448),
               "Letras, números, '_' ou '-'. Máximo de 20 caracteres.", 14,
               CORES["apoio"], anchor="lm")
    lona.texto((cx, 700), "[ENTER] Confirmar e calibrar · [ESC] Cancelar", 15,
               CORES["apoio"], anchor="mm")
    aplicar(frame, lona.finalizar())


# =====================================================================
# SIM / NÃO (legado) e calibração de gaze
# =====================================================================
def _painel_sim_nao(lona: Lona, metade_x: float, ativo_sim: bool) -> None:
    lona.retangulo((0, 0, metade_x, ALTURA_BASE), CORES["confirmado_fundo"])
    lona.retangulo((metade_x, 0, LARGURA_BASE, ALTURA_BASE), CORES["atencao_fundo"])
    cor_esq = CORES["confirmado"] if ativo_sim else misturar(CORES["confirmado"], CORES["fundo"], 0.55)
    cor_dir = CORES["atencao"] if not ativo_sim else misturar(CORES["atencao"], CORES["fundo"], 0.55)
    centro(lona, metade_x / 2, ALTURA_BASE * 0.44, "SIM", 110, cor_esq, "bold")
    centro(lona, metade_x + metade_x / 2, ALTURA_BASE * 0.44, "NÃO", 110, cor_dir, "bold")
    if ativo_sim:
        centro(lona, metade_x / 2, ALTURA_BASE * 0.44 + 92,
               "olhe para este lado", 18, CORES["apoio"])
    else:
        centro(lona, metade_x + metade_x / 2, ALTURA_BASE * 0.44 + 92,
               "olhe para este lado", 18, CORES["apoio"])
    lona.retangulo((metade_x - 1, 0, metade_x + 1, ALTURA_BASE), CORES["borda"])


def desenhar_painel_sim_nao(
    frame,
    largura,
    altura,
    metade_x,
    ativo_sim: bool,
    *,
    dica: str | None = "[M] Voltar ao menu",
):
    """Painel claro SIM/NÃO, com o lado ativo destacado."""
    chave = ("painel_sim_nao", int(largura), int(altura), int(metade_x),
             bool(ativo_sim), dica or "")
    imagem = _TELAS_ESTATICAS.get(chave)
    if imagem is None:
        lona = Lona(largura, altura)
        _painel_sim_nao(lona, metade_x * LARGURA_BASE / largura, bool(ativo_sim))

        if dica:
            largura_dica = lona.largura_texto(dica, 13) + 28
            lona.retangulo(
                (12, 70, 12 + largura_dica, 102),
                (*CORES["superficie"], 235),
                10,
                CORES["borda"],
                1,
            )
            lona.texto((26, 86), dica, 13, CORES["apoio"], anchor="lm")

        imagem = lona.finalizar()
        _guardar_tela(chave, imagem)

    aplicar(frame, imagem)


def desenhar_calibracao_sim_nao(
    frame,
    largura,
    altura,
    *,
    alvo: str,
    coletando: bool,
    progresso: float,
    amostras: int,
    minimo: int,
    descartadas: int,
    media_esq: float,
    media_dir: float,
    historico_esq,
    historico_dir,
    tamanho_historico: int,
    perfil: str | None,
):
    """Tela completa da calibração SIM/NÃO (legado), no novo design."""
    lona = Lona(largura, altura)
    ativo_sim = alvo == "SIM"
    _painel_sim_nao(lona, LARGURA_BASE / 2, ativo_sim)

    cabecalho(
        lona,
        "Calibração SIM/NÃO",
        f"Perfil: {perfil or 'padrão'} · modo legado",
        direita_texto=f"Olhe para {alvo}",
        direita_peso="semibold",
    )

    if coletando:
        lona.retangulo((MARGEM, 86, LARGURA_BASE - MARGEM, 96),
                       misturar(CORES["fundo"], CORES["texto"], 0.14), 5)
        if progresso > 0:
            lona.retangulo(
                (MARGEM, 86, MARGEM + (LARGURA_BASE - 2 * MARGEM) * progresso, 96),
                CORES["texto"],
                5,
            )
        centro(lona, LARGURA_BASE / 2, 122,
               f"{amostras}/{minimo} amostras válidas · {descartadas} descartadas",
               15, CORES["apoio"])
        lona.texto((MARGEM, 700), "[M] Cancelar calibração", 15, CORES["apoio"],
                   anchor="lm")
    else:
        centro(lona, LARGURA_BASE / 2, 104,
               f"Posicione o olhar fixo para o lado {alvo}.", 18, CORES["apoio"])
        centro(lona, LARGURA_BASE / 2, 700,
               "Aperte ESPAÇO para começar a coleta · [M] Voltar ao menu", 15,
               CORES["apoio"])
        lona.texto((MARGEM, 700), f"SIM {media_esq:.2f} · NÃO {media_dir:.2f}", 14,
                   CORES["apoio"], anchor="lm")

    aplicar(frame, lona.finalizar())

    if coletando:
        escala = largura / LARGURA_BASE
        desenhar_grafico_temporal(
            frame,
            historico_esq,
            historico_dir,
            media_esq,
            media_dir,
            round(280 * escala),
            round(150 * escala),
            largura - round(300 * escala),
            altura - round(170 * escala),
            tamanho_historico,
        )


def desenhar_progresso_sim_nao(frame, largura, altura, opcao: str, progresso: float):
    """Barra de progresso do dwell no modo SIM/NÃO."""
    progresso = max(0.0, min(1.0, float(progresso)))
    lona = Lona(largura, altura, fundo=None)
    y1, y2 = ALTURA_BASE - 24, ALTURA_BASE - 12
    largura_barra = LARGURA_BASE / 2 - 2 * MARGEM
    if opcao == "SIM":
        x1 = MARGEM
        cor = CORES["confirmado"]
    else:
        x1 = LARGURA_BASE - MARGEM - largura_barra
        cor = CORES["atencao"]
    lona.retangulo((x1, y1, x1 + largura_barra, y2),
                   (*misturar(cor, CORES["fundo"], 0.75), 240), 6)
    if progresso > 0:
        lona.retangulo((x1, y1, x1 + largura_barra * progresso, y2), cor, 6)
    sobrepor(frame, lona.finalizar_rgba())


def desenhar_calibracao_concluida(frame, largura, altura, sucesso, media_esq,
                                  media_dir, diferenca):
    lona = Lona(largura, altura)
    cabecalho(lona, "Calibração SIM/NÃO", "Modo legado")

    if sucesso:
        circulo_check(lona, LARGURA_BASE / 2, 220, 28, CORES["confirmado"])
        centro(lona, LARGURA_BASE / 2, 288, "Calibração concluída", 40,
               CORES["texto"], "bold")
        centro(lona, LARGURA_BASE / 2, 328, "Perfil salvo. O modo SIM/NÃO está pronto.",
               20, CORES["apoio"])
    else:
        alerta(lona, LARGURA_BASE / 2, 220, 28, CORES["atencao"])
        centro(lona, LARGURA_BASE / 2, 288, "Calibração fraca", 40, CORES["texto"], "bold")
        centro(lona, LARGURA_BASE / 2, 328,
               "Repita olhando mais para os cantos da tela.", 20, CORES["apoio"])

    lona.retangulo((LARGURA_BASE / 2 - 280, 380, LARGURA_BASE / 2 + 280, 470),
                   CORES["superficie"], 18, CORES["borda"], 1)
    valores = (
        ("SIM", f"{media_esq:.2f}", CORES["confirmado"]),
        ("NÃO", f"{media_dir:.2f}", CORES["atencao"]),
        ("Separação", f"{diferenca:.3f}",
         CORES["confirmado"] if sucesso else CORES["atencao"]),
    )
    for indice, (rotulo, valor, cor) in enumerate(valores):
        x = LARGURA_BASE / 2 - 280 + 187 * indice + 93
        centro(lona, x, 408, rotulo, 14, CORES["apoio"])
        centro(lona, x, 440, valor, 24, cor, "semibold")

    centro(lona, LARGURA_BASE / 2, 560,
           "Aperte [ENTER] para voltar ao menu", 16, CORES["texto"], "semibold")
    aplicar(frame, lona.finalizar())


# =====================================================================
# Modo cuidador e configurações
# =====================================================================
def _cartao_status(
    lona: Lona,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    titulo: str,
    valor: str,
    cor: tuple[int, int, int],
) -> None:
    lona.retangulo((x1, y1, x2, y2), CORES["superficie"], 18, CORES["borda"], 1)
    lona.texto((x1 + 24, y1 + 34), titulo, 13, CORES["apoio"], anchor="lm")
    lona.texto((x1 + 24, y1 + 68), valor, 22, cor, "semibold", anchor="lm")


def desenhar_modo_cuidador(
    frame,
    largura: int,
    altura: int,
    *,
    perfil: str | None,
    prancha_valida: bool,
    prancha_fraca: bool,
    calibracao_valida: bool,
    camera_ok: bool,
    versao: str = "2.2",
):
    lona = Lona(largura, altura)
    cabecalho(lona, "Modo cuidador", f"Prancha · v{versao}")

    centro(lona, LARGURA_BASE / 2, 170, "Acompanhe e ajuste o uso", 34,
           CORES["texto"], "bold")
    centro(lona, LARGURA_BASE / 2, 208,
           "Esta área é só do cuidador. O usuário continua na prancha.", 17,
           CORES["apoio"])

    if prancha_valida:
        estado_prancha, cor_prancha = "Calibrada", CORES["confirmado"]
    elif prancha_fraca:
        estado_prancha, cor_prancha = "Fraca", CORES["atencao"]
    else:
        estado_prancha, cor_prancha = "Pendente", CORES["atencao"]

    cartoes = (
        ("Perfil ativo", perfil or "Nenhum", CORES["texto"]),
        ("Prancha", estado_prancha, cor_prancha),
        ("SIM / NÃO", "Calibrado" if calibracao_valida else "Pendente",
         CORES["confirmado"] if calibracao_valida else CORES["atencao"]),
        ("Câmera", "Pronta" if camera_ok else "Sem sinal",
         CORES["confirmado"] if camera_ok else CORES["atencao"]),
    )
    largura_cartao, gap = 270, 18
    inicio = LARGURA_BASE / 2 - (4 * largura_cartao + 3 * gap) / 2
    for indice, (titulo, valor, cor) in enumerate(cartoes):
        x1 = inicio + indice * (largura_cartao + gap)
        _cartao_status(lona, x1, 250, x1 + largura_cartao, 350, titulo, valor, cor)

    lona.retangulo((MARGEM, 392, LARGURA_BASE / 2 - 12, 606),
                   CORES["superficie"], 20, CORES["borda"], 1)
    lona.texto((MARGEM + 28, 430), "O que você pode fazer", 20, CORES["texto"],
               "semibold", anchor="lm")
    acoes = (
        ("[P]", "Escolher ou criar perfil"),
        ("[C]", "Calibrar a prancha (4 blocos)"),
        ("[V]", "Calibrar SIM/NÃO (legado)"),
        ("[F3]", "Ver configurações atuais"),
    )
    y = 472
    for tecla, descricao in acoes:
        pilula(lona, MARGEM + 28, y - 14, tecla, tamanho=13, altura=28,
               fundo=CORES["neutro"], cor=CORES["texto"], borda=CORES["neutro"],
               padding=10, peso="semibold")
        lona.texto((MARGEM + 100, y), descricao, 17, CORES["apoio"], anchor="lm")
        y += 34

    lona.retangulo((LARGURA_BASE / 2 + 12, 392, LARGURA_BASE - MARGEM, 606),
                   CORES["superficie"], 20, CORES["borda"], 1)
    lona.texto((LARGURA_BASE / 2 + 40, 430), "Como a prancha funciona", 20,
               CORES["texto"], "semibold", anchor="lm")
    explicacao = (
        "O usuário escolhe um cartão mantendo o olhar fixo.",
        "A piscada também confirma, se estiver habilitada.",
        "Os ajustes de tempo ficam em config/settings.yaml.",
    )
    y = 474
    for linha in explicacao:
        lona.circulo((LARGURA_BASE / 2 + 48, y), 3, cor=CORES["apoio"])
        lona.texto((LARGURA_BASE / 2 + 62, y), linha, 16, CORES["apoio"], anchor="lm")
        y += 36

    centro(lona, LARGURA_BASE / 2, 670, "[F2] ou [ESC] voltar ao menu",
           15, CORES["apoio"])
    aplicar(frame, lona.finalizar())


def desenhar_configuracoes(
    frame,
    largura: int,
    altura: int,
    cfg: dict,
    perfil: str | None,
    versao: str = "2.2",
):
    """Resumo somente leitura das configurações ativas."""
    lona = Lona(largura, altura)
    cabecalho(lona, "Configurações", f"Prancha · v{versao} · somente leitura")

    det = cfg.get("deteccao", {})
    piscada = det.get("piscada", {})
    calib = cfg.get("calibracao", {})
    cam = cfg.get("camera", {})
    perfis_cfg = cfg.get("perfis", {})

    colunas = (
        (
            "Detecção",
            (
                ("Olhar fixo (dwell)", f"{det.get('dwell_ms', 0)} ms"),
                ("Tolerância de perda", f"{det.get('tolerancia_perda_ms', 0)} ms"),
                ("Confirmação na tela", f"{det.get('exibicao_confirmacao_ms', 0)} ms"),
                ("Piscada", "Ativada" if piscada.get("habilitada") else "Desativada"),
            ),
        ),
        (
            "Calibração",
            (
                ("Duração por lado", f"{calib.get('duracao_ms', 0)} ms"),
                ("Amostras mínimas", str(calib.get("min_amostras", 0))),
                ("Yaw máximo", f"{calib.get('max_yaw_graus', 0)}°"),
                ("Separação mínima", f"{calib.get('diferenca_minima', 0)}"),
            ),
        ),
        (
            "Câmera e perfis",
            (
                ("Índice da câmera", str(cam.get("indice", 0))),
                ("Resolução", f"{cam.get('largura', 0)}x{cam.get('altura', 0)}"),
                ("FPS", str(cam.get("fps", 0))),
                ("Validade do perfil", f"{perfis_cfg.get('validade_dias', 0)} dias"),
            ),
        ),
    )

    largura_coluna, gap = 370, 19
    inicio = LARGURA_BASE / 2 - (3 * largura_coluna + 2 * gap) / 2
    for indice, (titulo, itens) in enumerate(colunas):
        x1 = inicio + indice * (largura_coluna + gap)
        x2 = x1 + largura_coluna
        lona.retangulo((x1, 160, x2, 520), CORES["superficie"], 20, CORES["borda"], 1)
        lona.texto((x1 + 24, 200), titulo, 20, CORES["texto"], "semibold", anchor="lm")
        y = 246
        for rotulo, valor in itens:
            lona.texto((x1 + 24, y), rotulo, 14, CORES["apoio"], anchor="lm")
            lona.texto((x2 - 24, y), valor, 15, CORES["texto"], "semibold", anchor="rm")
            lona.retangulo((x1 + 24, y + 18, x2 - 24, y + 19), CORES["borda"])
            y += 58

    lona.retangulo((MARGEM, 544, LARGURA_BASE - MARGEM, 612), CORES["neutro"], 16)
    lona.texto((MARGEM + 24, 578),
               "Para alterar tempos ou câmera, edite config/settings.yaml e reabra o app.",
               16, CORES["texto"], anchor="lm")
    pilula(lona, LARGURA_BASE - MARGEM, 556, f"Perfil: {perfil or 'padrão'}",
           tamanho=13, anchor="right")
    centro(lona, LARGURA_BASE / 2, 670, "[F3] ou [ESC] voltar ao menu",
           15, CORES["apoio"])
    aplicar(frame, lona.finalizar())


# =====================================================================
# Utilitário (mantido para testes/diagnóstico)
# =====================================================================
def caminho_das_configuracoes() -> str:
    return str(paths.resolver_recurso("config/settings.yaml"))


__all__ = [
    "desenhar_aviso",
    "desenhar_aviso_cabeca",
    "desenhar_aviso_sem_rosto",
    "desenhar_calibracao_concluida",
    "desenhar_calibracao_sim_nao",
    "desenhar_configuracoes",
    "desenhar_debug_gaze",
    "desenhar_grafico_temporal",
    "desenhar_menu",
    "desenhar_modo_cuidador",
    "desenhar_novo_perfil",
    "desenhar_painel_sim_nao",
    "desenhar_progresso_sim_nao",
    "desenhar_recortes_debug",
    "desenhar_selecao_perfil",
    "desenhar_selecionado",
    "desenhar_sem_sinal",
    "extrair_roi_do_olho",
    "preparar_frame",
]
