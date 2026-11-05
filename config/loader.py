"""
Carregamento de configuração externa (YAML).

Mantém o sistema ajustável sem precisar editar código Python -- um
terapeuta ou cuidador pode alterar sensibilidade, resolução de câmera,
etc. só editando o settings.yaml.

O arquivo lido é mesclado sobre os valores padrão em código, de modo que
um YAML incompleto não gere ``KeyError`` em tempo de execução. Depois da
mesclagem, os valores são validados (tipos e faixas); se algo estiver
inválido, o sistema volta para a configuração padrão e registra o erro.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from core import paths

logger = logging.getLogger("eyetracking.config")

CAMINHO_PADRAO = paths.resolver_recurso("config/settings.yaml")


def carregar_config(caminho: str | Path | None = None) -> dict[str, Any]:
    """
    Carrega o settings.yaml.

    Se o arquivo não existir, estiver corrompido ou tiver valores
    inválidos, cai para os valores padrão em código (o app nunca deve
    travar por causa de configuração ausente/quebrada).
    """
    caminho = Path(caminho) if caminho is not None else _caminho_padrao()
    padrao = _config_padrao()

    if not caminho.exists():
        logger.warning("Arquivo de configuração '%s' não encontrado. Usando valores padrão.", caminho)
        return padrao

    try:
        conteudo = yaml.safe_load(caminho.read_text(encoding="utf-8"))
        if not isinstance(conteudo, dict) or not conteudo:
            raise ValueError("Arquivo de configuração vazio ou inválido.")
        cfg = _mesclar_profundo(padrao, conteudo)
        _validar_config(cfg)
        return cfg
    except Exception as e:  # noqa: BLE001 - fallback deliberado e registrado
        logger.error("Falha ao ler '%s' (%s). Usando valores padrão.", caminho, e)
        return padrao


def _caminho_padrao() -> Path:
    """
    Configuração padrão.

    No executável, um ``config/settings.yaml`` colocado ao lado do .exe
    tem prioridade sobre o arquivo empacotado, permitindo ajustes sem
    reconstruir o executável.
    """
    if paths.congelado():
        externo = paths.resolver_dados("config/settings.yaml")
        if externo.exists():
            return externo
    return CAMINHO_PADRAO


def _mesclar_profundo(base: dict, sobrescrita: dict) -> dict:
    """Mescla dicionários recursivamente sem alterar o dicionário base."""
    resultado = dict(base)
    for chave, valor in sobrescrita.items():
        if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
            resultado[chave] = _mesclar_profundo(resultado[chave], valor)
        else:
            resultado[chave] = valor
    return resultado


# =====================================================================
# Validação
# =====================================================================
def _eh_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _inteiro(valor: Any, nome: str, minimo: int = 0) -> None:
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < minimo:
        raise ValueError(f"{nome} deve ser inteiro >= {minimo} (recebido: {valor!r})")


def _numero(valor: Any, nome: str, minimo: float | None = None,
            maximo: float | None = None, minimo_exclusivo: bool = False) -> None:
    if not _eh_numero(valor):
        raise ValueError(f"{nome} deve ser numérico (recebido: {valor!r})")
    if minimo is not None:
        if minimo_exclusivo and valor <= minimo:
            raise ValueError(f"{nome} deve ser > {minimo} (recebido: {valor!r})")
        if not minimo_exclusivo and valor < minimo:
            raise ValueError(f"{nome} deve ser >= {minimo} (recebido: {valor!r})")
    if maximo is not None and valor > maximo:
        raise ValueError(f"{nome} deve ser <= {maximo} (recebido: {valor!r})")


def _booleano(valor: Any, nome: str) -> None:
    if not isinstance(valor, bool):
        raise ValueError(f"{nome} deve ser true/false (recebido: {valor!r})")


def _texto(valor: Any, nome: str) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} deve ser um texto não vazio (recebido: {valor!r})")


def _validar_config(cfg: dict[str, Any]) -> None:
    det = cfg["deteccao"]
    _inteiro(det["dwell_ms"], "deteccao.dwell_ms", minimo=1)
    _inteiro(det["tolerancia_perda_ms"], "deteccao.tolerancia_perda_ms")
    _inteiro(det["exibicao_confirmacao_ms"], "deteccao.exibicao_confirmacao_ms", minimo=1)
    _numero(det["alpha_ema"], "deteccao.alpha_ema", minimo=0.0, maximo=1.0,
            minimo_exclusivo=True)
    _inteiro(det["tamanho_historico_grafico"], "deteccao.tamanho_historico_grafico", minimo=20)
    _inteiro(det["limite_frames_sem_rosto"], "deteccao.limite_frames_sem_rosto", minimo=1)

    piscada = det["piscada"]
    _booleano(piscada["habilitada"], "deteccao.piscada.habilitada")
    _numero(piscada["limiar_ear"], "deteccao.piscada.limiar_ear", minimo=0.0,
            minimo_exclusivo=True)
    _inteiro(piscada["piscada_ms"], "deteccao.piscada.piscada_ms", minimo=1)
    _inteiro(piscada["foco_minimo_ms"], "deteccao.piscada.foco_minimo_ms")

    calib = cfg["calibracao"]
    _inteiro(calib["duracao_ms"], "calibracao.duracao_ms", minimo=1)
    _inteiro(calib["min_amostras"], "calibracao.min_amostras", minimo=1)
    _numero(calib["max_yaw_graus"], "calibracao.max_yaw_graus", minimo=0.0)
    _numero(calib["diferenca_minima"], "calibracao.diferenca_minima", minimo=0.0)

    prancha = cfg["prancha"]
    _numero(prancha["distancia_minima_boa"], "prancha.distancia_minima_boa",
            minimo=0.0, maximo=1.0)
    _numero(prancha["raio_max"], "prancha.raio_max", minimo=0.05,
            maximo=2.0, minimo_exclusivo=True)

    cam = cfg["camera"]
    _inteiro(cam["indice"], "camera.indice")
    _inteiro(cam["largura"], "camera.largura", minimo=1)
    _inteiro(cam["altura"], "camera.altura", minimo=1)
    _inteiro(cam["fps"], "camera.fps", minimo=1)
    if cam["backend"] not in ("auto", "msmf", "dshow", "any"):
        raise ValueError(
            f"camera.backend deve ser auto, msmf, dshow ou any (recebido: {cam['backend']!r})"
        )
    _inteiro(cam["timeout_inicial_ms"], "camera.timeout_inicial_ms", minimo=1000)

    modelo = cfg["modelo"]
    _texto(modelo["caminho"], "modelo.caminho")
    _texto(modelo["url"], "modelo.url")
    if not isinstance(modelo["sha256_esperado"], str):
        raise ValueError("modelo.sha256_esperado deve ser texto")
    if modelo["sha256_esperado"] and len(modelo["sha256_esperado"]) != 64:
        raise ValueError("modelo.sha256_esperado deve ter 64 caracteres (ou ficar vazio)")

    perfis = cfg["perfis"]
    _texto(perfis["pasta"], "perfis.pasta")
    _inteiro(perfis["validade_dias"], "perfis.validade_dias", minimo=1)

    logs = cfg["logs"]
    _texto(logs["pasta"], "logs.pasta")
    _texto(logs["nivel"], "logs.nivel")

    _booleano(cfg["feedback"]["som"], "feedback.som")

    janela = cfg["janela"]
    _texto(janela["titulo"], "janela.titulo")
    _booleano(janela["fullscreen"], "janela.fullscreen")


def _config_padrao() -> dict[str, Any]:
    """Valores de segurança caso o YAML não possa ser lido."""
    return {
        "deteccao": {
            "dwell_ms": 700,
            "tolerancia_perda_ms": 180,
            "exibicao_confirmacao_ms": 1500,
            "alpha_ema": 0.35,
            "tamanho_historico_grafico": 200,
            "limite_frames_sem_rosto": 60,
            "piscada": {
                "habilitada": True,
                "limiar_ear": 0.15,
                "piscada_ms": 350,
                "foco_minimo_ms": 150,
            },
        },
        "calibracao": {
            "duracao_ms": 3000,
            "min_amostras": 30,
            "max_yaw_graus": 25.0,
            "diferenca_minima": 0.03,
        },
        "prancha": {
            "distancia_minima_boa": 0.02,
            "raio_max": 0.55,
        },
        "camera": {
            "indice": 0,
            "largura": 1280,
            "altura": 720,
            "fps": 30,
            "backend": "auto",
            "timeout_inicial_ms": 6000,
        },
        "modelo": {
            "caminho": "models/face_landmarker.task",
            "url": (
                "https://storage.googleapis.com/mediapipe-models/"
                "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
            ),
            "sha256_esperado": "",
        },
        "perfis": {"pasta": "perfis", "validade_dias": 7},
        "logs": {"pasta": "logs", "nivel": "INFO"},
        "feedback": {"som": True},
        "janela": {
            "titulo": "Eye-Tracking Assistivo V2.1 (MediaPipe)",
            "fullscreen": True,
        },
    }
