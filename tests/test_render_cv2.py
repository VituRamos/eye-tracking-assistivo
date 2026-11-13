"""Testes de fumaça do novo design e das telas de produção (sem câmera)."""
from collections import deque

import numpy as np
import pytest

from config.loader import carregar_config
from ui import board_renderer as prancha
from ui import design
from ui import renderer_cv2 as ui

LARGURA, ALTURA = 1280, 720


def _quadro():
    return np.zeros((ALTURA, LARGURA, 3), dtype=np.uint8)


def _foi_desenhado(frame) -> bool:
    return int(frame.sum()) > 0


def _historico(inicio: float, passo: float) -> deque:
    return deque([inicio + passo * i for i in range(120)], maxlen=200)


# =====================================================================
# Design
# =====================================================================
def test_lona_finaliza_no_tamanho_pedido():
    lona = design.Lona(LARGURA, ALTURA)
    lona.retangulo((10, 10, 100, 100), design.CORES["texto"], 12)
    lona.texto((20, 60), "Olá", 24, design.CORES["texto"], "semibold")
    imagem = lona.finalizar()
    assert imagem.size == (LARGURA, ALTURA)
    assert imagem.mode == "RGB"


def test_lona_com_fundo_transparente_mantem_alfa():
    lona = design.Lona(LARGURA, ALTURA, fundo=None)
    lona.retangulo((100, 100, 200, 200), design.CORES["atencao"], 10)
    imagem = lona.finalizar_rgba()
    assert imagem.mode == "RGBA"
    assert imagem.getbbox() is not None


@pytest.mark.parametrize("nome", design.PICTOGRAMAS)
def test_pictogramas_svg_sao_lidos_e_rasterizados(nome):
    desenho = design._desenho(nome)
    assert desenho.caminhos
    mascara = design.renderizar_mascara(desenho, 64)
    assert mascara.size == (64, 64)
    assert mascara.getbbox() is not None


def test_pictograma_desconhecido_falha():
    with pytest.raises(KeyError):
        design.caminho_do_pictograma("inexistente")


def test_sobrepor_compoe_apenas_a_regiao_desenhada():
    frame = _quadro()
    frame[:] = 10
    lona = design.Lona(LARGURA, ALTURA, fundo=None)
    lona.retangulo((40, 40, 140, 90), design.CORES["confirmado"], 8)
    design.sobrepor(frame, lona.finalizar_rgba())

    assert tuple(frame[60, 80]) == design.CORES["confirmado"][::-1]
    assert tuple(frame[300, 600]) == (10, 10, 10)


# =====================================================================
# Menu e perfis
# =====================================================================
def test_menu_desenha_a_tela():
    frame = _quadro()
    ui.desenhar_menu(frame, LARGURA, ALTURA, True, 0.31, 0.71, "Ana", 0.03,
                     prancha_valida=True, camera_ok=True)
    assert frame.shape == (ALTURA, LARGURA, 3)
    assert _foi_desenhado(frame)


def test_menu_sem_camera_e_sem_calibracao_nao_quebra():
    frame = _quadro()
    ui.desenhar_menu(frame, LARGURA, ALTURA, False, 0.5, 0.5, None, 0.03,
                     prancha_valida=False, prancha_fraca=True, camera_ok=False)
    assert _foi_desenhado(frame)


def test_selecao_de_perfis_lista_e_vazio():
    for perfis in (["Ana", "Bruno"], []):
        frame = _quadro()
        ui.desenhar_selecao_perfil(frame, LARGURA, ALTURA, perfis, "Ana")
        assert _foi_desenhado(frame)


def test_novo_perfil_desenha_o_nome_digitado():
    frame = _quadro()
    ui.desenhar_novo_perfil(frame, LARGURA, ALTURA, "Ana")
    assert _foi_desenhado(frame)


