"""Testes do download atômico/verificação do modelo."""
import hashlib

import pytest

from core.model_loader import garantir_modelo_baixado


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


class TestGarantirModelo:
    def test_baixa_para_destino_e_nao_deixa_partial(self, tmp_path):
        origem = tmp_path / "origem.task"
        conteudo = b"modelo-fake"
        origem.write_bytes(conteudo)
        destino = tmp_path / "models" / "face.task"

        resultado = garantir_modelo_baixado(
            destino, origem.as_uri(), sha256(conteudo)
        )

        assert resultado == destino
        assert destino.read_bytes() == conteudo
        assert not destino.with_name(destino.name + ".part").exists()

    def test_reaproveita_arquivo_existente_valido(self, tmp_path):
        destino = tmp_path / "face.task"
        destino.write_bytes(b"ok")
        resultado = garantir_modelo_baixado(
            destino, "https://exemplo.invalid/nao-deve-baixar", sha256(b"ok")
        )
        assert resultado == destino
        assert destino.read_bytes() == b"ok"

    def test_rebaixa_quando_checksum_local_diverge(self, tmp_path):
        origem = tmp_path / "origem.task"
        conteudo = b"novo-conteudo"
        origem.write_bytes(conteudo)
        destino = tmp_path / "face.task"
        destino.write_bytes(b"conteudo-antigo")

        garantir_modelo_baixado(destino, origem.as_uri(), sha256(conteudo))
        assert destino.read_bytes() == conteudo

    def test_checksum_baixado_errado_remove_arquivo(self, tmp_path):
        origem = tmp_path / "origem.task"
        origem.write_bytes(b"conteudo")
        destino = tmp_path / "face.task"

        with pytest.raises(RuntimeError):
            garantir_modelo_baixado(destino, origem.as_uri(), "0" * 64)

        assert not destino.exists()
        assert not destino.with_name(destino.name + ".part").exists()

    def test_falha_de_download_limpa_partial(self, tmp_path):
        destino = tmp_path / "face.task"
        with pytest.raises(RuntimeError):
            garantir_modelo_baixado(destino, (tmp_path / "inexistente").as_uri())
        assert not destino.exists()
        assert not destino.with_name(destino.name + ".part").exists()
