"""
Preview isolado do novo design visual (tema claro).

Este pacote NÃO é usado pelo aplicativo em produção. Ele existe para
testar a linguagem visual nova (paleta, tipografia, pictogramas e telas)
sem tocar em ``ui/board_renderer.py``, em ``main.py`` ou nos tempos de
interação.

Entrada principal::

    python -m preview_novo_design
    python -m preview_novo_design --render-only

A dependência de Pillow fica apenas em ``requirements-preview.txt``.
"""

from __future__ import annotations

from .renderizar import renderizar_todas, telas_disponiveis

__all__ = ["renderizar_todas", "telas_disponiveis"]
