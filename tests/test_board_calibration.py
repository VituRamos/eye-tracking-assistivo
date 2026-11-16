"""Testes da persistência da calibração da prancha."""
import json
from datetime import datetime, timedelta

import pytest

from core.board import IDS_BLOCOS
from core.board_calibration import MEDIDA_ATUAL, GerenciadorPrancha, pontos_do_dados
from core.calibration import GerenciadorCalibracao


@pytest.fixture
def gerenciador(tmp_path):
    return GerenciadorPrancha(pasta=tmp_path / "perfis")


def _pontos():
    return {
        "oi": (0.25, 0.25),
        "comer": (0.75, 0.25),
        "beber": (0.25, 0.75),
        "banheiro": (0.75, 0.75),
    }


class TestSalvarECarregar:
    def test_salva_arquivo_com_sufixo_proprio(self, gerenciador):
        gerenciador.salvar("ana", _pontos())
        assert (gerenciador.pasta / "ana.prancha.json").exists()
        assert not (gerenciador.pasta / "ana.json").exists()

    def test_round_trip(self, gerenciador):
        gerenciador.salvar("ana", _pontos())
        dados = gerenciador.carregar("ana")

        assert dados is not None
        assert dados["nome"] == "ana"
        lidos = pontos_do_dados(dados)
        for bloco_id, ponto in _pontos().items():
            assert lidos[bloco_id] == pytest.approx(ponto)

    def test_perfil_inexistente_retorna_none(self, gerenciador):
        assert gerenciador.carregar("ninguem") is None

    def test_qualidade_boa_quando_blocos_bem_separados(self, gerenciador):
        dados = gerenciador.salvar("boa", _pontos())
        assert dados["qualidade"] == "boa"

    def test_qualidade_fraca_quando_blocos_quase_iguais(self, gerenciador):
        pontos = dict.fromkeys(IDS_BLOCOS, (0.50, 0.50))
        dados = gerenciador.salvar("fraca", pontos)
        assert dados["qualidade"] == "fraca"

    def test_limiar_de_qualidade_e_configuravel(self, tmp_path):
        gerenciador = GerenciadorPrancha(tmp_path / "perfis", distancia_minima_boa=0.9)
        dados = gerenciador.salvar("exigente", _pontos())
        assert dados["qualidade"] == "fraca"


class TestListarPerfis:
    def test_lista_vazia(self, gerenciador):
        assert gerenciador.listar_perfis() == []

    def test_lista_nomes_sem_sufixo(self, gerenciador):
        gerenciador.salvar("zeca", _pontos())
        gerenciador.salvar("ana", _pontos())
        assert gerenciador.listar_perfis() == ["ana", "zeca"]

    def test_nao_interfere_na_lista_de_perfis_sim_nao(self, tmp_path):
        pasta = tmp_path / "perfis"
        sim_nao = GerenciadorCalibracao(pasta=pasta)
        prancha = GerenciadorPrancha(pasta=pasta)

        sim_nao.salvar("ana", 0.3, 0.7)
        prancha.salvar("ana", _pontos())
        prancha.salvar("bruno", _pontos())

        # A prancha não pode aparecer como "ana.prancha" na lista SIM/NÃO.
        assert sim_nao.listar_perfis() == ["ana"]
        assert prancha.listar_perfis() == ["ana", "bruno"]


class TestValidade:
    def test_recente_nao_esta_vencida(self, gerenciador):
        dados = gerenciador.salvar("recente", _pontos())
        assert not gerenciador.calibrar_vencida(dados, validade_dias=7)

    def test_antiga_esta_vencida(self, gerenciador):
        dados = gerenciador.salvar("antiga", _pontos())
        dados["data_calibracao"] = (
            datetime.now() - timedelta(days=30)
        ).isoformat(timespec="seconds")
        assert gerenciador.calibrar_vencida(dados, validade_dias=7)

    def test_data_invalida_conta_como_vencida(self, gerenciador):
        dados = gerenciador.salvar("sem_data", _pontos())
        dados["data_calibracao"] = ""
        assert gerenciador.calibrar_vencida(dados)


