"""Testes do controlador puro de seleção (dwell + piscada)."""
import pytest

from core.selection import ControladorSelecao


def criar(**kwargs):
    padroes = dict(
        dwell_ms=700,
        tolerancia_perda_ms=180,
        piscada_habilitada=False,
        piscada_ms=350,
        foco_minimo_ms=150,
        exibicao_confirmacao_ms=1500,
    )
    padroes.update(kwargs)
    return ControladorSelecao(**padroes)


class TestDwell:
    def test_confirma_apos_tempo_de_foco(self):
        c = criar()
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.2)
        c.atualizar("SIM", False, 0.4)
        c.atualizar("SIM", False, 0.6)
        decisao = c.atualizar("SIM", False, 0.8)
        assert decisao.opcao_confirmada == "SIM"
        assert decisao.metodo == "dwell"
        assert decisao.progresso == 1.0

    def test_nao_confirma_antes_do_tempo(self):
        c = criar()
        c.atualizar("SIM", False, 0.0)
        decisao = c.atualizar("SIM", False, 0.4)
        assert decisao.opcao_confirmada is None
        assert 0.0 < decisao.progresso < 1.0

    def test_trocar_de_opcao_zera_progresso(self):
        c = criar()
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.5)
        decisao = c.atualizar("NAO", False, 0.55)
        assert decisao.opcao_focada == "NAO"
        assert decisao.progresso == pytest.approx(0.0)

    def test_perda_curta_de_foco_nao_zera_dwell(self):
        c = criar(tolerancia_perda_ms=200)
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.3)
        c.atualizar(None, False, 0.35)  # 50 ms sem foco
        decisao = c.atualizar("SIM", False, 0.5)
        assert decisao.opcao_confirmada is None
        assert decisao.progresso > 0.3

    def test_perda_longa_de_foco_zera_dwell(self):
        c = criar(tolerancia_perda_ms=200)
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.3)
        c.atualizar(None, False, 0.6)  # 300 ms sem foco
        decisao = c.atualizar("SIM", False, 0.7)
        assert decisao.opcao_confirmada is None
        assert decisao.progresso == pytest.approx(0.0)

    def test_gap_longo_e_limitado(self):
        # Uma pausa de 10s não deve confirmar sozinha na volta.
        c = criar(dwell_ms=700)
        c.atualizar("SIM", False, 0.0)
        decisao = c.atualizar("SIM", False, 10.0)
        assert decisao.opcao_confirmada is None
        assert decisao.progresso == pytest.approx(250 / 700)

    def test_olhos_fechados_pausam_dwell_sem_zera_lo(self):
        c = criar(dwell_ms=500, piscada_habilitada=False)
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.2)  # 200 ms
        c.atualizar("SIM", True, 0.4)   # pausa
        c.atualizar("SIM", True, 0.6)   # pausa
        decisao = c.atualizar("SIM", False, 0.7)  # +100 ms
        assert decisao.opcao_confirmada is None
        assert decisao.progresso == pytest.approx(300 / 500)
        decisao = c.atualizar("SIM", False, 0.9)  # +200 ms -> 500
        assert decisao.opcao_confirmada == "SIM"


class TestPiscada:
    def test_piscada_longa_confirma_com_foco(self):
        c = criar(piscada_habilitada=True, piscada_ms=350)
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.2)  # foco acumulado > 150 ms
        c.atualizar("SIM", True, 0.25)  # começa a piscada
        decisao = c.atualizar("SIM", True, 0.60)  # 350 ms fechado
        assert decisao.opcao_confirmada == "SIM"
        assert decisao.metodo == "piscada"

    def test_piscada_curta_nao_confirma(self):
        c = criar(piscada_habilitada=True, piscada_ms=350)
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.2)
        c.atualizar("SIM", True, 0.25)
        decisao = c.atualizar("SIM", True, 0.40)  # apenas 150 ms
        assert decisao.opcao_confirmada is None

    def test_piscada_sem_foco_nao_confirma(self):
        c = criar(piscada_habilitada=True, piscada_ms=350)
        c.atualizar(None, True, 0.0)
        decisao = c.atualizar(None, True, 1.0)
        assert decisao.opcao_confirmada is None

    def test_abrir_os_olhos_reinicia_piscada(self):
        c = criar(piscada_habilitada=True, piscada_ms=350)
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.2)
        c.atualizar("SIM", True, 0.25)
        c.atualizar("SIM", False, 0.35)  # abriu
        c.atualizar("SIM", True, 0.40)  # fechou de novo
        decisao = c.atualizar("SIM", True, 0.60)  # só 200 ms
        assert decisao.opcao_confirmada is None


class TestConfirmacao:
    def test_confirmacao_persiste_ate_reset(self):
        c = criar()
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.3)
        c.atualizar("SIM", False, 0.6)
        c.atualizar("SIM", False, 0.9)
        decisao = c.atualizar("SIM", False, 1.0)
        assert decisao.opcao_confirmada == "SIM"
        assert not c.deve_limpar_confirmacao(1.0)
        assert c.deve_limpar_confirmacao(2.5)

    def test_reset_limpa_tudo(self):
        c = criar()
        c.atualizar("SIM", False, 0.0)
        c.atualizar("SIM", False, 0.3)
        c.atualizar("SIM", False, 0.6)
        c.atualizar("SIM", False, 0.9)
        assert c.opcao_confirmada == "SIM"
        c.reset()
        assert c.opcao_focada is None
        assert c.opcao_confirmada is None
        assert c.atualizar("SIM", False, 1.0).progresso == pytest.approx(0.0)


class TestValidacao:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"dwell_ms": 0},
            {"tolerancia_perda_ms": -1},
            {"piscada_ms": 0},
            {"exibicao_confirmacao_ms": 0},
        ],
    )
    def test_parametros_invalidos(self, kwargs):
        with pytest.raises(ValueError):
            criar(**kwargs)
