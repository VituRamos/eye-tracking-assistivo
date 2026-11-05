"""Testes dos helpers de câmera (sem hardware real)."""
import cv2
import numpy as np
import pytest

from core import camera_thread
from core.camera_thread import (
    CameraIndisponivelError,
    CameraStream,
    abrir_camera,
    backends_candidatos,
    diagnosticar_camera,
)


class FakeCap:
    """Imita cv2.VideoCapture: abre, entrega N frames e depois falha."""

    def __init__(self, aberto=True, frames=0, eventos=None, nome="cap"):
        self.aberto = aberto
        self.frames = frames
        self.eventos = eventos if eventos is not None else []
        self.nome = nome
        self.released = False

    def isOpened(self):
        return self.aberto

    def set(self, *_args):
        return True

    def read(self):
        if self.frames > 0:
            self.frames -= 1
            return True, np.zeros((4, 4, 3), dtype=np.uint8)
        return False, None

    def release(self):
        self.released = True
        self.eventos.append(("release", self.nome))


class TestBackends:
    def test_auto_tenta_msmf_dshow_e_any(self):
        nomes = [n for n, _ in backends_candidatos("auto")]
        assert nomes == ["msmf", "dshow", "any"]

    def test_auto_com_maiusculas(self):
        assert next(n for n, _ in backends_candidatos("AUTO")) == "msmf"

    def test_backend_especifico(self):
        assert [n for n, _ in backends_candidatos("dshow")] == ["dshow"]

    def test_backend_invalido_levanta_erro(self):
        with pytest.raises(ValueError, match="Backend de câmera inválido"):
            backends_candidatos("webcam-magica")


class TestAbrirCamera:
    def test_usa_primeiro_backend_que_entrega_frame(self, monkeypatch):
        abertas = []

        def fabrica(indice, api):
            cap = FakeCap(frames=1 if api == camera_thread._BACKENDS["dshow"] else 0)
            abertas.append(cap)
            return cap

        monkeypatch.setattr(cv2, "VideoCapture", fabrica)
        cap, backend = abrir_camera(0, None, None, None, timeout_s=1.0)
        assert backend == "dshow"
        assert cap.isOpened()
        # O backend que não entregou frame precisa ter sido liberado.
        assert abertas[0].released is True

    def test_falha_quando_nenhum_backend_entrega(self, monkeypatch):
        monkeypatch.setattr(cv2, "VideoCapture", lambda *a: FakeCap(frames=0))
        with pytest.raises(CameraIndisponivelError) as info:
            abrir_camera(0, None, None, None, timeout_s=0.6)
        mensagem = str(info.value)
        assert "não está entregando imagens" in mensagem
        assert "msmf" in mensagem
        assert "dshow" in mensagem

    def test_backend_que_nao_abre_e_registrado(self, monkeypatch):
        monkeypatch.setattr(cv2, "VideoCapture", lambda *a: FakeCap(aberto=False))
        with pytest.raises(CameraIndisponivelError, match="não abriu"):
            abrir_camera(0, None, None, None, timeout_s=0.6)


class TestDiagnostico:
    def test_relata_cada_backend(self, monkeypatch):
        def fabrica(indice, api):
            if api == camera_thread._BACKENDS["msmf"]:
                return FakeCap(frames=1)
            return FakeCap(aberto=False)

        monkeypatch.setattr(cv2, "VideoCapture", fabrica)
        resultados = diagnosticar_camera(0, timeout_s=0.3)

        por_nome = {r.backend: r for r in resultados}
        assert por_nome["msmf"].recebeu_frame is True
        assert por_nome["dshow"].abriu is False
        assert por_nome["any"].abriu is False
        assert "não abriu" in por_nome["dshow"].erro


class TestModoTolerante:
    def test_nao_levanta_e_reporta_sem_frame(self, monkeypatch):
        monkeypatch.setattr(cv2, "VideoCapture", lambda *a: FakeCap(frames=0))
        camera = CameraStream(
            0, None, None, None, backend="msmf",
            timeout_inicial_s=0.3, tolerante=True,
        )
        try:
            assert camera.backend_em_uso == "nenhum"
            assert camera.segundos_sem_frame() == float("inf")
        finally:
            camera.parar()

    def test_sem_tolerancia_levanta(self, monkeypatch):
        monkeypatch.setattr(cv2, "VideoCapture", lambda *a: FakeCap(aberto=False))
        with pytest.raises(CameraIndisponivelError):
            CameraStream(0, None, None, None, backend="msmf", timeout_inicial_s=0.3)
