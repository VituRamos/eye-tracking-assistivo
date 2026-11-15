"""
Testes unitários das funções puras de core/gaze_engine.py.

Como essas funções não dependem de câmera nem de MediaPipe rodando de
verdade, usamos objetos falsos (FakeLandmark) só com os atributos .x/.y
que as funções esperam. Isso permite testar toda a lógica de cálculo
sem precisar de uma webcam nem de um rosto real.

Rode com: pytest tests/
"""
from dataclasses import dataclass

import numpy as np
import pytest

from core.gaze_engine import (
    DISTANCIA_BOA,
    DISTANCIA_INDEFINIDA,
    DISTANCIA_LONGE,
    DISTANCIA_PERTO,
    SuavizadorEMA,
    calcular_ear,
    calcular_ratio_iris_x,
    classificar_distancia,
    classificar_lado,
    compensar_ratio_por_yaw,
    distancia_rosto_normalizada,
    divergencia_dentro_do_limite,
    divergencia_entre_olhos,
    extrair_angulos_da_matriz,
    extrair_yaw_da_matriz,
    olho_fechado,
    pose_dentro_dos_limites,
)


@dataclass
class FakeLandmark:
    x: float
    y: float


def montar_landmarks_olho(x_canto_esq, x_canto_dir, x_iris, y=0.5):
    """
    Monta um dicionário simulando os landmarks do MediaPipe para um olho,
    usando os mesmos índices reais (33/133 do olho direito, por exemplo),
    mas preenchendo só o que os testes precisam.
    """
    indices_iris = [469, 470, 471, 472]
    landmarks = {33: FakeLandmark(x_canto_esq, y), 133: FakeLandmark(x_canto_dir, y)}
    for i in indices_iris:
        landmarks[i] = FakeLandmark(x_iris, y)
    return landmarks


# =====================================================================
# classificar_lado
# =====================================================================
class TestClassificarLado:
    def test_classifica_esquerda_quando_ratio_baixo(self):
        assert classificar_lado(0.2, media_esq=0.3, media_dir=0.7) == "Esquerda"

    def test_classifica_direita_quando_ratio_alto(self):
        assert classificar_lado(0.8, media_esq=0.3, media_dir=0.7) == "Direita"

    def test_zona_morta_retorna_centro(self):
        # Bem no meio do intervalo calibrado -> deve cair na zona morta
        assert classificar_lado(0.5, media_esq=0.3, media_dir=0.7) == "Centro"

    def test_funciona_com_calibracao_invertida(self):
        # Se por algum motivo o SIM ficou calibrado com ratio maior que o NAO,
        # a classificação ainda deve respeitar qual lado é qual.
        assert classificar_lado(0.8, media_esq=0.7, media_dir=0.3) == "Esquerda"


# =====================================================================
# calcular_ratio_iris_x
# =====================================================================
class TestCalcularRatioIrisX:
    def test_iris_no_centro_do_olho(self):
        largura, altura = 640, 480
        landmarks = montar_landmarks_olho(
            x_canto_esq=0.3, x_canto_dir=0.4, x_iris=0.35,
        )
        ratio = calcular_ratio_iris_x(landmarks, (33, 133), [469, 470, 471, 472], largura, altura)
        assert ratio == pytest.approx(0.5, abs=0.01)

    def test_ratio_fica_limitado_entre_0_e_1(self):
        largura, altura = 640, 480
        # íris "fora" do olho (situação anômala) não deve estourar os limites
        landmarks = montar_landmarks_olho(x_canto_esq=0.3, x_canto_dir=0.4, x_iris=0.9)
        ratio = calcular_ratio_iris_x(landmarks, (33, 133), [469, 470, 471, 472], largura, altura)
        assert 0.0 <= ratio <= 1.0


# =====================================================================
# SuavizadorEMA
# =====================================================================
class TestSuavizadorEMA:
    def test_primeiro_valor_e_usado_diretamente(self):
        suavizador = SuavizadorEMA(alpha=0.3)
        assert suavizador.atualizar(0.5) == pytest.approx(0.5)

    def test_converge_para_valor_constante(self):
        suavizador = SuavizadorEMA(alpha=0.5)
        for _ in range(50):
            valor = suavizador.atualizar(0.8)
        assert valor == pytest.approx(0.8, abs=1e-6)

    def test_reset_limpa_estado(self):
        suavizador = SuavizadorEMA(alpha=0.5)
        suavizador.atualizar(0.9)
        suavizador.reset()
        assert suavizador.valor is None

    def test_alpha_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            SuavizadorEMA(alpha=0.0)
        with pytest.raises(ValueError):
            SuavizadorEMA(alpha=1.5)


