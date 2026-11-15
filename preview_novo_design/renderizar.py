"""
Renderizador do preview: gera PNGs e abre a navegação interativa.

Uso::

    python -m preview_novo_design                 # gera e abre a janela
    python -m preview_novo_design --render-only   # só gera os PNGs

Os arquivos ficam em ``preview_novo_design/saidas/``. O modo interativo
usa OpenCV apenas para exibir as imagens; o desenho é feito com Pillow.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from .telas import TELAS, Tela
from .tema import CORES, fonte

SAIDA_PADRAO = Path(__file__).resolve().parent / "saidas"
TAMANHOS_PADRAO: tuple[tuple[int, int], ...] = ((1280, 720), (1920, 1080))


def telas_disponiveis() -> tuple[tuple[str, str, Tela], ...]:
    return TELAS


def _renderizar_uma(
    funcao: Tela,
    largura: int,
    altura: int,
    destino: Path,
) -> Path:
    imagem = funcao(largura, altura)
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino)
    return destino


def gerar_contato(saida: Path) -> Path:
    """Monta uma folha de contato com todas as telas em 1280x720."""
    colunas = 4
    mini_largura, mini_altura = 280, 158
    gap = 16
    margem = 56
    largura = margem * 2 + colunas * mini_largura + (colunas - 1) * gap
    linhas = math.ceil(len(TELAS) / colunas)
    topo = 80
    altura_linha = mini_altura + 34
    altura = topo + linhas * altura_linha + 16

    folha = Image.new("RGB", (largura, altura), CORES["fundo"])
    desenho = ImageDraw.Draw(folha)
    desenho.text(
        (margem, 34),
        "Novo design — telas do preview",
        font=fonte(20, "bold"),
        fill=CORES["texto"],
        anchor="lm",
    )
    desenho.text(
        (margem, 58),
        "Tema claro · base 1280x720 · gerado a partir de preview_novo_design",
        font=fonte(12),
        fill=CORES["apoio"],
        anchor="lm",
    )

    pasta_1280 = saida / "1280x720"
    for indice, (slug, nome, _) in enumerate(TELAS):
        coluna = indice % colunas
        linha = indice // colunas
        x = margem + coluna * (mini_largura + gap)
        y = topo + linha * altura_linha
        caminho = pasta_1280 / f"{slug}.png"
        original = (
            Image.open(caminho).convert("RGB")
            if caminho.exists()
            else TELAS[indice][2](1280, 720)
        )
        mini = original.resize((mini_largura, mini_altura), Image.Resampling.LANCZOS)
        folha.paste(mini, (x, y))
        desenho.rectangle(
            (x, y, x + mini_largura - 1, y + mini_altura - 1),
            outline=CORES["borda"],
            width=1,
        )
        desenho.text(
            (x, y + mini_altura + 12),
            nome,
            font=fonte(11),
            fill=CORES["apoio"],
            anchor="lm",
        )

    destino = saida / "contato.png"
    folha.save(destino)
    return destino


def renderizar_todas(
    saida: Path | str | None = None,
    tamanhos: tuple[tuple[int, int], ...] | None = None,
    *,
    contato: bool = True,
) -> list[Path]:
    """Gera todas as telas nos tamanhos pedidos e devolve os caminhos."""
    destino = Path(saida) if saida is not None else SAIDA_PADRAO
    destino.mkdir(parents=True, exist_ok=True)
    tamanhos = tamanhos or TAMANHOS_PADRAO

    gerados: list[Path] = []
    for largura, altura in tamanhos:
        pasta = destino / f"{largura}x{altura}"
        pasta.mkdir(parents=True, exist_ok=True)
        for slug, _, funcao in TELAS:
            gerados.append(
                _renderizar_uma(funcao, largura, altura, pasta / f"{slug}.png")
            )

    if contato:
        gerados.append(gerar_contato(destino))
    return gerados


def _abrir_janela(imagens: list[Image.Image], nomes: list[str], saida: Path) -> int:
    """Navegação por teclado. Importa OpenCV só quando necessário."""
    import cv2
    import numpy as np

    titulo = "Preview — novo design (tema claro)"
    indice = 0
    tela_cheia = False

    slugs = [slug for slug, _, _ in TELAS]
    indice_expandido = slugs.index("01_boas_vindas")
    indice_recolhido = slugs.index("01b_boas_vindas_recolhida")

    print("Controles: setas <- -> navegam | 1-9 atalhos | B recolhe o menu | "
          "S salva | F tela cheia | Q sai")
    try:
        cv2.namedWindow(titulo, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(titulo, 1280, 720)
        while True:
            imagem = imagens[indice]
            quadro = cv2.cvtColor(np.asarray(imagem), cv2.COLOR_RGB2BGR)
            cv2.imshow(titulo, quadro)
            cv2.setWindowTitle(titulo, f"{titulo} — {indice + 1}/{len(imagens)} {nomes[indice]}")

            tecla = cv2.waitKey(0)
            if tecla == -1:
                continue
            codigo = tecla & 0xFF

            if codigo in (27, ord("q"), ord("Q")):
                break
            if codigo in (32, 13, ord("d"), ord("D")) or tecla == 2555904 or tecla == 2621440:
                indice = (indice + 1) % len(imagens)
            elif codigo in (8, ord("a"), ord("A")) or tecla == 2424832 or tecla == 2490368:
                indice = (indice - 1) % len(imagens)
            elif ord("1") <= codigo <= ord("9"):
                alvo = codigo - ord("1")
                if alvo < len(imagens):
                    indice = alvo
            elif codigo in (ord("b"), ord("B")):
                indice = (
                    indice_expandido
                    if indice == indice_recolhido
                    else indice_recolhido
                )
            elif codigo in (ord("s"), ord("S")):
                pasta = saida / "interativo"
                pasta.mkdir(parents=True, exist_ok=True)
                nome = f"{indice + 1:02d}_{nomes[indice].lower().replace(' ', '_')}.png"
                imagem.save(pasta / nome)
                print(f"Salvo: {pasta / nome}")
            elif codigo in (ord("f"), ord("F")):
                tela_cheia = not tela_cheia
                cv2.setWindowProperty(
                    titulo,
                    cv2.WND_PROP_FULLSCREEN,
                    cv2.WINDOW_FULLSCREEN if tela_cheia else cv2.WINDOW_NORMAL,
                )
    except cv2.error as exc:
        print("Nao foi possivel abrir a janela interativa.")
        print("Use --render-only para gerar os PNGs e abri-los no visualizador.")
        print(f"Detalhe: {exc}")
    finally:
        cv2.destroyAllWindows()
    return 0


def modo_interativo(saida: Path | str | None = None) -> int:
    """Gera as telas em 1280x720 e abre a janela de navegação."""
    destino = Path(saida) if saida is not None else SAIDA_PADRAO
    imagens: list[Image.Image] = []
    nomes: list[str] = []
    for _, nome, funcao in TELAS:
        imagens.append(funcao(1280, 720))
        nomes.append(nome)
    return _abrir_janela(imagens, nomes, destino)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview isolado do novo design visual (tema claro).",
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="gera os PNGs e encerra (sem abrir janela)",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="pasta de saída dos PNGs",
    )
    parser.add_argument("--largura", type=int, default=None, help="largura personalizada")
    parser.add_argument("--altura", type=int, default=None, help="altura personalizada")
    parser.add_argument(
        "--sem-contato",
        action="store_true",
        help="não gera a folha de contato",
    )
    args = parser.parse_args(argv)

    if (args.largura is None) != (args.altura is None):
        parser.error("informe --largura e --altura juntos")
    tamanhos = (
        ((args.largura, args.altura),)  # type: ignore[arg-type]
        if args.largura is not None
        else TAMANHOS_PADRAO
    )

    gerados = renderizar_todas(args.saida, tamanhos, contato=not args.sem_contato)
    print(f"{len(gerados)} arquivo(s) gerado(s) em: {Path(args.saida).resolve()}")
    if args.sem_contato:
        print("Folha de contato desativada.")
    else:
        print(f"Folha de contato: {(Path(args.saida) / 'contato.png').resolve()}")

    if args.render_only:
        return 0
    return modo_interativo(args.saida)


if __name__ == "__main__":
    sys.exit(main())
