"""
Testes do gerenciador de persistência de calibração (core/calibration.py).

Usa a fixture `tmp_path` do pytest para criar uma pasta temporária a
cada teste -- assim os testes não escrevem em `perfis/` de verdade nem
dependem de estado deixado por execuções anteriores.
"""
from datetime import datetime, timedelta

import pytest

from core.calibration import GerenciadorCalibracao


@pytest.fixture
def gerenciador(tmp_path):
    return GerenciadorCalibracao(pasta=tmp_path / "perfis")


class TestSalvarECarregar:
    def test_salvar_e_carregar_perfil(self, gerenciador):
        gerenciador.salvar("joao", media_esq=0.30, media_dir=0.70)
        dados = gerenciador.carregar("joao")

        assert dados is not None
        assert dados["nome"] == "joao"
        assert dados["media_esquerda"] == pytest.approx(0.30)
        assert dados["media_direita"] == pytest.approx(0.70)

    def test_carregar_perfil_inexistente_retorna_none(self, gerenciador):
        assert gerenciador.carregar("nao_existe") is None

    def test_qualidade_boa_quando_diferenca_grande(self, gerenciador):
        dados = gerenciador.salvar("maria", media_esq=0.20, media_dir=0.80)
        assert dados["qualidade"] == "boa"

    def test_qualidade_fraca_quando_diferenca_pequena(self, gerenciador):
        dados = gerenciador.salvar("pedro", media_esq=0.48, media_dir=0.52)
        assert dados["qualidade"] == "fraca"


class TestListarPerfis:
    def test_lista_vazia_inicialmente(self, gerenciador):
        assert gerenciador.listar_perfis() == []

    def test_lista_perfis_salvos_em_ordem_alfabetica(self, gerenciador):
        gerenciador.salvar("zeca", 0.3, 0.7)
        gerenciador.salvar("ana", 0.3, 0.7)
        assert gerenciador.listar_perfis() == ["ana", "zeca"]


class TestValidadeCalibracao:
    def test_calibracao_recente_nao_esta_vencida(self, gerenciador):
        dados = gerenciador.salvar("recente", 0.3, 0.7)
        assert not gerenciador.calibracao_esta_vencida(dados, validade_dias=7)

    def test_calibracao_antiga_esta_vencida(self, gerenciador):
        dados = gerenciador.salvar("antigo", 0.3, 0.7)
        data_antiga = datetime.now() - timedelta(days=30)
        dados["data_calibracao"] = data_antiga.isoformat(timespec="seconds")
        assert gerenciador.calibracao_esta_vencida(dados, validade_dias=7)

    def test_dados_sem_data_conta_como_vencida(self, gerenciador):
        dados = {"nome": "x", "media_esquerda": 0.3, "media_direita": 0.7, "qualidade": "boa",
                 "data_calibracao": ""}
        assert gerenciador.calibracao_esta_vencida(dados)


class TestNomesInvalidos:
    def test_nome_com_caracteres_invalidos_levanta_erro(self, gerenciador):
        with pytest.raises(ValueError):
            gerenciador.salvar("../../etc/passwd", 0.3, 0.7)

    def test_nome_vazio_levanta_erro(self, gerenciador):
        with pytest.raises(ValueError):
            gerenciador.salvar("   ", 0.3, 0.7)


class TestValidacaoDeConteudo:
    def _escrever(self, gerenciador, nome, texto):
        (gerenciador.pasta / f"{nome}.json").write_text(texto, encoding="utf-8")

    def test_json_corrompido_retorna_none(self, gerenciador):
        self._escrever(gerenciador, "quebrado", "{nao e json")
        assert gerenciador.carregar("quebrado") is None

    def test_chaves_faltando_retorna_none(self, gerenciador):
        self._escrever(gerenciador, "incompleto", '{"nome": "x"}')
        assert gerenciador.carregar("incompleto") is None

    def test_media_fora_da_faixa_retorna_none(self, gerenciador):
        self._escrever(
            gerenciador,
            "fora",
            '{"nome": "x", "media_esquerda": 1.5, "media_direita": 0.5, '
            '"data_calibracao": "2026-01-01T00:00:00", "qualidade": "boa"}',
        )
        assert gerenciador.carregar("fora") is None

    def test_data_invalida_retorna_none(self, gerenciador):
        self._escrever(
            gerenciador,
            "data_ruim",
            '{"nome": "x", "media_esquerda": 0.3, "media_direita": 0.7, '
            '"data_calibracao": "ontem", "qualidade": "boa"}',
        )
        assert gerenciador.carregar("data_ruim") is None

    def test_arquivo_com_lista_retorna_none(self, gerenciador):
        self._escrever(gerenciador, "lista", "[1, 2, 3]")
        assert gerenciador.carregar("lista") is None

    def test_salvar_rejeita_nan(self, gerenciador):
        with pytest.raises(ValueError):
            gerenciador.salvar("nan", float("nan"), 0.7)