# =====================================================================
# EAR / piscada
# =====================================================================
class TestEAR:
    def test_olho_bem_aberto_nao_conta_como_fechado(self):
        landmarks = {
            159: FakeLandmark(0.5, 0.40),
            145: FakeLandmark(0.5, 0.48),
            33: FakeLandmark(0.45, 0.44),
            133: FakeLandmark(0.55, 0.44),
        }
        ear = calcular_ear(landmarks, (159, 145), (33, 133), largura=640, altura=480)
        assert not olho_fechado(ear, limiar=0.15)

    def test_olho_quase_fechado_conta_como_fechado(self):
        landmarks = {
            159: FakeLandmark(0.5, 0.440),
            145: FakeLandmark(0.5, 0.442),
            33: FakeLandmark(0.45, 0.441),
            133: FakeLandmark(0.55, 0.441),
        }
        ear = calcular_ear(landmarks, (159, 145), (33, 133), largura=640, altura=480)
        assert olho_fechado(ear, limiar=0.15)


# =====================================================================
# Compensação de pose de cabeça
# =====================================================================
class TestCompensacaoPose:
    def test_matriz_identidade_da_yaw_zero(self):
        matriz = np.eye(4)
        yaw = extrair_yaw_da_matriz(matriz)
        assert yaw == pytest.approx(0.0, abs=1e-6)

    def test_compensar_ratio_com_yaw_zero_nao_altera_valor(self):
        ratio_ajustado = compensar_ratio_por_yaw(0.5, yaw_graus=0.0)
        assert ratio_ajustado == pytest.approx(0.5)

    def test_compensar_ratio_com_yaw_positivo_desloca_valor(self):
        ratio_ajustado = compensar_ratio_por_yaw(0.5, yaw_graus=20.0, sensibilidade=0.004)
        assert ratio_ajustado < 0.5

    @staticmethod
    def _rotacao(eixo: str, graus: float) -> np.ndarray:
        rad = np.radians(graus)
        c, s = np.cos(rad), np.sin(rad)
        if eixo == "y":
            return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])
        if eixo == "x":
            return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]])
        return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

    def test_matriz_identidade_devolve_tres_angulos_zero(self):
        yaw, pitch, roll = extrair_angulos_da_matriz(np.eye(4))
        assert yaw == pytest.approx(0.0, abs=1e-6)
        assert pitch == pytest.approx(0.0, abs=1e-6)
        assert roll == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.parametrize("angulo", [-25, -10, 0, 10, 25])
    def test_yaw_sintetico(self, angulo):
        yaw, pitch, roll = extrair_angulos_da_matriz(self._rotacao("y", angulo))
        assert yaw == pytest.approx(angulo, abs=1e-6)
        assert pitch == pytest.approx(0.0, abs=1e-6)
        assert roll == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.parametrize("angulo", [-20, -8, 8, 20])
    def test_pitch_sintetico(self, angulo):
        yaw, pitch, roll = extrair_angulos_da_matriz(self._rotacao("x", angulo))
        assert yaw == pytest.approx(0.0, abs=1e-6)
        assert pitch == pytest.approx(angulo, abs=1e-6)
        assert roll == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.parametrize("angulo", [-30, -12, 12, 30])
    def test_roll_sintetico(self, angulo):
        yaw, pitch, roll = extrair_angulos_da_matriz(self._rotacao("z", angulo))
        assert yaw == pytest.approx(0.0, abs=1e-6)
        assert pitch == pytest.approx(0.0, abs=1e-6)
        assert roll == pytest.approx(angulo, abs=1e-6)

    def test_pose_dentro_dos_limites_aceita_pose_pequena(self):
        assert pose_dentro_dos_limites(10, 8, 12, 25, 25, 30) is True

    @pytest.mark.parametrize(
        ("yaw", "pitch", "roll"),
        [(30, 0, 0), (0, 30, 0), (0, 0, 40), (-30, 0, 0), (0, -30, 0), (0, 0, -40)],
    )
    def test_pose_fora_dos_limites_rejeita(self, yaw, pitch, roll):
        assert pose_dentro_dos_limites(yaw, pitch, roll, 25, 25, 30) is False

    def test_limite_zero_desliga_a_checagem_do_eixo(self):
        assert pose_dentro_dos_limites(80, 80, 80, 0, 0, 0) is True


