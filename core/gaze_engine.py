"""
Motor de cálculo de gaze (rastreamento de olhar).

Todas as funções aqui são PURAS: recebem landmarks + números, devolvem
números. Nenhuma função desenha nada com OpenCV e nenhuma depende de
câmera -- por isso são fáceis de testar com dados falsos (ver
tests/test_gaze_engine.py).

A camada de desenho/debug (recorte da região do olho, retângulos, etc.)
fica em ui/renderer_cv2.py.
"""
from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------
# Índices oficiais do MediaPipe Face Mesh (canônicos, não mudam entre rostos)
# ---------------------------------------------------------------------
OLHO_DIREITO_CANTOS = (33, 133)     # (canto externo, canto interno) do olho direito
OLHO_ESQUERDO_CANTOS = (362, 263)   # (canto interno, canto externo) do olho esquerdo
IRIS_DIREITA = [469, 470, 471, 472]
IRIS_ESQUERDA = [474, 475, 476, 477]

# Pontos de pálpebra superior/inferior, usados para EAR (piscada) e ratio_y
OLHO_DIREITO_VERTICAL = (159, 145)
OLHO_ESQUERDO_VERTICAL = (386, 374)


# =====================================================================
# Ratio horizontal (posição da íris dentro do olho)
# =====================================================================
def calcular_ratio_iris_x(landmarks, indices_cantos, indices_iris, largura, altura) -> float:
    """
    Retorna a posição horizontal da íris DENTRO da largura real daquele olho.
    0.0 = encostada no canto A, 1.0 = encostada no canto B.
    """
    p1 = landmarks[indices_cantos[0]]
    p2 = landmarks[indices_cantos[1]]
    x1_px, x2_px = p1.x * largura, p2.x * largura

    xs_iris = [landmarks[i].x * largura for i in indices_iris]
    iris_cx = float(np.mean(xs_iris))

    x_esq, x_dir = min(x1_px, x2_px), max(x1_px, x2_px)
    largura_olho = max(x_dir - x_esq, 1e-3)

    ratio = (iris_cx - x_esq) / largura_olho
    return min(max(ratio, 0.0), 1.0)


def calcular_ratio_iris_y(landmarks, indices_verticais, indices_iris, largura, altura) -> float:
    """
    Equivalente vertical do ratio_x. Abre caminho para uma grade 2D
    (não só SIM/NAO), útil para evoluir para um teclado por varredura.
    """
    p_sup = landmarks[indices_verticais[0]]
    p_inf = landmarks[indices_verticais[1]]
    y_sup, y_inf = p_sup.y * altura, p_inf.y * altura

    ys_iris = [landmarks[i].y * altura for i in indices_iris]
    iris_cy = float(np.mean(ys_iris))

    y_topo, y_base = min(y_sup, y_inf), max(y_sup, y_inf)
    altura_olho = max(y_base - y_topo, 1e-3)

    ratio = (iris_cy - y_topo) / altura_olho
    return min(max(ratio, 0.0), 1.0)


# =====================================================================
# Suavização -- EMA no lugar da média móvel simples
# =====================================================================
class SuavizadorEMA:
    """
    Suavização exponencial (Exponential Moving Average).

    Comparado à média móvel simples usada antes (`np.mean` de uma janela
    de N frames), o EMA reage mais rápido a mudanças reais de olhar
    (menos atraso perceptível) e ainda reduz o tremor frame a frame,
    porque dá peso maior às amostras recentes sem descartar o histórico.

    alpha próximo de 1.0 = quase sem suavização (responsivo, mais tremido)
    alpha próximo de 0.0 = muito suave (estável, mas com mais atraso)
    """

    def __init__(self, alpha: float = 0.35):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha deve estar entre 0 (exclusive) e 1 (inclusive)")
        self.alpha = alpha
        self.valor: float | None = None

    def atualizar(self, novo_valor: float) -> float:
        if self.valor is None:
            self.valor = novo_valor
        else:
            self.valor = self.alpha * novo_valor + (1 - self.alpha) * self.valor
        return self.valor

    def reset(self) -> None:
        self.valor = None


