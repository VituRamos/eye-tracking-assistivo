"""
Feedback sonoro curto para confirmações do sistema assistivo.

Um usuário que depende do olhar não tem como perceber com segurança uma
seleção apenas por uma mudança de cor na tela. Um bipe curto na
confirmação (e um som mais grave em erro) melhora muito a usabilidade
sem adicionar dependências: no Windows usamos ``winsound`` (stdlib).
"""
from __future__ import annotations

import logging
import sys
import threading

logger = logging.getLogger("eyetracking.feedback")


class FeedbackSonoro:
    def __init__(self, habilitado: bool = True):
        self.habilitado = habilitado

    def confirmar(self) -> None:
        self._tocar(880, 120)

    def erro(self) -> None:
        self._tocar(220, 300)

    def _tocar(self, frequencia: int, duracao_ms: int) -> None:
        if not self.habilitado:
            return
        # Bipe em thread separada para não travar o loop de vídeo.
        threading.Thread(
            target=self._beep, args=(frequencia, duracao_ms), daemon=True
        ).start()

    @staticmethod
    def _beep(frequencia: int, duracao_ms: int) -> None:
        try:
            if sys.platform == "win32":
                import winsound

                winsound.Beep(frequencia, duracao_ms)
            else:
                sys.stdout.write("\a")
                sys.stdout.flush()
        except Exception as e:  # noqa: BLE001 - som é acessório, nunca deve derrubar o app
            logger.debug("Não foi possível emitir o som: %s", e)
