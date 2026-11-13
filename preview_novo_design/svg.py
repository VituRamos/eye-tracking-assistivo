"""
Leitor mínimo de SVG para os pictogramas do preview.

Os quatro desenhos fornecidos são silhuetas preenchidas, com caminhos
simples (M, L, C, Q e Z) em uma viewBox quase quadrada. Em vez de
adicionar uma dependência de rasterização (Cairo, svglib...), este
módulo interpreta esses comandos e preenche os contornos com as
primitivas da Pillow em uma máscara 1-bit.

A máscara é gerada no tamanho já supersamplificado da ``Lona``; a
redução final com LANCZOS suaviza as bordas. Nada aqui é usado pelo
aplicativo de produção.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

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


# =====================================================================
# Álgebra das transformações
# =====================================================================
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


# =====================================================================
# Leitura dos comandos de caminho
# =====================================================================
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


# =====================================================================
# Leitura do arquivo e rasterização
# =====================================================================
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
