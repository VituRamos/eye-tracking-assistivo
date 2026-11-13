"""Smoke tests do preview do novo design (sem câmera/MediaPipe)."""
from __future__ import annotations

from PIL import Image, ImageChops

from preview_novo_design import telas, tema
from preview_novo_design.icones import (
    PICTOGRAMAS,
    caminho_do_pictograma,
    desenhar_pictograma,
)
from preview_novo_design.renderizar import TELAS, renderizar_todas
from preview_novo_design.svg import ler_svg, renderizar_mascara


def test_tokens_do_tema_claro() -> None:
    assert tema.CORES["fundo"] == (244, 241, 234)
    assert tema.CORES["texto"] == (27, 36, 48)
    assert tema.CORES["apoio"] == (77, 101, 114)
    assert tema.CORES["oi"] == (244, 198, 211)
    assert tema.CORES["comer"] == (246, 213, 140)
    assert tema.CORES["beber"] == (163, 221, 210)
    assert tema.CORES["banheiro"] == (179, 205, 243)
    assert tema.CORES["confirmado"] == (31, 122, 74)
    assert tema.CORES["atencao"] == (155, 74, 8)


def test_todas_as_telas_renderizam_em_16_9() -> None:
    for slug, _nome, funcao in TELAS:
        imagem = funcao(640, 360)
        assert isinstance(imagem, Image.Image)
        assert imagem.mode == "RGB"
        assert imagem.size == (640, 360)
        cores = imagem.getcolors(maxcolors=1_000_000)
        assert cores is not None and len(cores) > 8, slug


def test_prancha_tem_estados_distintos() -> None:
    repouso = telas.tela_prancha(640, 360)
    foco = telas.tela_prancha(640, 360, foco="comer", progresso=0.6)
    confirmado = telas.tela_prancha(640, 360, confirmado="beber")

    assert ImageChops.difference(repouso, foco).getbbox() is not None
    assert ImageChops.difference(repouso, confirmado).getbbox() is not None
    assert ImageChops.difference(foco, confirmado).getbbox() is not None


def test_tela_em_1920x1080() -> None:
    imagem = telas.tela_prancha(1920, 1080, foco="oi", progresso=0.3)
    assert imagem.size == (1920, 1080)
    assert imagem.mode == "RGB"


def test_pictogramas_desenham_tinta() -> None:
    for nome in PICTOGRAMAS:
        lona = tema.Lona(1280, 720)
        desenhar_pictograma(lona, nome, 640, 360, 200, tema.CORES["texto"])
        imagem = lona.finalizar()
        escuros = sum(
            1
            for x in range(530, 750)
            for y in range(250, 470)
            if sum(imagem.getpixel((x, y))) < 250
        )
        assert escuros > 500, nome


def test_svg_dos_pictogramas_carrega_caminhos() -> None:
    for nome in PICTOGRAMAS:
        caminho = caminho_do_pictograma(nome)
        assert caminho.exists(), nome
        desenho = ler_svg(caminho)
        assert desenho.viewbox[2] > 0 and desenho.viewbox[3] > 0
        assert desenho.caminhos
        pontos = [
            ponto
            for grupo in desenho.caminhos
            for sub in grupo
            for ponto in sub.pontos
        ]
        assert len(pontos) > 20, nome


def test_mascara_preserva_o_vao_do_prato() -> None:
    desenho = ler_svg(caminho_do_pictograma("comer"))
    mascara = renderizar_mascara(desenho, 128)
    assert mascara.mode == "1"
    assert mascara.getbbox() is not None
    assert mascara.getpixel((64, 64)) == 0
    assert mascara.histogram()[255] > 0


def test_menu_recolhido_estreita_a_barra_lateral() -> None:
    expandida = telas.tela_boas_vindas(1280, 720)
    recolhida = telas.tela_boas_vindas_recolhida(1280, 720)

    assert expandida.getpixel((150, 600)) == tema.CORES["superficie"]
    assert recolhida.getpixel((150, 600)) == tema.CORES["fundo"]
    assert recolhida.getpixel((60, 500)) == tema.CORES["superficie"]
    assert ImageChops.difference(expandida, recolhida).getbbox() is not None


def test_renderizador_gera_um_png_por_tela(tmp_path) -> None:
    gerados = renderizar_todas(tmp_path, tamanhos=((640, 360),), contato=False)
    assert len(gerados) == len(TELAS)
    assert all(caminho.exists() for caminho in gerados)
    assert (tmp_path / "640x360" / "01_boas_vindas.png").exists()
    assert (tmp_path / "640x360" / "14_modo_cuidador.png").exists()
