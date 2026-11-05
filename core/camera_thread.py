"""
Captura de câmera em thread separada.

A câmera roda em sua própria thread, alimentando uma fila de tamanho 1
(sempre o frame mais recente), e o loop principal só consome o que
estiver disponível.

Pontos importantes aprendidos com o diagnóstico em máquinas reais:

  * **Não basta ``isOpened()``**: alguns drivers (sobretudo câmeras UVC
    genéricas no Windows) abrem o dispositivo mas nunca entregam frame.
    Por isso a abertura só é considerada válida depois de receber o
    primeiro frame dentro de um tempo limite.
  * **Vários backends**: no Windows vale tentar MSMF, DirectShow e o
    backend automático, nessa ordem. Um deles costuma funcionar mesmo
    quando o outro falha com ``ERROR_INVALID_HANDLE``.
  * **Fechar antes de reabrir**: abrir uma segunda captura do mesmo
    dispositivo enquanto a primeira continua aberta deixa a câmera em um
    estado inválido no Windows. Aqui a captura antiga é sempre liberada
    antes de abrir a nova.
  * **Espera antes de reconectar**: reconectar a cada segundo impede a
    câmera de aquecer -- muitas precisam de 1 a 3 segundos até o
    primeiro frame. A reconexão usa espera progressiva (backoff).
"""
from __future__ import annotations

import contextlib
import logging
import queue
import threading
import time
from dataclasses import dataclass

import cv2

logger = logging.getLogger("eyetracking.camera")

# Mapa nome amigável -> constante do OpenCV. getattr porque algumas
# builds em Linux/macOS não expõem CAP_MSMF/CAP_DSHOW.
_BACKENDS = {
    "msmf": getattr(cv2, "CAP_MSMF", 1400),
    "dshow": getattr(cv2, "CAP_DSHOW", 700),
    "any": cv2.CAP_ANY,
}

INTERVALO_LEITURA_S = 0.03


class CameraIndisponivelError(RuntimeError):
    """Levantado quando a câmera não pode ser aberta ou não entrega frames."""


def backends_candidatos(nome: str = "auto") -> list[tuple[str, int]]:
    """
    Lista de backends a tentar, em ordem de preferência.

    ``auto`` tenta MSMF, depois DirectShow e por fim o backend padrão.
    Qualquer outro valor precisa ser um nome conhecido.
    """
    nome = (nome or "auto").strip().lower()
    if nome == "auto":
        candidatos = ["msmf", "dshow", "any"]
    else:
        if nome not in _BACKENDS:
            raise ValueError(
                f"Backend de câmera inválido: '{nome}'. "
                f"Use um de: auto, {', '.join(sorted(_BACKENDS))}."
            )
        candidatos = [nome]
    return [(n, _BACKENDS[n]) for n in candidatos]


def _esperar_primeiro_frame(cap, timeout_s: float) -> bool:
    """Tenta ler até receber um frame válido dentro de ``timeout_s``."""
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        try:
            ok, frame = cap.read()
        except cv2.error:
            return False
        if ok and frame is not None and getattr(frame, "size", 0) > 0:
            return True
        # Sem este sleep, um dispositivo que falha na hora gira a CPU.
        time.sleep(INTERVALO_LEITURA_S)
    return False


@dataclass
class ResultadoBackend:
    """Resultado de uma tentativa de abertura (usado no diagnóstico)."""

    backend: str
    abriu: bool
    recebeu_frame: bool
    segundos: float
    erro: str = ""


