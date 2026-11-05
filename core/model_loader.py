"""
Download e verificação de integridade do modelo Face Landmarker.

O download é atômico: grava em um arquivo ``.part`` e só renomeia para o
nome final depois de validar o checksum. Assim, uma queda de conexão não
deixa um ``.task`` truncado que seria aceito na próxima execução.
"""
from __future__ import annotations

import hashlib
import logging
import os
import urllib.request
from pathlib import Path

logger = logging.getLogger("eyetracking.model")


def _sha256_do_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def garantir_modelo_baixado(caminho: str | Path, url: str, sha256_esperado: str = "") -> Path:
    """
    Baixa o modelo .task na primeira execução, se ainda não existir
    localmente. Se ``sha256_esperado`` for fornecido, valida a integridade
    do arquivo (baixado ou já existente) e re-baixa em caso de divergência.
    """
    caminho_path = Path(caminho)
    caminho_path.parent.mkdir(parents=True, exist_ok=True)

    if caminho_path.exists():
        if not sha256_esperado:
            return caminho_path
        checksum_atual = _sha256_do_arquivo(caminho_path)
        if checksum_atual == sha256_esperado:
            return caminho_path
        logger.warning(
            "Checksum do modelo local não confere (esperado=%s, obtido=%s). Baixando novamente.",
            sha256_esperado, checksum_atual,
        )
        caminho_path.unlink(missing_ok=True)

    parcial = caminho_path.with_name(caminho_path.name + ".part")
    parcial.unlink(missing_ok=True)

    logger.info("Baixando modelo do MediaPipe Face Landmarker para '%s'...", caminho_path)
    try:
        urllib.request.urlretrieve(url, parcial)
    except Exception as e:  # converte para mensagem amigável
        parcial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Falha ao baixar o modelo de '{url}'. Verifique sua conexão com a internet."
        ) from e

    if not parcial.exists() or parcial.stat().st_size == 0:
        parcial.unlink(missing_ok=True)
        raise RuntimeError("O download do modelo terminou vazio. Tente novamente.")

    if sha256_esperado:
        checksum_baixado = _sha256_do_arquivo(parcial)
        if checksum_baixado != sha256_esperado:
            parcial.unlink(missing_ok=True)
            raise RuntimeError(
                "Checksum do modelo baixado não confere com o esperado. "
                "O arquivo foi removido; tente novamente."
            )

    os.replace(parcial, caminho_path)
    logger.info("Download concluído (%s).", caminho_path)
    return caminho_path
