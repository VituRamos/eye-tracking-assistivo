"""
Persistência da calibração da prancha de comunicação.

Cada perfil tem um arquivo ``perfis/<nome>.prancha.json`` com um ponto
de olhar (ratio_x, ratio_y) por bloco. A classificação depois é só
"vizinho mais próximo" (ver ``core/board.py``).

A calibração SIM/NÃO continua em ``perfis/<nome>.json``; os dois formatos
convivem sem conflito.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict

from core.board import IDS_BLOCOS

logger = logging.getLogger("eyetracking.prancha")

# Identifica COMO o olhar foi medido. O eixo vertical mudou de "pálpebras"
# para "linha dos cantos dos olhos" em 15/11/2026; perfis antigos guardam
# números de outra régua e não podem ser reaproveitados.
MEDIDA_ATUAL = "iris_cantos_v1"


class DadosPrancha(TypedDict):
    nome: str
    alvos: dict[str, list[float]]
    data_calibracao: str
    qualidade: str
    medida: str


class GerenciadorPrancha:
    def __init__(self, pasta: str | Path = "perfis", distancia_minima_boa: float = 0.02):
        self.pasta = Path(pasta)
        self.pasta.mkdir(exist_ok=True, parents=True)
        self.distancia_minima_boa = distancia_minima_boa

    def _caminho(self, nome_perfil: str) -> Path:
        nome = nome_perfil.strip()
        if not nome or not all(c.isalnum() or c in ("_", "-") for c in nome):
            raise ValueError(
                f"Nome de perfil inválido: '{nome_perfil}'. "
                "Use apenas letras, números, '_' ou '-'."
            )
        return self.pasta / f"{nome}.prancha.json"

    def salvar(self, nome_perfil: str, pontos: dict[str, tuple[float, float]]) -> DadosPrancha:
        _validar_pontos(pontos, exigir_todos=True)
        qualidade = (
            "boa"
            if _distancia_minima(pontos) >= self.distancia_minima_boa
            else "fraca"
        )
        dados: DadosPrancha = {
            "nome": nome_perfil,
            "alvos": {
                bloco_id: [round(x, 4), round(y, 4)]
                for bloco_id, (x, y) in pontos.items()
            },
            "data_calibracao": datetime.now().isoformat(timespec="seconds"),
            "qualidade": qualidade,
            "medida": MEDIDA_ATUAL,
        }
        caminho = self._caminho(nome_perfil)
        caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(
            "Calibração da prancha salva para '%s' (qualidade=%s).", nome_perfil, qualidade
        )
        return dados

    def carregar(self, nome_perfil: str) -> DadosPrancha | None:
        caminho = self._caminho(nome_perfil)
        if not caminho.exists():
            return None
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Falha ao ler a prancha de '%s': %s", nome_perfil, e)
            return None
        if isinstance(dados, dict) and dados.get("medida") != MEDIDA_ATUAL:
            logger.info(
                "Prancha de '%s' usa uma medida antiga (%r); refaça a calibração.",
                nome_perfil,
                dados.get("medida"),
            )
            return None
        validado = _validar_dados(dados)
        if validado is None:
            logger.error("Prancha de '%s' inválida. Ignorando.", nome_perfil)
        return validado

    def calibrar_vencida(self, dados: DadosPrancha, validade_dias: int = 7) -> bool:
        try:
            data = datetime.fromisoformat(str(dados["data_calibracao"]))
        except (KeyError, ValueError):
            return True
        return datetime.now() - data > timedelta(days=validade_dias)

    def listar_perfis(self) -> list[str]:
        """Nomes de perfil que têm prancha salva (sem o sufixo .prancha.json)."""
        sufixo = ".prancha.json"
        return sorted(
            p.name[: -len(sufixo)] for p in self.pasta.glob(f"*{sufixo}")
        )


def _distancia_minima(pontos: dict[str, tuple[float, float]]) -> float:
    valores = list(pontos.values())
    menor = math.inf
    for i in range(len(valores)):
        for j in range(i + 1, len(valores)):
            menor = min(
                menor,
                math.hypot(valores[i][0] - valores[j][0], valores[i][1] - valores[j][1]),
            )
    return 0.0 if menor is math.inf else menor


def _validar_pontos(pontos: dict[str, tuple[float, float]], exigir_todos: bool) -> None:
    desconhecidos = [b for b in pontos if b not in IDS_BLOCOS]
    if desconhecidos:
        raise ValueError(
            f"Blocos desconhecidos na calibração: {', '.join(desconhecidos)}"
        )
    if exigir_todos:
        faltando = [b for b in IDS_BLOCOS if b not in pontos]
        if faltando:
            raise ValueError(f"Faltam blocos na calibração: {', '.join(faltando)}")
    for bloco_id, ponto in pontos.items():
        if len(ponto) != 2:
            raise ValueError(f"Ponto do bloco '{bloco_id}' deve ter 2 valores (x, y)")
        for valor in ponto:
            if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                raise ValueError(f"Coordenada do bloco '{bloco_id}' deve ser numérica")
            if not math.isfinite(valor) or not 0.0 <= float(valor) <= 1.0:
                raise ValueError(
                    f"Coordenada do bloco '{bloco_id}' deve estar entre 0.0 e 1.0"
                )


def _validar_dados(dados: object) -> DadosPrancha | None:
    if not isinstance(dados, dict):
        return None

    alvos = dados.get("alvos")
    if not isinstance(alvos, dict) or not alvos:
        return None

    pontos: dict[str, tuple[float, float]] = {}
    for bloco_id, valores in alvos.items():
        if not isinstance(bloco_id, str) or not isinstance(valores, (list, tuple)):
            return None
        if len(valores) != 2:
            return None
        try:
            x, y = float(valores[0]), float(valores[1])
        except (TypeError, ValueError):
            return None
        pontos[bloco_id] = (x, y)

    try:
        _validar_pontos(pontos, exigir_todos=True)
        data = dados.get("data_calibracao")
        if not isinstance(data, str) or not data:
            return None
        datetime.fromisoformat(data)
    except (TypeError, ValueError):
        return None

    nome = dados.get("nome", "")
    qualidade = dados.get("qualidade", "desconhecida")
    medida = dados.get("medida")
    if not isinstance(nome, str) or not isinstance(qualidade, str):
        return None
    if medida != MEDIDA_ATUAL:
        return None

    return {
        "nome": nome,
        "alvos": {k: [v[0], v[1]] for k, v in pontos.items()},
        "data_calibracao": data,
        "qualidade": qualidade,
        "medida": medida,
    }


def pontos_do_dados(dados: DadosPrancha) -> dict[str, tuple[float, float]]:
    """Converte o formato JSON (listas) no formato usado em memória (tuplas)."""
    return {
        bloco_id: (float(valores[0]), float(valores[1]))
        for bloco_id, valores in dados["alvos"].items()
    }
