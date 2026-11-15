"""
Máquina de estados da aplicação.

Antes: `estado_app = "MENU"` como string solta + várias outras variáveis
globais (contador_fixacao, opcao_focada, etc.) soltas no módulo principal.

Agora: um Enum para os estados (evita erros de digitação tipo "MENU " com
espaço, ou "menu" minúsculo) e uma classe `AppState` que agrupa todo o
estado mutável em um único objeto, fácil de passar entre funções e de
testar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from core.board import IDS_BLOCOS, distancia_minima_entre_pontos


class EstadoApp(Enum):
    MENU = auto()
    ESCOLHER_CALIBRACAO = auto()
    SELECIONAR_PERFIL = auto()
    NOVO_PERFIL = auto()
    CALIB_PREPARAR = auto()
    CALIB_COLETANDO = auto()
    CALIB_CONCLUIDA = auto()
    ATIVO = auto()
    # Prancha de comunicação (modo principal)
    PRANCHA_CALIB_PREPARAR = auto()
    PRANCHA_CALIB_COLETANDO = auto()
    PRANCHA_CALIB_CONCLUIDA = auto()
    PRANCHA_ATIVO = auto()
    # Telas auxiliares do novo design (apenas apresentação)
    MODO_CUIDADOR = auto()
    CONFIGURACOES = auto()


@dataclass
class AppState:
    """Agrupa todo o estado mutável do app em um único objeto."""

    estado: EstadoApp = EstadoApp.MENU
    calib_fase: str = "ESQUERDA"
    coletas_calibracao: list[float] = field(default_factory=list)
    tempo_inicio_coleta: float = 0.0
    amostras_ignoradas: int = 0

    contador_fixacao: int = 0
    opcao_focada: str | None = None
    opcao_confirmada: str | None = None
    tempo_selecionado: float = 0.0

    # Confirmação alternativa por piscada
    contador_piscada: int = 0

    # Perfil / calibração ativa
    perfil_ativo: str | None = None
    media_esquerda_calibrada: float = 0.35
    media_direita_calibrada: float = 0.65
    calibracao_ja_feita: bool = False
    calibracao_fraca: bool = False

    # Prancha de comunicação: uma referência (ratio_x, ratio_y) por bloco
    indice_bloco_calib: int = 0
    coletas_prancha: list[tuple[float, float]] = field(default_factory=list)
    referencias_prancha: dict[str, tuple[float, float]] = field(default_factory=dict)
    tempo_inicio_coleta_prancha: float = 0.0
    prancha_calibrada: bool = False
    prancha_fraca: bool = False

    # Entrada de nome de novo perfil
    nome_digitado: str = ""

    # Aviso temporário na tela (ex.: "calibração fraca")
    aviso: str = ""
    aviso_ate: float = 0.0

    def resetar_selecao(self) -> None:
        self.opcao_focada = None
        self.opcao_confirmada = None
        self.contador_fixacao = 0
        self.contador_piscada = 0
        self.tempo_selecionado = 0.0

    def resetar_calibracao(self) -> None:
        self.calib_fase = "ESQUERDA"
        self.coletas_calibracao = []
        self.tempo_inicio_coleta = 0.0
        self.amostras_ignoradas = 0
        self.calibracao_fraca = False

    def resetar_prancha(self) -> None:
        self.indice_bloco_calib = 0
        self.coletas_prancha = []
        self.referencias_prancha = {}
        self.tempo_inicio_coleta_prancha = 0.0
        self.prancha_calibrada = False
        self.prancha_fraca = False

    def bloco_calib_atual(self) -> str:
        """Id do bloco que está sendo calibrado agora."""
        indice = min(max(self.indice_bloco_calib, 0), len(IDS_BLOCOS) - 1)
        return IDS_BLOCOS[indice]

    def prancha_valida(self, distancia_minima_boa: float) -> bool:
        """Prancha utilizável: calibrada, sem flag de fraca e com pontos separados."""
        if (
            not self.prancha_calibrada
            or self.prancha_fraca
            or len(self.referencias_prancha) < len(IDS_BLOCOS)
        ):
            return False
        return (
            distancia_minima_entre_pontos(self.referencias_prancha)
            >= distancia_minima_boa
        )

    def calibracao_valida(self, diferenca_minima: float) -> bool:
        """Calibração utilizável: existe, foi concluída e separa SIM/NAO."""
        return (
            self.calibracao_ja_feita
            and not self.calibracao_fraca
            and abs(self.media_direita_calibrada - self.media_esquerda_calibrada)
            >= diferenca_minima
        )

    def avisar(self, texto: str, agora: float, duracao: float = 3.0) -> None:
        self.aviso = texto
        self.aviso_ate = agora + duracao

    def aviso_ativo(self, agora: float) -> bool:
        return bool(self.aviso) and agora < self.aviso_ate

    def transicionar(self, novo_estado: EstadoApp) -> None:
        """Ponto único de transição (o chamador registra no log)."""
        self.estado = novo_estado
