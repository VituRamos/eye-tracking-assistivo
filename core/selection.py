"""
Controlador puro de seleção SIM/NÃO (dwell time + piscada).

A lógica de decisão antes vivia espalhada no loop de ``main.py`` e não
podia ser testada sem câmera. Aqui ela é isolada: o controlador recebe
apenas (opção focada, olho fechado, instante) e devolve o progresso e a
eventual confirmação. Nenhuma dependência de OpenCV/MediaPipe.

Melhorias em relação ao comportamento anterior:
  * dwell por TEMPO (ms), não por contagem de frames -- não muda de
    comportamento se o FPS da câmera oscilar;
  * tolerância a perdas curtas de foco: um frame de ruído não zera todo
    o progresso (importante para usuários com tremor ocular);
  * piscada exige tempo mínimo de olho fechado e foco já estabilizado;
  * confirmação exibida por um período fixo e depois liberada.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisaoSelecao:
    """Resultado de um passo do controlador."""

    opcao_focada: str | None = None
    opcao_confirmada: str | None = None
    progresso: float = 0.0
    metodo: str | None = None


class ControladorSelecao:
    """
    Controlador com tempo injetado (``agora`` em segundos).

    Args:
        dwell_ms: tempo contínuo de foco para confirmar por olhar fixo.
        tolerancia_perda_ms: perda máxima de foco tolerada sem zerar o dwell.
        piscada_habilitada: se a piscada também confirma.
        piscada_ms: tempo mínimo de olho fechado para contar como confirmação.
        foco_minimo_ms: tempo mínimo de foco antes de aceitar a piscada
            (evita confirmar ao piscar assim que o olhar chega na opção).
        exibicao_confirmacao_ms: por quanto tempo a confirmação fica na tela.
    """

    def __init__(
        self,
        dwell_ms: int = 700,
        tolerancia_perda_ms: int = 180,
        piscada_habilitada: bool = True,
        piscada_ms: int = 350,
        foco_minimo_ms: int = 150,
        exibicao_confirmacao_ms: int = 1500,
    ) -> None:
        if dwell_ms <= 0:
            raise ValueError("dwell_ms deve ser maior que zero")
        if tolerancia_perda_ms < 0:
            raise ValueError("tolerancia_perda_ms não pode ser negativo")
        if piscada_ms <= 0:
            raise ValueError("piscada_ms deve ser maior que zero")
        if foco_minimo_ms < 0:
            raise ValueError("foco_minimo_ms não pode ser negativo")
        if exibicao_confirmacao_ms <= 0:
            raise ValueError("exibicao_confirmacao_ms deve ser maior que zero")

        self.dwell_ms = dwell_ms
        self.tolerancia_perda_ms = tolerancia_perda_ms
        self.piscada_habilitada = piscada_habilitada
        self.piscada_ms = piscada_ms
        self.foco_minimo_ms = foco_minimo_ms
        self.exibicao_confirmacao_ms = exibicao_confirmacao_ms
        self.reset()

    def reset(self) -> None:
        self.opcao_focada: str | None = None
        self.opcao_confirmada: str | None = None
        self.metodo: str | None = None
        self._acumulado_ms = 0.0
        self._ultimo_foco: float | None = None
        self._inicio_piscada: float | None = None
        self._confirmada_em: float | None = None

    # -----------------------------------------------------------------
    def atualizar(
        self, opcao: str | None, olho_fechado: bool, agora: float
    ) -> DecisaoSelecao:
        """
        Avança um passo.

        ``opcao`` deve ser a opção atualmente focada (ou None quando o
        olhar está no centro / rosto ausente / pose inválida).
        ``agora`` deve ser um relógio monotônico em segundos.
        """
        if self.opcao_confirmada is not None:
            return self._decisao()

        self._atualizar_piscada(opcao, olho_fechado, agora)
        if self.opcao_confirmada is not None:
            return self._decisao()

        # Olhos fechados pausam o dwell (a íris fica instável durante a
        # piscada), mas preservam o foco para a confirmação por piscada.
        self._atualizar_dwell(opcao, agora, pausar=olho_fechado and opcao is not None)

        if self.opcao_focada is not None and self._acumulado_ms >= self.dwell_ms:
            return self._confirmar(agora, "dwell")

        return self._decisao()

    # -----------------------------------------------------------------
    def deve_limpar_confirmacao(self, agora: float) -> bool:
        """True quando a confirmação já foi exibida pelo tempo configurado."""
        return (
            self._confirmada_em is not None
            and (agora - self._confirmada_em) * 1000 >= self.exibicao_confirmacao_ms
        )

    # -----------------------------------------------------------------
    def _atualizar_piscada(
        self, opcao: str | None, olho_fechado: bool, agora: float
    ) -> None:
        foco_estavel = (
            opcao is not None
            and opcao == self.opcao_focada
            and self._acumulado_ms >= self.foco_minimo_ms
        )
        if not self.piscada_habilitada or not foco_estavel:
            self._inicio_piscada = None
            return

        if not olho_fechado:
            self._inicio_piscada = None
            return

        if self._inicio_piscada is None:
            self._inicio_piscada = agora
            return

        if (agora - self._inicio_piscada) * 1000 >= self.piscada_ms:
            self._confirmar(agora, "piscada")

    def _atualizar_dwell(self, opcao: str | None, agora: float, pausar: bool = False) -> None:
        if pausar:
            # Mantém o progresso, mas não conta o tempo de olho fechado.
            if self._ultimo_foco is not None:
                self._ultimo_foco = agora
            return

        if opcao is None:
            # Perda curta de foco é tolerada; uma perda longa zera o dwell.
            if (
                self._ultimo_foco is None
                or (agora - self._ultimo_foco) * 1000 > self.tolerancia_perda_ms
            ):
                self.opcao_focada = None
                self._acumulado_ms = 0.0
                self._ultimo_foco = None
            return

        if opcao != self.opcao_focada:
            self.opcao_focada = opcao
            self._acumulado_ms = 0.0
            self._ultimo_foco = agora
            return

        if self._ultimo_foco is not None:
            # Limita o delta para não "ganhar" dwell após uma pausa longa
            # (ex.: janela minimizada ou frame perdido).
            delta_ms = min(max((agora - self._ultimo_foco) * 1000, 0.0), 250.0)
            self._acumulado_ms += delta_ms
        self._ultimo_foco = agora

    def _confirmar(self, agora: float, metodo: str) -> DecisaoSelecao:
        self.opcao_confirmada = self.opcao_focada
        self.metodo = metodo
        self._confirmada_em = agora
        self._inicio_piscada = None
        return self._decisao()

    def _decisao(self) -> DecisaoSelecao:
        if self.opcao_confirmada is not None:
            return DecisaoSelecao(
                opcao_focada=self.opcao_focada,
                opcao_confirmada=self.opcao_confirmada,
                progresso=1.0,
                metodo=self.metodo,
            )
        progresso = 0.0
        if self.opcao_focada is not None:
            progresso = min(self._acumulado_ms / self.dwell_ms, 1.0)
        return DecisaoSelecao(
            opcao_focada=self.opcao_focada,
            opcao_confirmada=None,
            progresso=progresso,
            metodo=None,
        )