class TestValidacao:
    def test_salvar_exige_todos_os_blocos(self, gerenciador):
        with pytest.raises(ValueError, match="Faltam blocos"):
            gerenciador.salvar("incompleto", {"oi": (0.5, 0.5)})

    def test_coordenada_fora_da_faixa_levanta_erro(self, gerenciador):
        pontos = _pontos()
        pontos["oi"] = (1.5, 0.5)
        with pytest.raises(ValueError, match=r"entre 0\.0 e 1\.0"):
            gerenciador.salvar("fora", pontos)

    def test_nan_levanta_erro(self, gerenciador):
        pontos = _pontos()
        pontos["oi"] = (float("nan"), 0.5)
        with pytest.raises(ValueError, match=r"entre 0\.0 e 1\.0"):
            gerenciador.salvar("nan", pontos)

    def test_nome_invalido_levanta_erro(self, gerenciador):
        with pytest.raises(ValueError):
            gerenciador.salvar("../../etc/passwd", _pontos())

    def test_json_corrompido_retorna_none(self, gerenciador):
        (gerenciador.pasta / "quebrado.prancha.json").write_text(
            "{nao e json", encoding="utf-8",
        )
        assert gerenciador.carregar("quebrado") is None

    def test_estrutura_invalida_retorna_none(self, gerenciador):
        (gerenciador.pasta / "lista.prancha.json").write_text(
            "[1, 2, 3]", encoding="utf-8",
        )
        assert gerenciador.carregar("lista") is None

    def test_alvos_vazios_retorna_none(self, gerenciador):
        (gerenciador.pasta / "vazio.prancha.json").write_text(
            '{"nome": "x", "alvos": {}, "data_calibracao": "2026-01-01T00:00:00"}',
            encoding="utf-8",
        )
        assert gerenciador.carregar("vazio") is None

    def test_coordenada_invalida_no_arquivo_retorna_none(self, gerenciador):
        (gerenciador.pasta / "ruim.prancha.json").write_text(
            '{"nome": "x", "alvos": {"oi": [2.0, 0.5]}, '
            '"data_calibracao": "2026-01-01T00:00:00"}',
            encoding="utf-8",
        )
        assert gerenciador.carregar("ruim") is None

    def test_bloco_desconhecido_retorna_none(self, gerenciador):
        (gerenciador.pasta / "estranho.prancha.json").write_text(
            '{"nome": "x", "alvos": {"dormir": [0.5, 0.5]}, '
            '"data_calibracao": "2026-01-01T00:00:00"}',
            encoding="utf-8",
        )
        assert gerenciador.carregar("estranho") is None

    def test_prancha_de_outra_medida_e_invalidada(self, gerenciador):
        # O eixo vertical mudou de régua (pálpebras -> cantos dos olhos).
        # Perfis antigos têm números incompatíveis e devem ser refeitos.
        gerenciador.salvar("antiga", _pontos())
        caminho = gerenciador.pasta / "antiga.prancha.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados["medida"] = "iris_palpebras_v0"
        caminho.write_text(json.dumps(dados), encoding="utf-8")
        assert gerenciador.carregar("antiga") is None

    def test_prancha_sem_campo_medida_e_invalidada(self, gerenciador):
        gerenciador.salvar("sem_medida", _pontos())
        caminho = gerenciador.pasta / "sem_medida.prancha.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        dados.pop("medida", None)
        caminho.write_text(json.dumps(dados), encoding="utf-8")
        assert gerenciador.carregar("sem_medida") is None

    def test_salvar_grava_a_medida_atual(self, gerenciador):
        dados = gerenciador.salvar("atual", _pontos())
        assert dados["medida"] == MEDIDA_ATUAL
        assert gerenciador.carregar("atual") is not None

    def test_arquivo_incompleto_retorna_none(self, gerenciador):
        # Uma prancha só é utilizável com os 4 blocos; um arquivo
        # truncado (2 blocos) não deve ser aceito em silêncio.
        (gerenciador.pasta / "parcial.prancha.json").write_text(
            '{"nome": "x", "alvos": {"oi": [0.2, 0.2], "comer": [0.8, 0.2]}, '
            '"data_calibracao": "2026-01-01T00:00:00"}',
            encoding="utf-8",
        )
        assert gerenciador.carregar("parcial") is None
