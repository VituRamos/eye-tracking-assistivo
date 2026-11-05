"""Testes do carregamento/validação de configuração."""
import pytest

from config.loader import _config_padrao, carregar_config


def escrever_yaml(tmp_path, conteudo: str):
    caminho = tmp_path / "settings.yaml"
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


class TestMergeComPadroes:
    def test_yaml_parcial_completa_com_padroes(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  alpha_ema: 0.5\n",
        )
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["alpha_ema"] == 0.5
        assert cfg["deteccao"]["dwell_ms"] == 700
        assert cfg["deteccao"]["piscada"]["limiar_ear"] == 0.15
        assert cfg["camera"]["largura"] == 1280

    def test_yaml_aninhado_parcial_preserva_o_resto(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  piscada:\n    habilitada: false\n",
        )
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["piscada"]["habilitada"] is False
        assert cfg["deteccao"]["piscada"]["piscada_ms"] == 350


class TestFallback:
    def test_arquivo_inexistente_usa_padroes(self, tmp_path):
        cfg = carregar_config(tmp_path / "nao_existe.yaml")
        assert cfg == _config_padrao()

    def test_yaml_invalido_usa_padroes(self, tmp_path):
        caminho = escrever_yaml(tmp_path, "deteccao: [\n")
        assert carregar_config(caminho) == _config_padrao()

    def test_valor_fora_da_faixa_usa_padroes(self, tmp_path):
        caminho = escrever_yaml(tmp_path, "deteccao:\n  alpha_ema: 0\n")
        assert carregar_config(caminho) == _config_padrao()

    def test_tipo_errado_usa_padroes(self, tmp_path):
        caminho = escrever_yaml(tmp_path, "camera:\n  largura: 'muito grande'\n")
        assert carregar_config(caminho) == _config_padrao()

    @pytest.mark.parametrize(
        "conteudo",
        [
            "",
            "[]\n",
            "- item\n",
        ],
    )
    def test_estrutura_invalida_usa_padroes(self, tmp_path, conteudo):
        caminho = escrever_yaml(tmp_path, conteudo)
        assert carregar_config(caminho) == _config_padrao()