# =====================================================================
# Classificação esquerda/direita/centro
# =====================================================================
def classificar_lado(ratio_x: float, media_esq: float, media_dir: float) -> str:
    """Classifica por vizinho mais próximo entre os dois pontos calibrados (SIM e NAO)."""
    ponto_medio = (media_esq + media_dir) / 2
    metade_intervalo = abs(media_dir - media_esq) / 2
    zona_morta = metade_intervalo * 0.3
    esquerda_e_menor = media_esq < media_dir

    if ratio_x < ponto_medio - zona_morta:
        return "Esquerda" if esquerda_e_menor else "Direita"
    elif ratio_x > ponto_medio + zona_morta:
        return "Direita" if esquerda_e_menor else "Esquerda"
    return "Centro"


# =====================================================================
# EAR (Eye Aspect Ratio) -- detecção de piscada, usada como confirmação
# alternativa ao dwell time (olhar fixo por N frames)
# =====================================================================
def calcular_ear(landmarks, indices_verticais, indices_cantos, largura, altura) -> float:
    """
    Eye Aspect Ratio: cai quando o olho fecha (pisca). Valor tipicamente
    acima de ~0.25 com olho aberto e abaixo de ~0.15 com olho fechado,
    mas isso varia por pessoa/câmera -- o limiar é configurável
    (config/settings.yaml -> deteccao.piscada.limiar_ear).
    """
    p_sup = landmarks[indices_verticais[0]]
    p_inf = landmarks[indices_verticais[1]]
    p_canto1 = landmarks[indices_cantos[0]]
    p_canto2 = landmarks[indices_cantos[1]]

    dist_vertical = abs(p_sup.y - p_inf.y) * altura
    dist_horizontal = abs(p_canto1.x - p_canto2.x) * largura

    return dist_vertical / max(dist_horizontal, 1e-3)


def olho_fechado(ear: float, limiar: float = 0.15) -> bool:
    return ear < limiar


# =====================================================================
# Compensação de pose de cabeça
# =====================================================================
def extrair_angulos_da_matriz(
    matriz_transformacao: np.ndarray,
) -> tuple[float, float, float]:
    """
    Extrai (yaw, pitch, roll) em graus da matriz de transformação facial
    4x4 que o MediaPipe retorna com
    ``output_facial_transformation_matrixes=True``.

    A decomposição é a mesma usada em robótica (convenção ZYX):
      * yaw  = giro da cabeça para os lados;
      * pitch = cabeça para cima/baixo;
      * roll  = inclinação lateral (orelha na direção do ombro).

    Uma cabeça inclinada muda o ratio da íris mesmo com o olhar parado --
    sobretudo o ``ratio_y`` usado na prancha. Ter os três ângulos permite
    descartar o quadro em vez de confiar num olhar distorcido.
    """
    r = np.asarray(matriz_transformacao)[:3, :3]
    yaw = math.atan2(-float(r[2, 0]), math.sqrt(float(r[2, 1]) ** 2 + float(r[2, 2]) ** 2))
    pitch = math.atan2(float(r[2, 1]), float(r[2, 2]))
    roll = math.atan2(float(r[1, 0]), float(r[0, 0]))
    return (
        float(math.degrees(yaw)),
        float(math.degrees(pitch)),
        float(math.degrees(roll)),
    )


def extrair_yaw_da_matriz(matriz_transformacao: np.ndarray) -> float:
    """Compatibilidade: devolve só o yaw (graus) da matriz facial."""
    return extrair_angulos_da_matriz(matriz_transformacao)[0]


def pose_dentro_dos_limites(
    yaw_graus: float,
    pitch_graus: float,
    roll_graus: float,
    max_yaw: float,
    max_pitch: float,
    max_roll: float,
) -> bool:
    """
    True quando os três ângulos estão dentro dos limites configurados.

    Limites iguais a zero ou negativos são ignorados para aquele eixo, o
    que permite desligar a checagem de um eixo sem mudar o código.
    """
    if max_yaw > 0 and abs(float(yaw_graus)) > max_yaw:
        return False
    if max_pitch > 0 and abs(float(pitch_graus)) > max_pitch:
        return False
    return max_roll <= 0 or abs(float(roll_graus)) <= max_roll