# =====================================================================
# Divergência entre os olhos -- confiança do quadro
# =====================================================================
class TestDivergenciaEntreOlhos:
    @pytest.mark.parametrize(
        ("esq", "dir", "esperado"),
        [
            (0.5, 0.5, 0.0),
            (0.4, 0.6, 0.2),
            (0.7, 0.3, 0.4),
            (0.0, 1.0, 1.0),
        ],
    )
    def test_diferenca_absoluta(self, esq, dir, esperado):
        assert divergencia_entre_olhos(esq, dir) == pytest.approx(esperado)

    def test_dentro_do_limite_aceita_olhos_proximos(self):
        assert divergencia_dentro_do_limite(0.48, 0.52, limite=0.25) is True

    def test_acima_do_limite_rejeita_quadro(self):
        assert divergencia_dentro_do_limite(0.2, 0.8, limite=0.25) is False

    def test_limite_maior_aceita_estrabismo_consistente(self):
        assert divergencia_dentro_do_limite(0.2, 0.8, limite=0.7) is True

    def test_limite_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            divergencia_dentro_do_limite(0.5, 0.5, limite=0.0)
        with pytest.raises(ValueError):
            divergencia_dentro_do_limite(0.5, 0.5, limite=-0.1)


# =====================================================================
# Distância do rosto até a câmera (indicador informativo)
# =====================================================================
def montar_landmarks_olhos(x_dir=0.35, x_esq=0.55, y=0.5):
    """Landmarks mínimos com os cantos externos dos dois olhos."""
    return {
        33: FakeLandmark(x_dir, y),
        263: FakeLandmark(x_esq, y),
    }


class TestDistanciaRosto:
    def test_medida_e_a_distancia_entre_os_cantos_externos(self):
        landmarks = montar_landmarks_olhos(x_dir=0.30, x_esq=0.50)
        medida = distancia_rosto_normalizada(landmarks, 1280, 720)
        assert medida == pytest.approx(0.20)

    def test_rosto_mais_longe_tem_medida_menor(self):
        perto = distancia_rosto_normalizada(
            montar_landmarks_olhos(x_dir=0.20, x_esq=0.60), 1280, 720
        )
        longe = distancia_rosto_normalizada(
            montar_landmarks_olhos(x_dir=0.35, x_esq=0.55), 1280, 720
        )
        assert longe < perto

    def test_yaw_encurta_e_a_compensacao_recupera(self):
        landmarks = montar_landmarks_olhos(x_dir=0.30, x_esq=0.50)
        sem_yaw = distancia_rosto_normalizada(landmarks, 1280, 720, 0.0)
        cabeça_virada = dict(landmarks)
        # Simula o encurtamento horizontal causado por 30 graus de yaw.
        cabeça_virada[263] = FakeLandmark(0.30 + 0.20 * np.cos(np.radians(30)), 0.5)
        com_yaw = distancia_rosto_normalizada(cabeça_virada, 1280, 720, 30.0)
        assert com_yaw == pytest.approx(sem_yaw, rel=1e-6)

    def test_yaw_extremo_nao_divide_por_zero(self):
        landmarks = montar_landmarks_olhos(x_dir=0.49, x_esq=0.51)
        medida = distancia_rosto_normalizada(landmarks, 1280, 720, 89.0)
        assert medida > 0


class TestClassificarDistancia:
    @pytest.mark.parametrize(
        ("medida", "esperado"),
        [
            (0.05, DISTANCIA_LONGE),
            (0.10, DISTANCIA_LONGE),
            (0.11, DISTANCIA_BOA),
            (0.20, DISTANCIA_BOA),
            (0.34, DISTANCIA_BOA),
            (0.35, DISTANCIA_PERTO),
            (0.60, DISTANCIA_PERTO),
        ],
    )
    def test_faixas(self, medida, esperado):
        assert classificar_distancia(medida, 0.11, 0.34) == esperado

    def test_limites_invertidos_ficam_indefinidos(self):
        assert classificar_distancia(0.2, 0.40, 0.30) == DISTANCIA_INDEFINIDA
        assert classificar_distancia(0.2, 0.0, 0.30) == DISTANCIA_INDEFINIDA
