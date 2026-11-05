"""Testes de fumaça do desenho da prancha (sem câmera/MediaPipe)."""
import numpy as np

from ui import board_renderer as br

LARGURA, ALTURA = 1280, 720


def _quadro():
    return np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)


def _foi_desenhado(frame) -> bool:
    return int(frame.sum()) > 0


def test_prancha_em_uso_desenha_a_tela():
    frame = _quadro()
    br.desenhar_prancha(
        frame, LARGURA, ALTURA, foco="comer", progresso=0.5, perfil="maria",
    )
    assert frame.shape == (ALTURA, LARGURA, 3)
    assert _foi_desenhado(frame)


def test_prancha_com_confirmacao_desenha_a_tela():
    frame = _quadro()
    br.desenhar_prancha(
        frame, LARGURA, ALTURA, confirmado="banheiro", perfil="maria",
    )
    assert _foi_desenhado(frame)


def test_calibracao_aguardando_desenha_a_tela():
    frame = _quadro()
    br.desenhar_calibracao_prancha(
        frame, LARGURA, ALTURA, "beber", 2, 4, aguardando=True,
    )
    assert _foi_desenhado(frame)


def test_calibracao_coletando_desenha_a_tela():
    frame = _quadro()
    br.desenhar_calibracao_prancha(
        frame, LARGURA, ALTURA, "beber", 2, 4,
        progresso=0.6, amostras=18, minimo_amostras=30, descartadas=2,
    )
    assert _foi_desenhado(frame)


def test_conclusao_com_sucesso_e_com_falha():
    referencias = {
        "oi": (0.28, 0.31),
        "comer": (0.72, 0.30),
        "beber": (0.29, 0.71),
        "banheiro": (0.71, 0.70),
    }
    for sucesso in (True, False):
        frame = _quadro()
        br.desenhar_prancha_concluida(
            frame, LARGURA, ALTURA, sucesso, referencias, 0.40,
        )
        assert _foi_desenhado(frame)