def compensar_ratio_por_yaw(ratio_x: float, yaw_graus: float, sensibilidade: float = 0.004) -> float:
    """
    Ajusta o ratio_x horizontal subtraindo uma fração proporcional ao
    ângulo de yaw da cabeça.

    ATENÇÃO: é uma correção empírica e opcional. O ratio já é medido
    dentro da largura do olho, o que remove boa parte do efeito da
    rotação. Por isso o padrão do aplicativo é NÃO compensar
    (``deteccao.compensar_yaw: false``); se ativar, recalibre a prancha
    com a compensação ligada para que os dois lados usem a mesma régua.
    """
    correcao = yaw_graus * sensibilidade
    return min(max(ratio_x - correcao, 0.0), 1.0)


# =====================================================================
# Divergência entre os olhos -- confiança do quadro
# =====================================================================
def divergencia_entre_olhos(ratio_esq: float, ratio_dir: float) -> float:
    """
    Diferença absoluta entre os ratios horizontais dos dois olhos.

    Quando os dois olhos apontam para lugares muito diferentes, o quadro
    normalmente não representa um olhar válido: pode ser piscada, oclusão,
    reflexo na íris ou ruído do detector. Nesse caso é melhor ignorar o
    quadro do que deixá-lo mexer no dwell ou entrar na calibração.
    """
    return abs(float(ratio_esq) - float(ratio_dir))


def divergencia_dentro_do_limite(
    ratio_esq: float, ratio_dir: float, limite: float
) -> bool:
    """
    True quando a divergência entre os olhos está dentro do limite.

    O limite é por pessoa: quem tem estrabismo pode divergir de forma
    consistente, então ele fica em ``deteccao.divergencia_max`` e pode ser
    afrouxado no Modo Cuidador sem tocar no código.
    """
    if limite <= 0:
        raise ValueError("limite de divergência deve ser maior que zero")
    return divergencia_entre_olhos(ratio_esq, ratio_dir) <= float(limite)


# =====================================================================
# Distância do rosto até a câmera (indicador informativo)
# =====================================================================
DISTANCIA_BOA = "boa"
DISTANCIA_LONGE = "longe"
DISTANCIA_PERTO = "perto"
DISTANCIA_INDEFINIDA = "indefinida"


def distancia_rosto_normalizada(
    landmarks,
    largura: int,
    altura: int,
    yaw_graus: float = 0.0,
) -> float:
    """
    Medida relativa de distância do rosto até a câmera.

    Usa a distância entre os cantos externos dos dois olhos, em fração da
    largura do quadro. Quanto menor o valor, mais longe o rosto está. O
    yaw da cabeça encurta essa distância na imagem; por isso o resultado é
    dividido pelo cosseno do ângulo (limitado a 60 graus), compensando
    cabeças levemente viradas.

    Não é uma medida em centímetros: é um proxy estável para comparar o
    enquadramento atual com a faixa configurada em ``deteccao``.
    """
    canto_direito = landmarks[OLHO_DIREITO_CANTOS[0]]
    canto_esquerdo = landmarks[OLHO_ESQUERDO_CANTOS[1]]

    dx = (float(canto_direito.x) - float(canto_esquerdo.x)) * largura
    dy = (float(canto_direito.y) - float(canto_esquerdo.y)) * altura
    medida = math.hypot(dx, dy) / max(float(largura), 1.0)

    yaw = abs(float(yaw_graus))
    fator = math.cos(math.radians(min(yaw, 60.0)))
    return medida / max(fator, 0.5)


def classificar_distancia(
    medida: float,
    longe_abaixo: float,
    perto_acima: float,
) -> str:
    """
    Classifica a medida de distância em ``longe``, ``boa`` ou ``perto``.

    Os limites são absolutos e configuráveis: câmeras com campo de visão
    muito diferente podem precisar de ajuste no Modo Cuidador. Quando os
    limites são inválidos, devolve ``indefinida`` em vez de arriscar um
    aviso errado.
    """
    if longe_abaixo <= 0 or perto_acima <= longe_abaixo:
        return DISTANCIA_INDEFINIDA
    if medida < float(longe_abaixo):
        return DISTANCIA_LONGE
    if medida > float(perto_acima):
        return DISTANCIA_PERTO
    return DISTANCIA_BOA