def abrir_camera(
    indice: int,
    largura: int | None,
    altura: int | None,
    fps: int | None,
    backend: str = "auto",
    timeout_s: float = 6.0,
):
    """
    Abre a câmera testando os backends candidatos.

    Retorna ``(captura, nome_backend)``. Levanta ``CameraIndisponivelError``
    se nenhum backend entregar um frame dentro do tempo total.
    """
    candidatos = backends_candidatos(backend)
    timeout_por_backend = max(0.3, timeout_s / len(candidatos))
    tentativas: list[str] = []

    for nome, api in candidatos:
        captura = cv2.VideoCapture(indice, api)
        if not captura.isOpened():
            captura.release()
            tentativas.append(f"{nome}: não abriu")
            logger.debug("Câmera %d: backend %s não abriu.", indice, nome)
            continue

        if largura:
            captura.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
        if altura:
            captura.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
        if fps:
            captura.set(cv2.CAP_PROP_FPS, fps)

        if _esperar_primeiro_frame(captura, timeout_por_backend):
            logger.info("Câmera %d aberta com backend %s.", indice, nome)
            return captura, nome

        # Fecha ANTES de tentar o próximo backend: dois acessos simultâneos
        # ao mesmo dispositivo costumam invalidar o handle no Windows.
        captura.release()
        tentativas.append(f"{nome}: abriu, mas não entregou frame")
        logger.warning(
            "Câmera %d: backend %s abriu mas não entregou frame em %.1fs.",
            indice, nome, timeout_por_backend,
        )

    raise CameraIndisponivelError(
        f"A câmera de índice {indice} não está entregando imagens.\n\n"
        + "\n".join(f"  - {t}" for t in tentativas)
        + "\n\nVerifique:\n"
        "  1. se a webcam não está em uso por outro programa (Teams, Zoom, "
        "Navegador, app Câmera);\n"
        "  2. se ela aparece em Configurações > Privacidade > Câmera com "
        "acesso permitido;\n"
        "  3. se o cabo/porta USB está firme — tente outra porta;\n"
        "  4. se ela funciona no aplicativo Câmera do Windows."
    )


def diagnosticar_camera(
    indice: int = 0,
    largura: int | None = None,
    altura: int | None = None,
    fps: int | None = None,
    backend: str = "auto",
    timeout_s: float = 2.5,
) -> list[ResultadoBackend]:
    """
    Testa cada backend com o índice informado e relata o que aconteceu.

    Não levanta exceção: serve para o ``--check-camera`` explicar ao
    usuário exatamente onde a captura para.
    """
    resultados: list[ResultadoBackend] = []
    for nome, api in backends_candidatos(backend):
        inicio = time.monotonic()
        captura = None
        try:
            captura = cv2.VideoCapture(indice, api)
            abriu = bool(captura.isOpened())
            if not abriu:
                resultados.append(
                    ResultadoBackend(nome, False, False, time.monotonic() - inicio,
                                     "dispositivo não abriu")
                )
                continue
            if largura:
                captura.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
            if altura:
                captura.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
            if fps:
                captura.set(cv2.CAP_PROP_FPS, fps)
            recebeu = _esperar_primeiro_frame(captura, timeout_s)
            resultados.append(
                ResultadoBackend(
                    nome, True, recebeu, time.monotonic() - inicio,
                    "" if recebeu else f"abriu, mas nenhum frame em {timeout_s:.1f}s",
                )
            )
        except cv2.error as e:
            resultados.append(
                ResultadoBackend(nome, False, False, time.monotonic() - inicio, str(e))
            )
        finally:
            if captura is not None:
                captura.release()
    return resultados


