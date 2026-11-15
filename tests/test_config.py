"""Testes do carregamento/validação de configuração."""
import pytest

from config.loader import _config_padrao, carregar_config, salvar_config


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
        assert cfg["deteccao"]["divergencia_max"] == 0.25
        assert cfg["deteccao"]["sem_rosto_ms"] == 2000
        assert cfg["deteccao"]["compensar_yaw"] is False
        assert cfg["deteccao"]["confianca_minima"] == 0.5
        assert cfg["calibracao"]["max_pitch_graus"] == 25.0
        assert cfg["calibracao"]["max_roll_graus"] == 30.0
        assert cfg["camera"]["largura"] == 1280

    def test_yaml_aninhado_parcial_preserva_o_resto(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  piscada:\n    habilitada: false\n",
        )
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["piscada"]["habilitada"] is False
        assert cfg["deteccao"]["piscada"]["piscada_ms"] == 350

    def test_limite_em_frames_e_convertido_para_ms(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  limite_frames_sem_rosto: 60\n",
        )
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["sem_rosto_ms"] == 2000
        assert "limite_frames_sem_rosto" not in cfg["deteccao"]

    def test_sem_rosto_ms_tem_prioridade_sobre_a_chave_antiga(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  limite_frames_sem_rosto: 60\n  sem_rosto_ms: 3500\n",
        )
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["sem_rosto_ms"] == 3500


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

    def test_tema_invalido_usa_padroes(self, tmp_path):
        caminho = escrever_yaml(tmp_path, "aparencia:\n  tema: azul\n")
        assert carregar_config(caminho) == _config_padrao()

    @pytest.mark.parametrize("valor", [0, -0.1, 1.5])
    def test_divergencia_fora_da_faixa_usa_padroes(self, tmp_path, valor):
        caminho = escrever_yaml(tmp_path, f"deteccao:\n  divergencia_max: {valor}\n")
        assert carregar_config(caminho) == _config_padrao()

    def test_divergencia_personalizada_e_aceita(self, tmp_path):
        caminho = escrever_yaml(tmp_path, "deteccao:\n  divergencia_max: 0.4\n")
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["divergencia_max"] == 0.4

    def test_distancia_padrao(self, tmp_path):
        cfg = carregar_config(tmp_path / "nao_existe.yaml")
        assert cfg["deteccao"]["distancia_habilitada"] is True
        assert cfg["deteccao"]["distancia_longe_abaixo"] == 0.11
        assert cfg["deteccao"]["distancia_perto_acima"] == 0.34

    def test_distancia_personalizada_e_aceita(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  distancia_longe_abaixo: 0.08\n  distancia_perto_acima: 0.40\n",
        )
        cfg = carregar_config(caminho)
        assert cfg["deteccao"]["distancia_longe_abaixo"] == 0.08
        assert cfg["deteccao"]["distancia_perto_acima"] == 0.40

    def test_distancia_com_limites_invertidos_usa_padroes(self, tmp_path):
        caminho = escrever_yaml(
            tmp_path,
            "deteccao:\n  distancia_longe_abaixo: 0.5\n  distancia_perto_acima: 0.2\n",
        )
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


class TestSalvar:
    def test_ida_e_volta_preserva_valores(self, tmp_path):
        cfg = _config_padrao()
        cfg["deteccao"]["dwell_ms"] = 900
        cfg["deteccao"]["piscada"]["habilitada"] = False
        cfg["camera"]["fps"] = 60
        cfg["janela"]["resolucao"] = "1280x720"

        caminho = salvar_config(cfg, tmp_path / "settings.yaml")

        assert caminho.exists()
        assert carregar_config(caminho) == cfg

    def test_resolucao_invalida_e_rejeitada(self, tmp_path):
        cfg = _config_padrao()
        cfg["janela"]["resolucao"] = "800x600"
        with pytest.raises(ValueError):
            salvar_config(cfg, tmp_path / "settings.yaml")

    def test_arquivo_nao_fica_parcial_em_caso_de_erro(self, tmp_path):
        destino = tmp_path / "settings.yaml"
        destino.write_text("configuracao antiga", encoding="utf-8")
        cfg = _config_padrao()
        cfg["janela"]["resolucao"] = "invalida"

        with pytest.raises(ValueError):
            salvar_config(cfg, destino)

        assert destino.read_text(encoding="utf-8") == "configuracao antiga"
