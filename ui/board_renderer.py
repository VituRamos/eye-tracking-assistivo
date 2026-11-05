"""
Desenho da prancha de comunicação (grade de cartões estilo PECS).

Este módulo só desenha: recebe o bloco focado, o progresso do dwell e o
bloco confirmado, e pinta a tela. Toda a decisão de *qual* bloco está
focado vive em ``core/board.py``; a persistência da calibração, em
``core/board_calibration.py``.

Os pictogramas são desenhados com primitivas do OpenCV (sem assets
externos), então o executável continua sendo um único arquivo.
"""
from __future__ import annotations

import cv2
import numpy as np

from core import board

# Cores (BGR)
_FUNDO = (24, 26, 32)
_TEXTO = (255, 255, 255)
_TEXTO_SUAVE = (185, 190, 200)
_TEXTO_ESCURO = (18, 18, 18)
_DESTAQUE = (60, 240, 255)
_CONFIRMADO = (80, 220, 90)
_BARRA_FUNDO = (55, 58, 66)


# =====================================================================
# Utilitários de desenho
# =====================================================================
def _retangulo_arredondado(frame, x1, y1, x2, y2, raio, cor, espessura=-1):
    raio = max(0, min(raio, (x2 - x1) // 2, (y2 - y1) // 2))
    if raio == 0:
        cv2.rectangle(frame, (x1, y1), (x2, y2), cor, espessura)
        return

    if espessura < 0:
        cv2.rectangle(frame, (x1 + raio, y1), (x2 - raio, y2), cor, -1)
        cv2.rectangle(frame, (x1, y1 + raio), (x2, y2 - raio), cor, -1)
        for cx, cy in (
            (x1 + raio, y1 + raio), (x2 - raio, y1 + raio),
            (x1 + raio, y2 - raio), (x2 - raio, y2 - raio),
        ):
            cv2.circle(frame, (cx, cy), raio, cor, -1)
        return

    cv2.line(frame, (x1 + raio, y1), (x2 - raio, y1), cor, espessura)
    cv2.line(frame, (x1 + raio, y2), (x2 - raio, y2), cor, espessura)
    cv2.line(frame, (x1, y1 + raio), (x1, y2 - raio), cor, espessura)
    cv2.line(frame, (x2, y1 + raio), (x2, y2 - raio), cor, espessura)
    cv2.ellipse(frame, (x1 + raio, y1 + raio), (raio, raio), 0, 180, 270, cor, espessura)
    cv2.ellipse(frame, (x2 - raio, y1 + raio), (raio, raio), 0, 270, 360, cor, espessura)
    cv2.ellipse(frame, (x1 + raio, y2 - raio), (raio, raio), 0, 90, 180, cor, espessura)
    cv2.ellipse(frame, (x2 - raio, y2 - raio), (raio, raio), 0, 0, 90, cor, espessura)


def _texto_centralizado(frame, texto, cx, y, escala, cor, espessura=2,
                        fonte=cv2.FONT_HERSHEY_DUPLEX):
    (largura_texto, _), _ = cv2.getTextSize(texto, fonte, escala, espessura)
    cv2.putText(frame, texto, (cx - largura_texto // 2, y), fonte, escala, cor, espessura)


# =====================================================================
# Pictogramas (desenhados com primitivas)
# =====================================================================
def _icone_oi(frame, cx, cy, tamanho, cor):
    esp = max(3, tamanho // 18)
    palma = tamanho * 0.20
    _retangulo_arredondado(
        frame, int(cx - palma), int(cy), int(cx + palma), int(cy + tamanho * 0.36),
        int(palma * 0.55), cor, -1,
    )
    for i, deslocamento in enumerate((-0.18, -0.06, 0.06, 0.18)):
        altura = tamanho * (0.34 if i in (1, 2) else 0.28)
        x = int(cx + tamanho * deslocamento)
        cv2.line(frame, (x, int(cy + tamanho * 0.02)),
                 (x, int(cy - altura)), cor, esp)
    # Polegar
    cv2.line(frame, (int(cx - palma), int(cy + tamanho * 0.12)),
             (int(cx - tamanho * 0.34), int(cy - tamanho * 0.06)), cor, esp)
    # Pulso
    cv2.line(frame, (int(cx - palma * 0.7), int(cy + tamanho * 0.34)),
             (int(cx - palma * 0.7), int(cy + tamanho * 0.46)), cor, esp)
    cv2.line(frame, (int(cx + palma * 0.7), int(cy + tamanho * 0.34)),
             (int(cx + palma * 0.7), int(cy + tamanho * 0.46)), cor, esp)


def _icone_comer(frame, cx, cy, tamanho, cor):
    esp = max(3, tamanho // 18)
    # Prato
    cv2.ellipse(frame, (int(cx), int(cy + tamanho * 0.22)),
                (int(tamanho * 0.36), int(tamanho * 0.11)), 0, 0, 360, cor, esp)
    cv2.ellipse(frame, (int(cx), int(cy + tamanho * 0.22)),
                (int(tamanho * 0.22), int(tamanho * 0.06)), 0, 0, 360, cor, esp)
    # Garfo
    x_garfo = int(cx - tamanho * 0.24)
    cv2.line(frame, (x_garfo, int(cy - tamanho * 0.20)),
             (x_garfo, int(cy + tamanho * 0.10)), cor, esp)
    for desloc in (-0.06, 0.0, 0.06):
        cv2.line(frame, (int(x_garfo + tamanho * desloc), int(cy - tamanho * 0.36)),
                 (int(x_garfo + tamanho * desloc), int(cy - tamanho * 0.16)), cor, esp)
    # Faca
    x_faca = int(cx + tamanho * 0.24)
    cv2.line(frame, (x_faca, int(cy - tamanho * 0.20)),
             (x_faca, int(cy + tamanho * 0.10)), cor, esp)
    cv2.ellipse(frame, (int(x_faca + tamanho * 0.03), int(cy - tamanho * 0.20)),
                (int(tamanho * 0.06), int(tamanho * 0.16)), 0, 270, 90, cor, esp)


def _icone_beber(frame, cx, cy, tamanho, cor):
    esp = max(3, tamanho // 18)
    topo = int(cy - tamanho * 0.16)
    base = int(cy + tamanho * 0.34)
    pontos = [
        (int(cx - tamanho * 0.24), topo),
        (int(cx + tamanho * 0.24), topo),
        (int(cx + tamanho * 0.16), base),
        (int(cx - tamanho * 0.16), base),
    ]
    cv2.polylines(frame, [np.array(pontos, dtype="int32")], True, cor, esp)
    # Alça
    cv2.ellipse(frame, (int(cx + tamanho * 0.20), int(cy + tamanho * 0.08)),
                (int(tamanho * 0.10), int(tamanho * 0.13)), 0, -90, 90, cor, esp)
    # Canudo
    cv2.line(frame, (int(cx + tamanho * 0.06), int(cy - tamanho * 0.40)),
             (int(cx + tamanho * 0.14), int(cy - tamanho * 0.10)), cor, esp)
    # Líquido
    cv2.line(frame, (int(cx - tamanho * 0.18), int(cy + tamanho * 0.12)),
             (int(cx + tamanho * 0.18), int(cy + tamanho * 0.12)), cor, max(2, esp // 2))


def _icone_banheiro(frame, cx, cy, tamanho, cor):
    esp = max(3, tamanho // 18)
    # Caixa de descarga
    _retangulo_arredondado(
        frame, int(cx - tamanho * 0.26), int(cy - tamanho * 0.40),
        int(cx + tamanho * 0.06), int(cy - tamanho * 0.16), int(tamanho * 0.04), cor, esp,
    )
    # Vaso
    cv2.ellipse(frame, (int(cx + tamanho * 0.06), int(cy + tamanho * 0.04)),
                (int(tamanho * 0.26), int(tamanho * 0.17)), 0, 0, 360, cor, esp)
    # Base
    cv2.line(frame, (int(cx - tamanho * 0.02), int(cy + tamanho * 0.18)),
             (int(cx - tamanho * 0.06), int(cy + tamanho * 0.40)), cor, esp)
    cv2.line(frame, (int(cx + tamanho * 0.18), int(cy + tamanho * 0.18)),
             (int(cx + tamanho * 0.16), int(cy + tamanho * 0.40)), cor, esp)
    cv2.line(frame, (int(cx - tamanho * 0.10), int(cy + tamanho * 0.40)),
             (int(cx + tamanho * 0.22), int(cy + tamanho * 0.40)), cor, esp)


_ICONES = {
    "oi": _icone_oi,
    "comer": _icone_comer,
    "beber": _icone_beber,
    "banheiro": _icone_banheiro,
}


# =====================================================================
# Componentes da tela
# =====================================================================
def _fundo(frame, largura, altura):
    cv2.rectangle(frame, (0, 0), (largura, altura), _FUNDO, -1)


def _barra_progresso(frame, x1, y1, x2, y2, progresso, cor=_DESTAQUE):
    progresso = min(max(float(progresso), 0.0), 1.0)
    _retangulo_arredondado(frame, x1, y1, x2, y2, (y2 - y1) // 2, _BARRA_FUNDO, -1)
    if progresso <= 0:
        return
    largura_cheia = int((x2 - x1) * progresso)
    if largura_cheia > 2:
        _retangulo_arredondado(
            frame, x1, y1, x1 + largura_cheia, y2, (y2 - y1) // 2, cor, -1,
        )


def _desenhar_cartao(frame, bloco, largura, altura, foco: bool, confirmado: bool,
                    progresso: float):
    x1, y1, x2, y2 = board.retangulo(bloco, largura, altura)
    raio = 22

    if confirmado:
        _retangulo_arredondado(frame, x1 - 8, y1 - 8, x2 + 8, y2 + 8, raio + 8,
                               _CONFIRMADO, -1)
    elif foco:
        _retangulo_arredondado(frame, x1 - 8, y1 - 8, x2 + 8, y2 + 8, raio + 8,
                               _DESTAQUE, -1)

    _retangulo_arredondado(frame, x1, y1, x2, y2, raio, bloco.cor, -1)
    _retangulo_arredondado(frame, x1, y1, x2, y2, raio, (15, 15, 15), 4)

    # Pictograma
    cx = (x1 + x2) // 2
    cy = y1 + int((y2 - y1) * 0.44)
    tamanho = int(min(x2 - x1, y2 - y1) * 0.56)
    _ICONES[bloco.icone](frame, cx, cy, tamanho, _TEXTO_ESCURO)

    # Rótulo
    escala = 1.25 if len(bloco.rotulo) <= 6 else 1.05
    _texto_centralizado(frame, bloco.rotulo, cx, y2 - 34, escala, _TEXTO_ESCURO, 3)

    # Progresso do dwell dentro do cartão focado
    if foco and not confirmado and progresso > 0:
        _barra_progresso(
            frame, x1 + 34, y2 - 20, x2 - 34, y2 - 10, progresso, (30, 30, 30),
        )


def _cabecalho(frame, largura, confirmado_id: str | None, perfil: str | None):
    _texto_centralizado(frame, "PRANCHA DE COMUNICACAO", largura // 2, 52,
                        1.05, _TEXTO, 3)
    if confirmado_id:
        _texto_centralizado(
            frame, f"VOCE ESCOLHEU: {board.rotulo(confirmado_id)}", largura // 2,
            90, 0.9, _CONFIRMADO, 2,
        )
    elif perfil:
        _texto_centralizado(frame, f"Perfil: {perfil}", largura // 2, 90,
                            0.62, _TEXTO_SUAVE, 1)
    else:
        _texto_centralizado(frame, "Olhe para um cartao para escolher", largura // 2,
                            90, 0.62, _TEXTO_SUAVE, 1)


def _rodape(frame, largura, altura, texto: str):
    _texto_centralizado(frame, texto, largura // 2, altura - 16, 0.55,
                        _TEXTO_SUAVE, 1, cv2.FONT_HERSHEY_SIMPLEX)


def desenhar_prancha(frame, largura: int, altura: int, foco: str | None = None,
                     progresso: float = 0.0, confirmado: str | None = None,
                     perfil: str | None = None):
    """Tela da prancha no modo de uso (seleção por olhar)."""
    _fundo(frame, largura, altura)
    _cabecalho(frame, largura, confirmado, perfil)

    for bloco in board.BLOCOS:
        _desenhar_cartao(
            frame, bloco, largura, altura,
            foco=(bloco.id == foco),
            confirmado=(bloco.id == confirmado),
            progresso=progresso if bloco.id == foco else 0.0,
        )

    _rodape(frame, largura, altura,
            "[M] Voltar ao menu   |   Olhe fixo para escolher   |   Piscada tambem confirma")


def desenhar_calibracao_prancha(frame, largura: int, altura: int, bloco_id: str,
                                indice: int, total: int, progresso: float = 0.0,
                                amostras: int = 0, minimo_amostras: int = 0,
                                descartadas: int = 0, aguardando: bool = False):
    """Tela de calibração: destaca o bloco alvo e mostra o avanço da coleta."""
    _fundo(frame, largura, altura)

    _texto_centralizado(frame, "CALIBRACAO DA PRANCHA", largura // 2, 42,
                        0.95, _TEXTO, 2)
    alvo = board.rotulo(bloco_id)
    _texto_centralizado(
        frame, f"Bloco {indice + 1} de {total}: olhe fixo para o cartao {alvo}",
        largura // 2, 78, 0.68, _DESTAQUE, 2,
    )
    _barra_progresso(frame, 80, 86, largura - 80, 94, progresso, _CONFIRMADO)

    for bloco in board.BLOCOS:
        _desenhar_cartao(
            frame, bloco, largura, altura,
            foco=(bloco.id == bloco_id),
            confirmado=False,
            progresso=0.0 if aguardando else progresso,
        )

    if aguardando:
        texto = ("Aperte ESPACO para comecar a coleta   |   [M] Voltar ao menu")
    else:
        texto = (
            f"{amostras}/{minimo_amostras} amostras validas"
            f"   |   {descartadas} descartadas (piscada/pose)"
            "   |   [M] Cancelar"
        )
    _rodape(frame, largura, altura, texto)


def desenhar_prancha_concluida(frame, largura: int, altura: int, sucesso: bool,
                               referencias: dict[str, tuple[float, float]],
                               distancia_minima: float):
    """Tela final da calibração da prancha."""
    cor_fundo = (22, 62, 26) if sucesso else (68, 24, 24)
    cv2.rectangle(frame, (0, 0), (largura, altura), cor_fundo, -1)

    titulo = "PRANCHA CALIBRADA!" if sucesso else "CALIBRACAO FRACA"
    _texto_centralizado(frame, titulo, largura // 2, 80, 1.2, _TEXTO, 3)

    if sucesso:
        mensagem = "Os 4 cartoes foram calibrados e o perfil foi salvo."
        cor_mensagem = _CONFIRMADO
    else:
        mensagem = (
            "Os cartoes ficaram com pontos de olhar muito parecidos. "
            "Repita olhando bem para cada cartao."
        )
        cor_mensagem = (80, 180, 255)
    _texto_centralizado(frame, mensagem, largura // 2, 130, 0.62, cor_mensagem, 1,
                        cv2.FONT_HERSHEY_SIMPLEX)

    y = 210
    for bloco in board.BLOCOS:
        ponto = referencias.get(bloco.id)
        if ponto is None:
            texto = f"{bloco.rotulo}:  (nao coletado)"
        else:
            texto = f"{bloco.rotulo}:  x={ponto[0]:.2f}   y={ponto[1]:.2f}"
        _texto_centralizado(frame, texto, largura // 2, y, 0.68, _TEXTO, 1,
                            cv2.FONT_HERSHEY_SIMPLEX)
        y += 46

    _texto_centralizado(
        frame, f"Separacao minima entre cartoes: {distancia_minima:.3f}",
        largura // 2, y + 20, 0.58, _TEXTO_SUAVE, 1, cv2.FONT_HERSHEY_SIMPLEX,
    )
    _texto_centralizado(frame, "Aperte [ENTER] para voltar ao menu",
                        largura // 2, altura - 60, 0.7, _TEXTO, 1,
                        cv2.FONT_HERSHEY_SIMPLEX)