class CameraStream:
    def __init__(
        self,
        indice: int = 0,
        largura: int | None = None,
        altura: int | None = None,
        fps: int | None = None,
        backend: str = "auto",
        timeout_inicial_s: float = 6.0,
        tolerante: bool = False,
    ):
        self.indice = indice
        self.largura = largura
        self.altura = altura
        self.fps = fps
        self.backend = backend
        self.timeout_inicial_s = timeout_inicial_s

        self._lock = threading.Lock()
        try:
            self.cap, self._backend_usado = abrir_camera(
                indice, largura, altura, fps, backend, timeout_inicial_s
            )
        except CameraIndisponivelError as e:
            if not tolerante:
                raise
            # Modo tolerante: segue rodando e mostra a tela de "sem sinal"
            # com instruções, tentando reconectar em segundo plano.
            logger.error("Câmera indisponível na abertura: %s", e)
            self.cap = None
            self._backend_usado = "nenhum"

        self.fila: queue.Queue = queue.Queue(maxsize=1)
        self._rodando = True
        self._ultimo_frame_em: float | None = None
        self._falhas_seguidas = 0
        self._thread = threading.Thread(target=self._capturar, name="camera", daemon=True)
        self._thread.start()
        logger.info("Câmera %d iniciada (backend=%s).", indice, self._backend_usado)

    # -----------------------------------------------------------------
    def _capturar(self) -> None:
        falhas = 0
        espera = 0.5
        while self._rodando:
            with self._lock:
                cap = self.cap

            if cap is None:
                # Nenhum backend funcionou na abertura: tenta de novo,
                # com espera progressiva, em vez de desistir.
                time.sleep(espera)
                espera = min(4.0, espera * 2)
                if self._rodando:
                    self._reconectar()
                continue

            try:
                sucesso, frame = cap.read()
            except cv2.error:
                sucesso, frame = False, None

            if sucesso and frame is not None and getattr(frame, "size", 0) > 0:
                falhas = 0
                espera = 0.5
                self._falhas_seguidas = 0
                self._ultimo_frame_em = time.monotonic()
                self._publicar(frame)
                continue

            falhas += 1
            self._falhas_seguidas = falhas
            # Espera progressiva: 0.5s, 1s, 2s, 4s (máx. 4s) antes de
            # reabrir. Reabrir a cada segundo impede o aquecimento da
            # câmera e trava o dispositivo no Windows.
            espera = min(4.0, espera * 2) if falhas > 1 else 0.5
            logger.debug("Falha de leitura #%d; tentando reabrir em %.1fs.", falhas, espera)
            time.sleep(espera)
            if not self._rodando:
                break
            self._reconectar()

    def _publicar(self, frame) -> None:
        # Mantém sempre só o frame mais recente -- evita acumular atraso.
        with contextlib.suppress(queue.Empty):
            self.fila.get_nowait()
        with contextlib.suppress(queue.Full):
            self.fila.put(frame, timeout=0.5)

    # -----------------------------------------------------------------
    def _reconectar(self) -> None:
        with self._lock:
            antigo = self.cap
            self.cap = None
        # Libera ANTES de abrir de novo (ver docstring do módulo).
        if antigo is not None:
            with contextlib.suppress(Exception):
                antigo.release()

        # Ao reconectar, insiste no backend que já funcionava; se nunca
        # houve um, volta para a configuração original (ex.: "auto").
        backend = self._backend_usado if self._backend_usado != "nenhum" else self.backend
        try:
            novo, backend = abrir_camera(
                self.indice, self.largura, self.altura, self.fps,
                backend, timeout_s=max(2.0, self.timeout_inicial_s),
            )
        except CameraIndisponivelError:
            logger.error("Câmera %d continua sem entregar imagens.", self.indice)
            return
        except ValueError:
            logger.error("Backend '%s' inválido ao reconectar.", self._backend_usado)
            return

        with self._lock:
            self.cap = novo
        if backend != self._backend_usado:
            self._backend_usado = backend
        with contextlib.suppress(queue.Empty):
            self.fila.get_nowait()
        logger.info("Câmera %d reconectada (backend=%s).", self.indice, backend)

    # -----------------------------------------------------------------
    @property
    def backend_em_uso(self) -> str:
        return self._backend_usado

    def segundos_sem_frame(self) -> float:
        """Há quanto tempo nenhum frame chega (infinito se nunca chegou)."""
        if self._ultimo_frame_em is None:
            return float("inf")
        return time.monotonic() - self._ultimo_frame_em

    def ler(self, timeout: float = 0.2):
        """Bloqueia até um frame estar disponível (ou levanta queue.Empty)."""
        return self.fila.get(timeout=timeout)

    def parar(self) -> None:
        self._rodando = False
        self._thread.join(timeout=3.0)
        if self._thread.is_alive():
            logger.warning("Thread da câmera não encerrou a tempo; liberando mesmo assim.")
        with self._lock:
            cap, self.cap = self.cap, None
        if cap is not None:
            with contextlib.suppress(Exception):
                cap.release()
        logger.info("Câmera liberada.")