# =====================================================================
# SIM / NÃO e calibração
# =====================================================================
@pytest.mark.parametrize("ativo_sim", [True, False])
def test_painel_sim_nao_muda_o_lado_ativo(ativo_sim):
    frame = _quadro()
    ui.desenhar_painel_sim_nao(frame, LARGURA, ALTURA, LARGURA // 2, ativo_sim)
    assert _foi_desenhado(frame)


def test_painel_sim_nao_reaproveita_a_tela_em_cache():
    frame = _quadro()
    ui.desenhar_painel_sim_nao(frame, LARGURA, ALTURA, LARGURA // 2, True)
    primeiro = frame.copy()
    segundo = _quadro()
    ui.desenhar_painel_sim_nao(segundo, LARGURA, ALTURA, LARGURA // 2, True)
    assert np.array_equal(primeiro, segundo)


def test_calibracao_sim_nao_preparar_e_coletando():
    hist_esq = _historico(0.3, 0.001)
    hist_dir = _historico(0.7, -0.001)
    for coletando in (False, True):
        frame = _quadro()
        ui.desenhar_calibracao_sim_nao(
            frame, LARGURA, ALTURA,
            alvo="SIM",
            coletando=coletando,
            progresso=0.5 if coletando else 0.0,
            amostras=20 if coletando else 0,
            minimo=40,
            descartadas=2,
            media_esq=0.31,
            media_dir=0.71,
            historico_esq=hist_esq,
            historico_dir=hist_dir,
            tamanho_historico=200,
            perfil="Ana",
        )
        assert _foi_desenhado(frame)


@pytest.mark.parametrize("sucesso", [True, False])
def test_calibracao_sim_nao_concluida(sucesso):
    frame = _quadro()
    ui.desenhar_calibracao_concluida(
        frame, LARGURA, ALTURA, sucesso, 0.31, 0.71, 0.40,
    )
    assert _foi_desenhado(frame)


def test_barra_de_progresso_sim_nao():
    for opcao in ("SIM", "NAO"):
        frame = _quadro()
        ui.desenhar_progresso_sim_nao(frame, LARGURA, ALTURA, opcao, 0.62)
        assert _foi_desenhado(frame)


def test_grafico_temporal_e_debug_gaze():
    frame = _quadro()
    ui.desenhar_grafico_temporal(
        frame,
        _historico(0.3, 0.001),
        _historico(0.7, -0.001),
        0.31, 0.71, 280, 160, LARGURA - 300, ALTURA - 200, 200,
    )
    ui.desenhar_debug_gaze(frame, LARGURA, ALTURA, "esq:0.31 dir:0.71")
    assert _foi_desenhado(frame)


# =====================================================================
# Prancha
# =====================================================================
@pytest.mark.parametrize("confirmado", [None, "banheiro"])
def test_prancha_em_uso(confirmado):
    frame = _quadro()
    prancha.desenhar_prancha(
        frame, LARGURA, ALTURA,
        foco=None if confirmado else "comer",
        progresso=0.0 if confirmado else 0.55,
        confirmado=confirmado,
        perfil="Ana",
    )
    assert _foi_desenhado(frame)


def test_prancha_calibracao_aguardando_e_coletando():
    for aguardando in (True, False):
        frame = _quadro()
        prancha.desenhar_calibracao_prancha(
            frame, LARGURA, ALTURA, "beber", 1, 4,
            progresso=0.0 if aguardando else 0.45,
            amostras=0 if aguardando else 18,
            minimo_amostras=40,
            descartadas=0 if aguardando else 2,
            aguardando=aguardando,
        )
        assert _foi_desenhado(frame)


def test_prancha_calibracao_concluida_sucesso_e_fraca():
    referencias = {
        "oi": (0.21, 0.22),
        "comer": (0.78, 0.24),
        "beber": (0.22, 0.78),
        "banheiro": (0.79, 0.77),
    }
    for sucesso in (True, False):
        frame = _quadro()
        prancha.desenhar_prancha_concluida(
            frame, LARGURA, ALTURA, sucesso, referencias, 0.31,
        )
        assert _foi_desenhado(frame)


# =====================================================================
# Modo cuidador, configurações e avisos
# =====================================================================
def test_modo_cuidador_desenha_a_tela():
    frame = _quadro()
    ui.desenhar_modo_cuidador(
        frame, LARGURA, ALTURA,
        perfil="Ana", prancha_valida=True, prancha_fraca=False,
        calibracao_valida=True, camera_ok=True,
    )
    assert _foi_desenhado(frame)


def test_configuracoes_refletem_o_yaml():
    frame = _quadro()
    ui.desenhar_configuracoes(frame, LARGURA, ALTURA, carregar_config(), "Ana")
    assert _foi_desenhado(frame)


def test_avisos_e_tela_sem_camera():
    for desenhar in (
        ui.desenhar_aviso_sem_rosto,
        ui.desenhar_aviso_cabeca,
    ):
        frame = _quadro()
        desenhar(frame, LARGURA, ALTURA)
        assert _foi_desenhado(frame)

    frame = _quadro()
    ui.desenhar_aviso(frame, LARGURA, ALTURA, "Mensagem de teste")
    assert _foi_desenhado(frame)

    frame = _quadro()
    ui.desenhar_sem_sinal(frame, LARGURA, ALTURA, 12.0, "MSMF")
    assert _foi_desenhado(frame)


def test_selecionado_desenha_o_rotulo():
    frame = _quadro()
    ui.desenhar_selecionado(frame, LARGURA, ALTURA, "SIM")
    assert _foi_desenhado(frame)


# =====================================================================
# Resolução nativa 1920x1080
# =====================================================================
def test_telas_de_producao_renderizam_em_1920x1080():
    largura, altura = 1920, 1080
    hist_esq = _historico(0.3, 0.001)
    hist_dir = _historico(0.7, -0.001)

    def quadro():
        return np.zeros((altura, largura, 3), dtype=np.uint8)

    telas = []

    frame = quadro()
    ui.desenhar_menu(frame, largura, altura, True, 0.31, 0.71, "Ana", 0.03,
                     prancha_valida=True, camera_ok=True)
    telas.append(frame)

    frame = quadro()
    ui.desenhar_painel_sim_nao(frame, largura, altura, largura // 2, True)
    telas.append(frame)

    frame = quadro()
    ui.desenhar_calibracao_sim_nao(
        frame, largura, altura, alvo="SIM", coletando=True, progresso=0.5,
        amostras=20, minimo=40, descartadas=1, media_esq=0.31, media_dir=0.71,
        historico_esq=hist_esq, historico_dir=hist_dir,
        tamanho_historico=200, perfil="Ana",
    )
    telas.append(frame)

    frame = quadro()
    prancha.desenhar_prancha(frame, largura, altura, foco="comer",
                             progresso=0.55, perfil="Ana")
    telas.append(frame)

    frame = quadro()
    ui.desenhar_modo_cuidador(
        frame, largura, altura, perfil="Ana", prancha_valida=True,
        prancha_fraca=False, calibracao_valida=True, camera_ok=True,
    )
    telas.append(frame)

    frame = quadro()
    ui.desenhar_configuracoes(frame, largura, altura, carregar_config(), "Ana")
    telas.append(frame)

    frame = quadro()
    ui.desenhar_sem_sinal(frame, largura, altura, 12.0, "MSMF")
    telas.append(frame)

    for frame in telas:
        assert frame.shape == (altura, largura, 3)
        assert _foi_desenhado(frame)


def test_grafico_e_aviso_escalam_para_1920x1080():
    largura, altura = 1920, 1080
    frame = np.zeros((altura, largura, 3), dtype=np.uint8)

    ui.desenhar_grafico_temporal(
        frame,
        _historico(0.3, 0.001),
        _historico(0.7, -0.001),
        0.31, 0.71,
        round(280 * largura / LARGURA), round(160 * altura / ALTURA),
        largura - 450, altura - 300, 200,
    )
    ui.desenhar_aviso_sem_rosto(frame, largura, altura)
    ui.desenhar_aviso(frame, largura, altura, "Mensagem de teste")

    assert frame.shape == (altura, largura, 3)
    assert _foi_desenhado(frame)
