"""
Tokens visuais e utilitários de desenho do novo design (tema claro).

A base de layout é 1280x720, a mesma do app. As telas são desenhadas com
a Pillow em uma ``Lona`` com supersampling e reduzidas no final, o que
mantém texto, curvas e pictogramas nítidos em 1280x720 e 1920x1080.

Nada aqui decide seleção, tempos ou calibração: são apenas cores,
tipografia e formas.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from core import paths

# =====================================================================
# Geometria de referência
# =====================================================================
LARGURA_BASE = 1280
ALTURA_BASE = 720
SUPERSAMPLING = 1

MARGEM = 56
ESPACAMENTO = 22
RAIO_CARTAO = 28
TOPO_GRADE = 126
BASE_GRADE = 44

# =====================================================================
# Paleta (tema claro)
# =====================================================================
CORES: dict[str, tuple[int, int, int]] = {
    "fundo": (244, 241, 234),        # #F4F1EA
    "superficie": (255, 255, 255),   # #FFFFFF
    "borda": (219, 216, 208),        # #DBD8D0
    "texto": (27, 36, 48),           # #1B2430
    "apoio": (77, 101, 114),         # #4D6572
    "foco": (27, 36, 48),            # #1B2430
    "neutro": (231, 228, 220),       # #E7E4DC
    "confirmado": (31, 122, 74),     # #1F7A4A
    "confirmado_fundo": (228, 242, 233),
    "atencao": (155, 74, 8),         # #9B4A08
    "atencao_fundo": (251, 235, 221),
    "oi": (244, 198, 211),           # #F4C6D3
    "comer": (246, 213, 140),        # #F6D58C
    "beber": (163, 221, 210),        # #A3DDD2
    "banheiro": (179, 205, 243),     # #B3CDF3
    "branco": (255, 255, 255),
    "sombra": (27, 36, 48),
}

CORES_CARTAO: dict[str, tuple[int, int, int]] = {
    "oi": CORES["oi"],
    "comer": CORES["comer"],
    "beber": CORES["beber"],
    "banheiro": CORES["banheiro"],
}

MATIZ_CARTAO: dict[str, tuple[int, int, int]] = {
    "oi": CORES["oi"],
    "comer": CORES["comer"],
    "beber": CORES["beber"],
    "banheiro": CORES["banheiro"],
}


def misturar(
    cor_a: tuple[int, int, int],
    cor_b: tuple[int, int, int],
    proporcao: float,
) -> tuple[int, int, int]:
    """Mistura ``cor_a`` com ``cor_b`` (0 = só A, 1 = só B)."""
    t = max(0.0, min(1.0, float(proporcao)))
    return tuple(round(a + (b - a) * t) for a, b in zip(cor_a, cor_b, strict=True))  # type: ignore[return-value]


def com_alpha(cor: tuple[int, int, int], alpha: int) -> tuple[int, int, int, int]:
    return (*cor, max(0, min(255, int(alpha))))


# =====================================================================
# Tipografia
# =====================================================================
_PASTA_FONTES = Path("C:/Windows/Fonts")
_FONTES = {
    "regular": ("segoeui.ttf", "arial.ttf"),
    "semibold": ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"),
    "bold": ("segoeuib.ttf", "arialbd.ttf"),
    "light": ("segoeuil.ttf", "segoeui.ttf", "arial.ttf"),
}


@lru_cache(maxsize=8)
def _caminho_fonte(peso: str) -> str | None:
    for nome in _FONTES.get(peso, _FONTES["regular"]):
        caminho = _PASTA_FONTES / nome
        if caminho.exists():
            return str(caminho)
    return None


@lru_cache(maxsize=256)
def fonte(tamanho: int, peso: str = "regular") -> ImageFont.FreeTypeFont:
    """Fonte Segoe UI (fallback Arial) no tamanho pedido, em pixels finais."""
    tamanho = max(1, int(tamanho))
    caminho = _caminho_fonte(peso)
    if caminho:
        return ImageFont.truetype(caminho, size=tamanho)
    return ImageFont.load_default(size=tamanho)


# =====================================================================
# Lona de desenho
# =====================================================================
class Lona:
    """Canvas em unidades de layout (1280x720) com supersampling."""

    def __init__(
        self,
        largura: int = LARGURA_BASE,
        altura: int = ALTURA_BASE,
        supersampling: int = SUPERSAMPLING,
        fundo: tuple[int, int, int] | None = CORES["fundo"],
    ) -> None:
        self.largura = int(largura)
        self.altura = int(altura)
        self.ss = max(1, int(supersampling))
        self.k = (self.largura / LARGURA_BASE) * self.ss
        self.img = Image.new(
            "RGBA",
            (self.largura * self.ss, self.altura * self.ss),
            com_alpha(fundo, 255) if fundo is not None else (0, 0, 0, 0),
        )
        self.draw = ImageDraw.Draw(self.img)

    # -- conversão de unidades -------------------------------------
    def px(self, valor: float) -> int:
        return round(float(valor) * self.k)

    def caixa(self, caixa: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        return tuple(self.px(v) for v in caixa)  # type: ignore[return-value]

    def pontos(self, pontos: list[tuple[float, float]]) -> list[tuple[int, int]]:
        return [(self.px(x), self.px(y)) for x, y in pontos]

    # -- texto ------------------------------------------------------
    def fonte(self, tamanho: float, peso: str = "regular") -> ImageFont.FreeTypeFont:
        return fonte(max(1, round(tamanho * self.k)), peso)

    def largura_texto(self, texto: str, tamanho: float, peso: str = "regular") -> float:
        return self.draw.textlength(texto, font=self.fonte(tamanho, peso)) / self.k

    def texto(
        self,
        xy: tuple[float, float],
        texto: str,
        tamanho: float = 20,
        cor: tuple[int, int, int] = CORES["texto"],
        peso: str = "regular",
        anchor: str = "la",
    ) -> None:
        self.draw.text(
            (self.px(xy[0]), self.px(xy[1])),
            texto,
            font=self.fonte(tamanho, peso),
            fill=cor,
            anchor=anchor,
        )

    # -- formas -----------------------------------------------------
    def retangulo(
        self,
        caixa: tuple[float, float, float, float],
        cor: tuple[int, int, int] | None = None,
        raio: float = 0,
        contorno: tuple[int, int, int] | None = None,
        largura: float = 1,
    ) -> None:
        x1, y1, x2, y2 = self.caixa(caixa)
        r = max(0, self.px(raio))
        w = max(1, self.px(largura)) if contorno is not None else 0
        if r == 0:
            self.draw.rectangle(
                (x1, y1, x2, y2),
                fill=cor,
                outline=contorno,
                width=w if contorno is not None else 1,
            )
            return
        self.draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=r,
            fill=cor,
            outline=contorno,
            width=w if contorno is not None else 1,
        )

    def elipse(
        self,
        caixa: tuple[float, float, float, float],
        cor: tuple[int, int, int] | None = None,
        contorno: tuple[int, int, int] | None = None,
        largura: float = 1,
    ) -> None:
        x1, y1, x2, y2 = self.caixa(caixa)
        w = max(1, self.px(largura)) if contorno is not None else 0
        self.draw.ellipse(
            (x1, y1, x2, y2),
            fill=cor,
            outline=contorno,
            width=w if contorno is not None else 1,
        )

    def circulo(
        self,
        centro: tuple[float, float],
        raio: float,
        cor: tuple[int, int, int] | None = None,
        contorno: tuple[int, int, int] | None = None,
        largura: float = 1,
    ) -> None:
        cx, cy = centro
        self.elipse((cx - raio, cy - raio, cx + raio, cy + raio), cor, contorno, largura)

    def linha(
        self,
        pontos: list[tuple[float, float]],
        cor: tuple[int, int, int],
        largura: float = 2,
    ) -> None:
        self.draw.line(
            self.pontos(pontos),
            fill=cor,
            width=max(1, self.px(largura)),
            joint="curve",
        )

    def poligono(
        self,
        pontos: list[tuple[float, float]],
        cor: tuple[int, int, int] | None = None,
        contorno: tuple[int, int, int] | None = None,
        largura: float = 1,
    ) -> None:
        w = max(1, self.px(largura)) if contorno is not None else 0
        self.draw.polygon(
            self.pontos(pontos),
            fill=cor,
            outline=contorno,
            width=w if contorno is not None else 1,
        )

    # -- composição -------------------------------------------------
    def finalizar(self) -> Image.Image:
        base = self.img.convert("RGB")
        if self.ss == 1:
            return base
        return base.resize((self.largura, self.altura), Image.Resampling.LANCZOS)

    def finalizar_rgba(self) -> Image.Image:
        """Reduz mantendo o canal alfa (para sobreposições)."""
        if self.ss == 1:
            return self.img
        return self.img.resize((self.largura, self.altura), Image.Resampling.LANCZOS)


# =====================================================================
# Leitor mínimo de SVG (pictogramas)
# =====================================================================
Matriz = tuple[float, float, float, float, float, float]
ViewBox = tuple[float, float, float, float]

_IDENTIDADE: Matriz = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_TOLERANCIA = 0.2
_PROFUNDIDADE_MAXIMA = 12

_NUMERO = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_TRANSFORMACAO = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")
_COMANDO_OU_NUMERO = re.compile(
    r"([MmLlHhVvCcSsQqTtAaZz])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)"
)


@dataclass(frozen=True)
class Subcaminho:
    """Um contorno fechado; o sinal de ``area`` indica o sentido."""

    pontos: tuple[tuple[float, float], ...]
    area: float


@dataclass(frozen=True)
class Desenho:
    """Caminhos de um SVG, já transformados para a viewBox."""

    caminhos: tuple[tuple[Subcaminho, ...], ...]
    viewbox: ViewBox


def _compor(m1: Matriz, m2: Matriz) -> Matriz:
    """Devolve ``m1`` aplicada depois de ``m2``."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _aplicar(matriz: Matriz, x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matriz
    return (a * x + c * y + e, b * x + d * y + f)


