"""Testes da geometria e da classificação da prancha (core/board.py)."""
import pytest

from core import board


class TestBlocos:
    def test_tem_os_quatro_blocos_iniciais(self):
        assert board.IDS_BLOCOS == ("oi", "comer", "beber", "banheiro")

    def test_rotulos_sao_exibidos_em_maiusculas(self):
        assert [b.rotulo for b in board.BLOCOS] == [
            "OI", "COMER", "BEBER", "BANHEIRO",
        ]

    def test_obter_bloco_existente(self):
        assert board.obter("comer").rotulo == "COMER"

    def test_obter_bloco_inexistente_levanta_erro(self):
        with pytest.raises(KeyError, match="Bloco desconhecido"):
            board.obter("dormir")

    def test_rotulo_de_none_e_vazio(self):
        assert board.rotulo(None) == ""

    def test_rotulo_de_bloco_valido(self):
        assert board.rotulo("banheiro") == "BANHEIRO"


class TestGeometria:
    def test_grade_2x2_respeita_ordem_de_leitura(self):
        largura, altura = 1280, 720
        oi = board.retangulo(board.obter("oi"), largura, altura)
        comer = board.retangulo(board.obter("comer"), largura, altura)
        beber = board.retangulo(board.obter("beber"), largura, altura)
        banheiro = board.retangulo(board.obter("banheiro"), largura, altura)

        assert oi[0] < comer[0]          # oi à esquerda de comer
        assert oi[1] < beber[1]          # oi acima de beber
        assert beber[0] < banheiro[0]
        assert comer[1] < banheiro[1]

    def test_cartoes_nao_se_sobrepoem(self):
        largura, altura = 1280, 720
        retangulos = [board.retangulo(b, largura, altura) for b in board.BLOCOS]
        for i, (x1, y1, x2, y2) in enumerate(retangulos):
            for j, (a1, b1, a2, b2) in enumerate(retangulos):
                if i == j:
                    continue
                sobrepoe = x1 < a2 and a1 < x2 and y1 < b2 and b1 < y2
                assert not sobrepoe, f"blocos {i} e {j} se sobrepõem"

    def test_cartoes_cabem_na_tela(self):
        largura, altura = 1280, 720
        for bloco in board.BLOCOS:
            x1, y1, x2, y2 = board.retangulo(bloco, largura, altura)
            assert 0 <= x1 < x2 <= largura
            assert 0 <= y1 < y2 <= altura

    def test_centro_fica_dentro_do_retangulo(self):
        largura, altura = 1280, 720
        for bloco in board.BLOCOS:
            x1, y1, x2, y2 = board.retangulo(bloco, largura, altura)
            cx, cy = board.centro_do_bloco(bloco, largura, altura)
            assert x1 < cx < x2
            assert y1 < cy < y2


class TestClassificacao:
    def _referencias(self):
        return {
            "oi": (0.30, 0.30),
            "comer": (0.70, 0.30),
            "beber": (0.30, 0.70),
            "banheiro": (0.70, 0.70),
        }

    def test_reconhece_cada_ponto_calibrado(self):
        referencias = self._referencias()
        for bloco_id, ponto in referencias.items():
            assert board.classificar(*ponto, referencias) == bloco_id

    def test_escolhe_o_vizinho_mais_proximo(self):
        assert board.classificar(0.32, 0.34, self._referencias()) == "oi"
        assert board.classificar(0.68, 0.72, self._referencias()) == "banheiro"

    def test_sem_referencias_nao_escolhe_nada(self):
        assert board.classificar(0.5, 0.5, {}) is None

    def test_olhar_muito_longe_nao_escolhe(self):
        # Ponto no canto oposto, com raio pequeno: nenhum bloco deve ser
        # escolhido só por ser "o menos distante".
        assert board.classificar(0.0, 0.0, self._referencias(), raio_max=0.1) is None

    def test_raio_max_generoso_aceita(self):
        assert board.classificar(0.0, 0.0, self._referencias(), raio_max=2.0) == "oi"


class TestDistanciaMinima:
    def test_distancia_entre_quatro_cantos(self):
        referencias = {
            "oi": (0.2, 0.2),
            "comer": (0.8, 0.2),
            "beber": (0.2, 0.8),
            "banheiro": (0.8, 0.8),
        }
        assert board.distancia_minima_entre_pontos(referencias) == pytest.approx(0.6)

    def test_pontos_iguais_dao_distancia_zero(self):
        referencias = {"oi": (0.5, 0.5), "comer": (0.5, 0.5)}
        assert board.distancia_minima_entre_pontos(referencias) == 0.0

    def test_menos_de_dois_pontos_da_zero(self):
        assert board.distancia_minima_entre_pontos({}) == 0.0
        assert board.distancia_minima_entre_pontos({"oi": (0.5, 0.5)}) == 0.0
