"""
Resolução de caminhos em desenvolvimento e no executável (PyInstaller).

Em desenvolvimento, recursos (config, modelo) e dados (logs, perfis) ficam
na raiz do projeto. No executável gerado pelo PyInstaller:

  * recursos empacotados ficam em ``sys._MEIPASS`` (temporário, somente leitura);
  * dados graváveis ficam ao lado do ``.exe``.

Isso evita que o programa tente escrever dentro do diretório temporário do
PyInstaller e faz o modelo empacotado ser encontrado sem novo download.
"""
from __future__ import annotations

import sys
from pathlib import Path


def congelado() -> bool:
    """True quando rodando a partir do executável gerado pelo PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def pasta_recurso() -> Path:
    """Pasta onde ficam os arquivos empacotados (config, modelo)."""
    if congelado():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def pasta_dados() -> Path:
    """Pasta gravável para logs/perfis (ao lado do executável, se congelado)."""
    if congelado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolver_recurso(relativo: str | Path) -> Path:
    """Resolve um caminho relativo contra a pasta de recursos."""
    caminho = Path(relativo)
    return caminho if caminho.is_absolute() else pasta_recurso() / caminho


def resolver_dados(relativo: str | Path) -> Path:
    """Resolve um caminho relativo contra a pasta gravável de dados."""
    caminho = Path(relativo)
    return caminho if caminho.is_absolute() else pasta_dados() / caminho


def resolver_modelo(relativo: str | Path) -> Path:
    """
    Resolve o caminho do modelo.

    Ordem de preferência:
      1. caminho absoluto informado na configuração;
      2. modelo empacotado no executável (ou presente na raiz do projeto);
      3. caminho gravável ao lado do executável (onde o download é feito).
    """
    caminho = Path(relativo)
    if caminho.is_absolute():
        return caminho
    embutido = pasta_recurso() / caminho
    if embutido.exists():
        return embutido
    return pasta_dados() / caminho
