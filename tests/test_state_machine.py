"""Testes da máquina de estados e das regras de calibração."""
from core.state_machine import AppState, EstadoApp


class TestCalibracaoValida:
    def test_sem_calibracao_e_invalida(self):
        app = AppState()
        assert not app.calibracao_valida(0.03)

    def test_calibracao_com_boa_separacao_e_valida(self):
        app = AppState()
        app.calibracao_ja_feita = True
        app.media_esquerda_calibrada = 0.30
        app.media_direita_calibrada = 0.70
        assert app.calibracao_valida(0.03)

    def test_calibracao_fraca_e_invalida(self):
        app = AppState()
        app.calibracao_ja_feita = True
        app.media_esquerda_calibrada = 0.50
        app.media_direita_calibrada = 0.51
        assert not app.calibracao_valida(0.03)

    def test_flag_de_calibracao_fraca_bloqueia(self):
        app = AppState()
        app.calibracao_ja_feita = True
        app.media_esquerda_calibrada = 0.2
        app.media_direita_calibrada = 0.8
        app.calibracao_fraca = True
        assert not app.calibracao_valida(0.03)


class TestAvisos:
    def test_aviso_expira(self):
        app = AppState()
        app.avisar("teste", agora=10.0, duracao=2.0)
        assert app.aviso_ativo(11.0)
        assert not app.aviso_ativo(12.1)

    def test_aviso_vazio_nunca_esta_ativo(self):
        assert not AppState().aviso_ativo(0.0)


class TestResets:
    def test_resetar_calibracao_limpa_estado(self):
        app = AppState()
        app.calib_fase = "DIREITA"
        app.coletas_calibracao = [0.4, 0.5]
        app.tempo_inicio_coleta = 123.0
        app.calibracao_fraca = True
        app.resetar_calibracao()
        assert app.calib_fase == "ESQUERDA"
        assert app.coletas_calibracao == []
        assert app.tempo_inicio_coleta == 0.0
        assert not app.calibracao_fraca

    def test_resetar_selecao_limpa_estado(self):
        app = AppState()
        app.opcao_focada = "SIM"
        app.opcao_confirmada = "SIM"
        app.contador_fixacao = 10
        app.contador_piscada = 5
        app.resetar_selecao()
        assert app.opcao_focada is None
        assert app.opcao_confirmada is None
        assert app.contador_fixacao == 0
        assert app.contador_piscada == 0

    def test_transicao_troca_estado(self):
        app = AppState()
        app.transicionar(EstadoApp.ATIVO)
        assert app.estado == EstadoApp.ATIVO


class TestPrancha:
    def _referencias(self):
        return {
            "oi": (0.25, 0.25),
            "comer": (0.75, 0.25),
            "beber": (0.25, 0.75),
            "banheiro": (0.75, 0.75),
        }

    def test_sem_calibracao_e_invalida(self):
        assert not AppState().prancha_valida(0.02)

    def test_calibracao_completa_e_valida(self):
        app = AppState()
        app.referencias_prancha = self._referencias()
        app.prancha_calibrada = True
        assert app.prancha_valida(0.02)

    def test_flag_fraca_bloqueia(self):
        app = AppState()
        app.referencias_prancha = self._referencias()
        app.prancha_calibrada = True
        app.prancha_fraca = True
        assert not app.prancha_valida(0.02)

    def test_faltando_bloco_e_invalida(self):
        app = AppState()
        app.referencias_prancha = {"oi": (0.25, 0.25), "comer": (0.75, 0.25)}
        app.prancha_calibrada = True
        assert not app.prancha_valida(0.02)

    def test_pontos_muito_proximos_sao_invalidos(self):
        app = AppState()
        app.referencias_prancha = dict.fromkeys(
            ("oi", "comer", "beber", "banheiro"), (0.5, 0.5)
        )
        app.prancha_calibrada = True
        assert not app.prancha_valida(0.02)

    def test_resetar_prancha_limpa_tudo(self):
        app = AppState()
        app.indice_bloco_calib = 2
        app.coletas_prancha = [(0.3, 0.4)]
        app.referencias_prancha = self._referencias()
        app.tempo_inicio_coleta_prancha = 99.0
        app.prancha_calibrada = True
        app.prancha_fraca = True

        app.resetar_prancha()

        assert app.indice_bloco_calib == 0
        assert app.coletas_prancha == []
        assert app.referencias_prancha == {}
        assert app.tempo_inicio_coleta_prancha == 0.0
        assert not app.prancha_calibrada
        assert not app.prancha_fraca

    def test_bloco_atual_segue_a_ordem(self):
        app = AppState()
        assert app.bloco_calib_atual() == "oi"
        app.indice_bloco_calib = 1
        assert app.bloco_calib_atual() == "comer"
        app.indice_bloco_calib = 3
        assert app.bloco_calib_atual() == "banheiro"
        app.indice_bloco_calib = 99
        assert app.bloco_calib_atual() == "banheiro"
