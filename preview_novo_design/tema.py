"""
Tokens visuais do novo design (tema claro).

A base de layout é 1280x720 (a mesma do app atual); as telas são
desenhadas com supersampling 2x e reduzidas no final, para textos e
curvas ficarem nítidos também em 1920x1080.

Nada aqui é importado pelo app de produção.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# =====================================================================
# Geometria de referência
# =====================================================================
LARGURA_BASE = 1280
ALTURA_BASE = 720
SUPERSAMPLING = 2

MARGEM = 56
ESPACAMENTO = 22
RAIO_CARTAO = 28
TOPO_GRADE = 126
BASE_GRADE = 44

# =====================================================================
# Paleta -- tema claro do board
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


def hex_para_rgb(valor: str) -> tuple[int, int, int]:
    """Converte ``#RRGGBB`` em uma tupla RGB."""
    valor = valor.lstrip("#")
    return tuple(int(valor[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def com_alpha(cor: tuple[int, int, int], alpha: int) -> tuple[int, int, int, int]:
    return (*cor, max(0, min(255, int(alpha))))


def misturar(
    cor_a: tuple[int, int, int],
    cor_b: tuple[int, int, int],
    proporcao: float,
) -> tuple[int, int, int]:
    """Mistura ``cor_a`` com ``cor_b`` (0 = só A, 1 = só B)."""
    t = max(0.0, min(1.0, float(proporcao)))
    return tuple(round(a + (b - a) * t) for a, b in zip(cor_a, cor_b, strict=True))  # type: ignore[return-value]


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
    ) -> None:
        self.largura = int(largura)
        self.altura = int(altura)
        self.ss = max(1, int(supersampling))
        self.k = (self.largura / LARGURA_BASE) * self.ss
        self.img = Image.new(
            "RGBA",
            (self.largura * self.ss, self.altura * self.ss),
            com_alpha(CORES["fundo"], 255),
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
        pts = self.pontos(pontos)
        w = max(1, self.px(largura)) if contorno is not None else 0
        self.draw.polygon(
            pts,
            fill=cor,
            outline=contorno,
            width=w if contorno is not None else 1,
        )

    # -- composição -------------------------------------------------
    def colar(self, camada: Image.Image) -> None:
        self.img = Image.alpha_composite(self.img, camada)
        self.draw = ImageDraw.Draw(self.img)

    def finalizar(self) -> Image.Image:
        base = self.img.convert("RGB")
        if self.ss == 1:
            return base
        return base.resize((self.largura, self.altura), Image.Resampling.LANCZOS)