def _matriz_transformacao(texto: str) -> Matriz:
    matriz = _IDENTIDADE
    for nome, argumentos in _TRANSFORMACAO.findall(texto):
        valores = [float(v) for v in _NUMERO.findall(argumentos)]
        if nome == "translate" and valores:
            tx = valores[0]
            ty = valores[1] if len(valores) > 1 else 0.0
            local: Matriz = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif nome == "scale" and valores:
            sx = valores[0]
            sy = valores[1] if len(valores) > 1 else sx
            local = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif nome == "matrix" and len(valores) == 6:
            local = tuple(valores)  # type: ignore[assignment]
        elif nome == "rotate" and valores:
            angulo = math.radians(valores[0])
            cos, sen = math.cos(angulo), math.sin(angulo)
            rotacao: Matriz = (cos, sen, -sen, cos, 0.0, 0.0)
            if len(valores) == 3:
                cx, cy = valores[1], valores[2]
                rotacao = _compor(
                    (1.0, 0.0, 0.0, 1.0, cx, cy),
                    _compor(rotacao, (1.0, 0.0, 0.0, 1.0, -cx, -cy)),
                )
            local = rotacao
        else:
            raise ValueError(f"Transformação SVG não suportada: {nome}({argumentos})")
        matriz = _compor(matriz, local)
    return matriz


