"""Testes de integração da recentralização do olhar (motor em simulação).

O motor é iniciado sem câmera (``simular=True``) e com uma pasta de dados
temporária. Assim dá para testar o comando que a interface envia sem
depender de webcam, MediaPipe ou do perfil real do usuário.
"""
from __future__ import annotations

import argparse

import pytest

from ponte import Motor

REFERENCIAS = {
    "oi": (0.30, 0.30),
    "comer": (0.70, 0.30),
    "beber": (0.30, 0.70),
    "banheiro": (0.70, 0.70),
}


@pytest.fixture
def motor(tmp_path):
    args = argparse.Namespace(simular=True, dados=str(tmp_path), config=None)
    m = Motor(args)
    m.feedback.habilitado = False
    m.app.perfil_ativo = "padrao"
    m.app.referencias_prancha = dict(REFERENCIAS)
    return m


class TestRecentralizacao:
    def test_move_todos_os_pontos_e_persiste(self, motor):
        motor.recentralizar_prancha(0.02, -0.03, agora=10.0)

        assert motor.app.referencias_prancha["oi"] == pytest.approx((0.32, 0.27))
        assert motor.app.referencias_prancha["banheiro"] == pytest.approx(
            (0.72, 0.67)
        )
        assert motor._recentralizacao_anterior is not None

        salvo = motor.prancha_gerenciador.carregar("padrao")
        assert salvo is not None
        assert salvo["alvos"]["oi"] == pytest.approx([0.32, 0.27])

    def test_desfazer_restaura_e_persiste_o_estado_anterior(self, motor):
        motor.recentralizar_prancha(0.02, 0.02, agora=10.0)
        motor.desfazer_recentralizacao(agora=11.0)

        assert motor.app.referencias_prancha == pytest.approx(REFERENCIAS)
        assert motor._recentralizacao_anterior is None

        salvo = motor.prancha_gerenciador.carregar("padrao")
        assert salvo is not None
        assert salvo["alvos"]["oi"] == pytest.approx([0.30, 0.30])

    def test_recusa_ajuste_que_sairia_da_area(self, motor):
        motor.recentralizar_prancha(0.50, 0.0, agora=10.0)

        assert motor.app.referencias_prancha == pytest.approx(REFERENCIAS)
        assert motor._recentralizacao_anterior is None

    def test_exige_prancha_completa(self, motor):
        motor.app.referencias_prancha = {"oi": (0.30, 0.30)}

        motor.recentralizar_prancha(0.02, 0.02, agora=10.0)

        assert motor.app.referencias_prancha == {"oi": (0.30, 0.30)}
        assert motor._recentralizacao_anterior is None


class TestSnapshotRecentralizacao:
    def test_snapshot_expoe_estado_da_recentralizacao(self, motor):
        antes = motor._snapshot(1.0)
        assert antes["podeDesfazerRecentralizacao"] is False

        motor.recentralizar_prancha(0.01, 0.01, agora=2.0)
        depois = motor._snapshot(3.0)
        assert depois["podeDesfazerRecentralizacao"] is True

    def test_snapshot_expoe_aviso_de_distancia_no_modo_cuidador(self, motor):
        from core.state_machine import EstadoApp

        motor.app.transicionar(EstadoApp.MODO_CUIDADOR)
        motor.distancia_rosto = 0.20
        motor.distancia_estado = "boa"
        motor.distancia_aviso = True

        snapshot = motor._snapshot(1.0)

        assert snapshot["distanciaRosto"] == pytest.approx(0.20)
        assert snapshot["distanciaEstado"] == "boa"
        assert snapshot["distanciaAviso"] is True


class TestRetencaoExibicao:
    """O status e o ponto não podem piscar quando o detector perde o rosto."""

    def _quadro_valido(self, motor, monkeypatch, agora=100.0):
        motor.simulador = False
        motor.rosto_detectado = True
        motor.pose_confiavel = True
        motor.olhos_fechados = False
        motor.divergencia_ok = True
        motor.ratio_valido = 0.62
        motor.ratio_y_valido = 0.44
        motor.distancia_estado = "boa"
        motor.distancia_rosto = 0.20
        monkeypatch.setattr("ponte.time.monotonic", lambda: agora)
        motor._memorizar_rastreamento()

    def test_segura_rosto_e_ponto_por_pouco_tempo(self, motor, monkeypatch):
        self._quadro_valido(motor, monkeypatch)

        # Quadro seguinte sem rosto: o motor volta aos valores neutros.
        motor.rosto_detectado = False
        motor.ratio_valido = 0.5
        motor.ratio_y_valido = 0.5
        motor.distancia_estado = "indefinida"

        retido = motor._snapshot(100.4)
        assert retido["rostoOk"] is True
        assert retido["gaze"]["valido"] is True
        assert retido["gaze"]["x"] == pytest.approx(0.62)
        assert retido["gaze"]["y"] == pytest.approx(0.44)
        assert retido["distanciaEstado"] == "boa"

        # Depois da janela de retenção, o status volta a "sem rosto".
        assert motor._snapshot(101.0)["rostoOk"] is False

    def test_retencao_nao_usa_ponto_de_piscada(self, motor, monkeypatch):
        self._quadro_valido(motor, monkeypatch)
        motor.olhos_fechados = True
        motor.ratio_valido = 0.10
        motor._memorizar_rastreamento()

        assert motor._gaze_exibicao[0] == pytest.approx(0.62)

    def test_piscada_curta_nao_mostra_olhos_fechados(self, motor):
        motor.olhos_fechados = True
        motor._olhos_fechados_desde = 10.0

        assert motor._snapshot(10.12)["olhosFechados"] is False
        assert motor._snapshot(10.60)["olhosFechados"] is True
