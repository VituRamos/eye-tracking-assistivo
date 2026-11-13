"""Testes da tradução dos ajustes editados na interface para o YAML."""
import pytest

from config.loader import _config_padrao
from ponte import (
    aplicar_ajustes_config,
    histerese_aviso_cabeca,
    histerese_aviso_distancia,
)


class TestAplicarAjustes:
    def test_converte_camel_case_para_snake_case(self):
        base = _config_padrao()
        novo = aplicar_ajustes_config(
            base,
            {
                "deteccao": {
                    "dwellMs": 900,
                    "alphaEma": 0.5,
                    "divergenciaMax": 0.4,
                    "distanciaHabilitada": False,
                    "distanciaLongeAbaixo": 0.09,
                    "distanciaPertoAcima": 0.31,
                    "distanciaEntradaMs": 900,
                    "distanciaSaidaMs": 500,
                    "piscadaHabilitada": False,
                    "limiarEar": 0.2,
                },
                "calibracao": {"duracaoMs": 4000},
                "camera": {"largura": 1920, "backend": "dshow"},
                "perfis": {"validadeDias": 15},
                "feedback": {"som": False},
                "aparencia": {"tema": "escuro"},
                "janela": {"resolucao": "1280x720", "fullscreen": True},
            },
        )

        assert novo["deteccao"]["dwell_ms"] == 900
        assert novo["deteccao"]["alpha_ema"] == 0.5
        assert novo["deteccao"]["divergencia_max"] == 0.4
        assert novo["deteccao"]["distancia_habilitada"] is False
        assert novo["deteccao"]["distancia_longe_abaixo"] == 0.09
        assert novo["deteccao"]["distancia_perto_acima"] == 0.31
        assert novo["deteccao"]["distancia_entrada_ms"] == 900
        assert novo["deteccao"]["distancia_saida_ms"] == 500
        assert novo["deteccao"]["piscada"]["habilitada"] is False
        assert novo["deteccao"]["piscada"]["limiar_ear"] == 0.2
        assert novo["calibracao"]["duracao_ms"] == 4000
        assert novo["camera"]["largura"] == 1920
        assert novo["camera"]["backend"] == "dshow"
        assert novo["perfis"]["validade_dias"] == 15
        assert novo["feedback"]["som"] is False
        assert novo["aparencia"]["tema"] == "escuro"
        assert novo["janela"]["resolucao"] == "1280x720"
        assert novo["janela"]["fullscreen"] is True

    def test_nao_altera_a_configuracao_original(self):
        base = _config_padrao()
        aplicar_ajustes_config(base, {"deteccao": {"dwellMs": 900}})
        assert base["deteccao"]["dwell_ms"] == 700

    def test_booleano_invalido_e_rejeitado(self):
        with pytest.raises(ValueError):
            aplicar_ajustes_config(
                _config_padrao(),
                {"deteccao": {"piscadaHabilitada": "sim"}},
            )

    def test_ajustes_ausentes_preservam_valores(self):
        base = _config_padrao()
        novo = aplicar_ajustes_config(base, {})
        assert novo == base


class TestHistereseAvisoCabeca:
    def test_so_mostra_depois_de_tempo_continuo_fora_de_posicao(self):
        mostrar, ruim, boa = histerese_aviso_cabeca(False, None, None, True, 10.0)
        assert mostrar is False

        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, True, 10.30)
        assert mostrar is False

        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, True, 10.46)
        assert mostrar is True

    def test_nao_pisca_quando_a_pose_oscila(self):
        mostrar, ruim, boa = histerese_aviso_cabeca(False, None, None, True, 0.0)
        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, True, 0.50)
        assert mostrar is True

        # Uma única leitura boa não esconde o aviso na hora.
        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, False, 0.55)
        assert mostrar is True
        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, True, 0.60)
        assert mostrar is True

        # Só some após recuperação contínua.
        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, False, 0.70)
        mostrar, ruim, boa = histerese_aviso_cabeca(mostrar, ruim, boa, False, 1.10)
        assert mostrar is False


class TestHistereseAvisoDistancia:
    def test_so_mostra_depois_do_tempo_de_entrada(self):
        mostrar, ruim, boa = histerese_aviso_distancia(
            False, None, None, True, 10.0, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is False

        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, True, 10.5, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is False

        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, True, 10.81, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is True

    def test_oscilacao_curta_nao_esconde_o_aviso(self):
        mostrar, ruim, boa = histerese_aviso_distancia(
            False, None, None, True, 0.0, entrada_s=0.8, saida_s=0.6
        )
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, True, 0.9, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is True

        # Volta à faixa boa por menos que a histerese de saída.
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, False, 1.0, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is True
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, False, 1.5, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is True

    def test_some_depois_da_recuperacao_continua(self):
        mostrar, ruim, boa = histerese_aviso_distancia(
            False, None, None, True, 0.0, entrada_s=0.8, saida_s=0.6
        )
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, True, 0.9, entrada_s=0.8, saida_s=0.6
        )
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, False, 1.0, entrada_s=0.8, saida_s=0.6
        )
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, False, 1.61, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is False

    def test_mudar_de_longe_para_perto_mantem_o_aviso(self):
        mostrar, ruim, boa = histerese_aviso_distancia(
            False, None, None, True, 0.0, entrada_s=0.8, saida_s=0.6
        )
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, True, 0.9, entrada_s=0.8, saida_s=0.6
        )
        # Continua fora da faixa (agora perto): não reinicia o tempo.
        mostrar, ruim, boa = histerese_aviso_distancia(
            mostrar, ruim, boa, True, 1.2, entrada_s=0.8, saida_s=0.6
        )
        assert mostrar is True
