"""Exibição de erros fatais quando não há console (executável windowed)."""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger("eyetracking.erros")


def mostrar_erro_fatal(mensagem: str, titulo: str = "Eye-Tracking Assistivo") -> None:
    """
    Mostra o erro de forma visível ao cuidador.

    No executável gerado sem console, um traceback seria invisível; nesse
    caso abrimos uma caixa de diálogo nativa do Windows. Em desenvolvimento
    (ou em outras plataformas), imprimimos no stderr.
    """
    logger.error(mensagem)
    try:
        if sys.platform == "win32" and (
            getattr(sys, "frozen", False) or sys.stderr is None
        ):
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, mensagem, titulo, 0x10)  # MB_ICONERROR
            return
    except Exception as e:  # noqa: BLE001 - último recurso de comunicação
        logger.debug("Falha ao exibir MessageBox: %s", e)

    print(f"ERRO: {mensagem}", file=sys.stderr)