def _comandos(d: str) -> list[tuple[str, list[float]]]:
    saida: list[tuple[str, list[float]]] = []
    comando = ""
    numeros: list[float] = []
    for achado in _COMANDO_OU_NUMERO.finditer(d):
        if achado.group(1):
            if comando:
                saida.append((comando, numeros))
            comando = achado.group(1)
            numeros = []
        else:
            numeros.append(float(achado.group(2)))
    if comando:
        saida.append((comando, numeros))
    return saida


def _meio(
    a: tuple[float, float], b: tuple[float, float]
) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _distancia_quadrada_reta(
    ponto: tuple[float, float],
    inicio: tuple[float, float],
    fim: tuple[float, float],
) -> float:
    dx, dy = fim[0] - inicio[0], fim[1] - inicio[1]
    if dx == 0 and dy == 0:
        return (ponto[0] - inicio[0]) ** 2 + (ponto[1] - inicio[1]) ** 2
    t = ((ponto[0] - inicio[0]) * dx + (ponto[1] - inicio[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px, py = inicio[0] + t * dx, inicio[1] + t * dy
    return (ponto[0] - px) ** 2 + (ponto[1] - py) ** 2


def _curva_plana(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> bool:
    limite = _TOLERANCIA * _TOLERANCIA
    return (
        _distancia_quadrada_reta(p1, p0, p3) <= limite
        and _distancia_quadrada_reta(p2, p0, p3) <= limite
    )


def _achatar_cubica(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    saida: list[tuple[float, float]],
    profundidade: int = 0,
) -> None:
    if profundidade >= _PROFUNDIDADE_MAXIMA or _curva_plana(p0, p1, p2, p3):
        saida.append(p3)
        return
    p01 = _meio(p0, p1)
    p12 = _meio(p1, p2)
    p23 = _meio(p2, p3)
    p012 = _meio(p01, p12)
    p123 = _meio(p12, p23)
    p0123 = _meio(p012, p123)
    _achatar_cubica(p0, p01, p012, p0123, saida, profundidade + 1)
    _achatar_cubica(p0123, p123, p23, p3, saida, profundidade + 1)


def _quadratica_para_cubica(
    p0: tuple[float, float],
    controle: tuple[float, float],
    p2: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    c1 = (
        p0[0] + 2 / 3 * (controle[0] - p0[0]),
        p0[1] + 2 / 3 * (controle[1] - p0[1]),
    )
    c2 = (
        p2[0] + 2 / 3 * (controle[0] - p2[0]),
        p2[1] + 2 / 3 * (controle[1] - p2[1]),
    )
    return c1, c2


def _area(pontos: tuple[tuple[float, float], ...]) -> float:
    total = 0.0
    for indice, (x1, y1) in enumerate(pontos):
        x2, y2 = pontos[(indice + 1) % len(pontos)]
        total += x1 * y2 - x2 * y1
    return total / 2


def _interpretar(d: str, matriz: Matriz) -> list[Subcaminho]:
    subcaminhos: list[Subcaminho] = []
    pontos: list[tuple[float, float]] = []
    atual = (0.0, 0.0)
    inicio = (0.0, 0.0)
    ultimo = ""
    controle: tuple[float, float] | None = None

    def comecar() -> None:
        if not pontos:
            pontos.append(atual)

    def fechar() -> None:
        nonlocal pontos
        if len(pontos) >= 3:
            transformados = tuple(_aplicar(matriz, x, y) for x, y in pontos)
            subcaminhos.append(Subcaminho(transformados, _area(transformados)))
        pontos = []

    for comando, valores in _comandos(d):
        letra = comando.upper()
        relativo = comando != letra

        if letra == "Z":
            fechar()
            atual = inicio
            ultimo = "Z"
            controle = None
            continue

        i = 0
        while i < len(valores):
            if letra == "M":
                if i + 2 > len(valores):
                    break
                x, y = valores[i], valores[i + 1]
                if relativo:
                    x += atual[0]
                    y += atual[1]
                fechar()
                pontos = [(x, y)]
                atual = (x, y)
                inicio = (x, y)
                i += 2
                letra = "L"
                ultimo = "M"
                controle = None
            elif letra in ("L", "T"):
                if i + 2 > len(valores):
                    break
                x, y = valores[i], valores[i + 1]
                if relativo:
                    x += atual[0]
                    y += atual[1]
                if letra == "L":
                    comecar()
                    pontos.append((x, y))
                else:
                    if ultimo in ("Q", "T") and controle is not None:
                        qx = 2 * atual[0] - controle[0]
                        qy = 2 * atual[1] - controle[1]
                    else:
                        qx, qy = atual
                    c1, c2 = _quadratica_para_cubica(atual, (qx, qy), (x, y))
                    comecar()
                    _achatar_cubica(atual, c1, c2, (x, y), pontos)
                    controle = (qx, qy)
                atual = (x, y)
                i += 2
                ultimo = letra
                if letra == "L":
                    controle = None
            elif letra in ("H", "V"):
                if i + 1 > len(valores):
                    break
                valor = valores[i]
                if letra == "H":
                    x = valor + (atual[0] if relativo else 0.0)
                    y = atual[1]
                else:
                    x = atual[0]
                    y = valor + (atual[1] if relativo else 0.0)
                comecar()
                pontos.append((x, y))
                atual = (x, y)
                i += 1
                ultimo = letra
                controle = None
            elif letra in ("C", "S"):
                necessario = 6 if letra == "C" else 4
                if i + necessario > len(valores):
                    break
                if letra == "C":
                    x1, y1, x2, y2, x, y = valores[i : i + 6]
                    if relativo:
                        x1 += atual[0]
                        y1 += atual[1]
                        x2 += atual[0]
                        y2 += atual[1]
                        x += atual[0]
                        y += atual[1]
                    c1 = (x1, y1)
                    c2 = (x2, y2)
                else:
                    x2, y2, x, y = valores[i : i + 4]
                    if relativo:
                        x2 += atual[0]
                        y2 += atual[1]
                        x += atual[0]
                        y += atual[1]
                    if ultimo in ("C", "S") and controle is not None:
                        c1 = (2 * atual[0] - controle[0], 2 * atual[1] - controle[1])
                    else:
                        c1 = atual
                    c2 = (x2, y2)
                comecar()
                _achatar_cubica(atual, c1, c2, (x, y), pontos)
                atual = (x, y)
                controle = c2
                i += necessario
                ultimo = letra
            elif letra == "Q":
                if i + 4 > len(valores):
                    break
                qx, qy, x, y = valores[i : i + 4]
                if relativo:
                    qx += atual[0]
                    qy += atual[1]
                    x += atual[0]
                    y += atual[1]
                c1, c2 = _quadratica_para_cubica(atual, (qx, qy), (x, y))
                comecar()
                _achatar_cubica(atual, c1, c2, (x, y), pontos)
                atual = (x, y)
                controle = (qx, qy)
                i += 4
                ultimo = "Q"
            elif letra == "A":
                raise NotImplementedError("Caminhos SVG com arcos não são suportados.")
            else:
                raise ValueError(f"Comando SVG não suportado: {comando}")

    fechar()
    return subcaminhos


def _viewbox(raiz: ET.Element) -> ViewBox:
    valores = [float(v) for v in _NUMERO.findall(raiz.attrib.get("viewBox", ""))]
    if len(valores) == 4:
        return (valores[0], valores[1], valores[2], valores[3])
    largura = [float(v) for v in _NUMERO.findall(raiz.attrib.get("width", ""))]
    altura = [float(v) for v in _NUMERO.findall(raiz.attrib.get("height", ""))]
    if largura and altura:
        return (0.0, 0.0, largura[0], altura[0])
    raise ValueError("SVG sem viewBox ou largura/altura.")


def ler_svg(caminho: Path | str) -> Desenho:
    """Lê um SVG e devolve os caminhos já normalizados pela viewBox."""
    raiz = ET.parse(caminho).getroot()
    caminhos: list[tuple[Subcaminho, ...]] = []

    def visitar(no: ET.Element, matriz: Matriz) -> None:
        matriz = _compor(matriz, _matriz_transformacao(no.attrib.get("transform", "")))
        if isinstance(no.tag, str) and no.tag.rsplit("}", 1)[-1] == "path":
            d = no.attrib.get("d", "").strip()
            if d:
                subcaminhos = _interpretar(d, matriz)
                if subcaminhos:
                    caminhos.append(tuple(subcaminhos))
        for filho in no:
            visitar(filho, matriz)

    visitar(raiz, _IDENTIDADE)
    return Desenho(tuple(caminhos), _viewbox(raiz))


def renderizar_mascara(desenho: Desenho, lado: int) -> Image.Image:
    """Rasteriza o desenho em uma máscara 1-bit de ``lado`` x ``lado``."""
    lado = max(1, int(lado))
    vx, vy, vw, vh = desenho.viewbox
    if vw <= 0 or vh <= 0:
        raise ValueError("viewBox SVG inválida.")

    escala = min(lado / vw, lado / vh)
    deslocamento_x = (lado - vw * escala) / 2 - vx * escala
    deslocamento_y = (lado - vh * escala) / 2 - vy * escala

    def pixels(sub: Subcaminho) -> list[tuple[int, int]]:
        return [
            (
                round(x * escala + deslocamento_x),
                round(y * escala + deslocamento_y),
            )
            for x, y in sub.pontos
        ]

    mascara = Image.new("1", (lado, lado), 0)
    for grupo in desenho.caminhos:
        if not grupo:
            continue
        referencia = max(grupo, key=lambda sub: abs(sub.area))
        if referencia.area == 0:
            continue
        temporaria = Image.new("1", (lado, lado), 0)
        desenho_temp = ImageDraw.Draw(temporaria)
        for sub in grupo:
            if sub.area * referencia.area > 0 and len(sub.pontos) >= 3:
                desenho_temp.polygon(pixels(sub), fill=255)
        for sub in grupo:
            if sub.area * referencia.area < 0 and len(sub.pontos) >= 3:
                desenho_temp.polygon(pixels(sub), fill=0)
        mascara = ImageChops.logical_or(mascara, temporaria)
    return mascara


# =====================================================================
# Pictogramas
# =====================================================================
PICTOGRAMAS = ("oi", "comer", "beber", "banheiro")


def _pasta_pictogramas() -> Path:
    return paths.pasta_recurso() / "ui" / "assets" / "pictogramas"


def caminho_do_pictograma(nome: str) -> Path:
    if nome not in PICTOGRAMAS:
        raise KeyError(f"Pictograma desconhecido: {nome!r}")
    return _pasta_pictogramas() / f"{nome}.svg"


@lru_cache(maxsize=8)
def _desenho(nome: str) -> Desenho:
    return ler_svg(caminho_do_pictograma(nome))


@lru_cache(maxsize=64)
def _mascara(nome: str, lado: int) -> Image.Image:
    return renderizar_mascara(_desenho(nome), lado)


def desenhar_pictograma(
    lona: Lona,
    nome: str,
    cx: float,
    cy: float,
    tamanho: float,
    cor: tuple[int, int, int],
) -> None:
    """Desenha o pictograma ``nome`` centrado em ``(cx, cy)``."""
    lado = max(1, lona.px(tamanho))
    mascara = _mascara(nome, lado)
    camada = Image.new("RGBA", (lado, lado), (*cor, 255))
    x0 = lona.px(cx) - lado // 2
    y0 = lona.px(cy) - lado // 2
    lona.img.paste(camada, (x0, y0), mascara)


# =====================================================================
# Componentes compartilhados
# =====================================================================
def centro(
    lona: Lona,
    cx: float,
    cy: float,
    texto: str,
    tamanho: float,
    cor: tuple[int, int, int] = CORES["texto"],
    peso: str = "regular",
) -> None:
    lona.texto((cx, cy), texto, tamanho, cor, peso, anchor="mm")


def linha_arredondada(
    lona: Lona,
    pontos: list[tuple[float, float]],
    cor: tuple[int, int, int],
    largura: float,
) -> None:
    lona.linha(pontos, cor, largura)
    for ponto in pontos:
        lona.circulo(ponto, largura / 2, cor=cor)


def arco(
    lona: Lona,
    cx: float,
    cy: float,
    raio: float,
    inicio: float,
    fim: float,
    cor: tuple[int, int, int],
    largura: float,
    passos: int = 24,
) -> None:
    pontos = []
    for indice in range(passos + 1):
        angulo = math.radians(inicio + (fim - inicio) * indice / passos)
        pontos.append((cx + raio * math.cos(angulo), cy + raio * math.sin(angulo)))
    linha_arredondada(lona, pontos, cor, largura)


def check(
    lona: Lona,
    cx: float,
    cy: float,
    raio: float,
    cor: tuple[int, int, int],
    largura: float,
) -> None:
    linha_arredondada(
        lona,
        [
            (cx - raio * 0.46, cy + raio * 0.02),
            (cx - raio * 0.10, cy + raio * 0.38),
            (cx + raio * 0.50, cy - raio * 0.38),
        ],
        cor,
        largura,
    )


def circulo_check(
    lona: Lona,
    cx: float,
    cy: float,
    raio: float,
    cor: tuple[int, int, int],
    *,
    preenchido: bool = False,
) -> None:
    if preenchido:
        lona.circulo((cx, cy), raio, cor=cor)
        check(lona, cx, cy, raio * 0.72, CORES["branco"], max(3.0, raio * 0.16))
    else:
        lona.circulo((cx, cy), raio, contorno=cor, largura=4)
        check(lona, cx, cy, raio * 0.72, cor, max(3.5, raio * 0.16))


def marca(lona: Lona, x: float = 56, y: float = 34) -> None:
    """Marca da prancha: quatro quadrantes nas cores dos cartões."""
    lado = 11
    gap = 3
    lona.retangulo((x, y, x + lado, y + lado), CORES["texto"], 3)
    lona.retangulo((x + lado + gap, y, x + 2 * lado + gap, y + lado), CORES["oi"], 3)
    lona.retangulo((x, y + lado + gap, x + lado, y + 2 * lado + gap), CORES["beber"], 3)
    lona.retangulo(
        (x + lado + gap, y + lado + gap, x + 2 * lado + gap, y + 2 * lado + gap),
        CORES["comer"],
        3,
    )


def pilula(
    lona: Lona,
    x: float,
    y: float,
    texto: str,
    *,
    tamanho: float = 14,
    altura: float = 30,
    fundo: tuple[int, int, int] = CORES["superficie"],
    cor: tuple[int, int, int] = CORES["apoio"],
    borda: tuple[int, int, int] = CORES["borda"],
    padding: float = 14,
    anchor: str = "left",
    peso: str = "regular",
) -> None:
    largura = lona.largura_texto(texto, tamanho, peso) + padding * 2
    if anchor == "right":
        x1, x2 = x - largura, x
    elif anchor == "center":
        x1, x2 = x - largura / 2, x + largura / 2
    else:
        x1, x2 = x, x + largura
    lona.retangulo((x1, y, x2, y + altura), fundo, altura / 2, borda, 1)
    lona.texto((x1 + padding, y + altura / 2), texto, tamanho, cor, peso, anchor="lm")


def botao(
    lona: Lona,
    caixa: tuple[float, float, float, float],
    texto: str,
    *,
    primario: bool = True,
    tamanho: float = 18,
) -> None:
    x1, y1, x2, y2 = caixa
    if primario:
        lona.retangulo(caixa, CORES["texto"], 14)
        cor = CORES["fundo"]
    else:
        lona.retangulo(caixa, CORES["superficie"], 14, CORES["borda"], 1.5)
        cor = CORES["texto"]
    centro(lona, (x1 + x2) / 2, (y1 + y2) / 2, texto, tamanho, cor, "semibold")


def alerta(
    lona: Lona,
    cx: float,
    cy: float,
    raio: float,
    cor: tuple[int, int, int],
    *,
    preenchido: bool = False,
) -> None:
    if preenchido:
        lona.circulo((cx, cy), raio, cor=cor)
        centro(lona, cx, cy - 1, "!", raio * 1.45, CORES["branco"], "bold")
    else:
        lona.circulo((cx, cy), raio, contorno=cor, largura=4)
        centro(lona, cx, cy - 2, "!", raio * 1.25, cor, "bold")


def banner(
    lona: Lona,
    texto: str,
    *,
    y1: float = 88,
    y2: float = 130,
    icone: str = "alerta",
    x1: float = MARGEM,
    x2: float = LARGURA_BASE - MARGEM,
) -> None:
    lona.retangulo(
        (x1, y1, x2, y2),
        CORES["atencao_fundo"],
        12,
        CORES["atencao"],
        1.5,
    )
    cy = (y1 + y2) / 2
    if icone == "rosto":
        icone_rosto(lona, x1 + 28, cy, CORES["atencao"])
    elif icone == "cabeca":
        icone_cabeca(lona, x1 + 26, cy, CORES["atencao"])
    else:
        alerta(lona, x1 + 28, cy, 11, CORES["atencao"], preenchido=True)
    lona.texto((x1 + 52, cy), texto, 18, CORES["atencao"], "semibold", anchor="lm")


def icone_rosto(
    lona: Lona,
    cx: float,
    cy: float,
    cor: tuple[int, int, int],
) -> None:
    lona.circulo((cx, cy), 10, contorno=cor, largura=2.5)
    lona.circulo((cx - 3.5, cy - 2), 1.4, cor=cor)
    lona.circulo((cx + 3.5, cy - 2), 1.4, cor=cor)
    lona.linha([(cx - 3.5, cy + 4), (cx + 3.5, cy + 4)], cor, 2)


def icone_cabeca(
    lona: Lona,
    cx: float,
    cy: float,
    cor: tuple[int, int, int],
) -> None:
    lona.circulo((cx - 4, cy), 9, contorno=cor, largura=2.5)
    lona.circulo((cx - 1, cy - 2), 1.3, cor=cor)
    lona.linha([(cx + 6, cy), (cx + 18, cy)], cor, 2.5)
    lona.linha([(cx + 13, cy - 4), (cx + 18, cy)], cor, 2.5)
    lona.linha([(cx + 13, cy + 4), (cx + 18, cy)], cor, 2.5)


def cabecalho(
    lona: Lona,
    titulo: str,
    subtitulo: str | None = None,
    *,
    instrucao: str | None = None,
    direita_texto: str | None = None,
    direita_tamanho: float = 14,
    direita_peso: str = "regular",
) -> None:
    marca(lona, 56, 28)
    lona.texto((92, 39), titulo, 21, CORES["texto"], "semibold", anchor="lm")
    if subtitulo:
        lona.texto((92, 62), subtitulo, 13, CORES["apoio"], anchor="lm")
    if direita_texto:
        pilula(
            lona,
            LARGURA_BASE - MARGEM,
            24,
            direita_texto,
            tamanho=direita_tamanho,
            anchor="right",
            peso=direita_peso,
        )
    if instrucao:
        lona.texto((92, 92), instrucao, 15, CORES["apoio"], anchor="lm")


def rodape(lona: Lona, texto: str, *, y: float = 700) -> None:
    centro(lona, LARGURA_BASE / 2, y, texto, 14, CORES["apoio"])


def aplicar(frame, imagem: Image.Image) -> None:
    """Copia a imagem RGB desenhada para o frame BGR do OpenCV."""
    import numpy as np

    rgb = np.asarray(imagem)
    if frame.shape[0] != rgb.shape[0] or frame.shape[1] != rgb.shape[1]:
        frame[:] = 0
        frame[: rgb.shape[0], : rgb.shape[1]] = rgb[:, :, ::-1]
        return
    frame[:] = rgb[:, :, ::-1]


def sobrepor(frame, imagem: Image.Image) -> None:
    """Compõe uma imagem RGBA (com transparência) sobre o frame BGR.

    Só a região realmente desenhada (bounding box do alfa) é convertida e
    composta, o que mantém avisos e pílulas baratos em 1280x720 e 1080p.
    """
    import numpy as np

    if frame.shape[0] != imagem.size[1] or frame.shape[1] != imagem.size[0]:
        imagem = imagem.resize((frame.shape[1], frame.shape[0]), Image.Resampling.LANCZOS)
    caixa = imagem.getbbox()
    if caixa is None:
        return
    x1, y1, x2, y2 = caixa
    base = Image.fromarray(frame[y1:y2, x1:x2, ::-1]).convert("RGBA")
    base.alpha_composite(imagem.crop(caixa))
    frame[y1:y2, x1:x2] = np.asarray(base.convert("RGB"))[:, :, ::-1]
