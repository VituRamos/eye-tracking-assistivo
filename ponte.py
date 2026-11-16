"""
Ponte headless entre o core Python e a interface Tauri.

O aplicativo final mantém TODA a lógica de câmera, olhar, dwell,
calibração e perfis no Python -- exatamente a mesma do ``main.py`` -- e
usa a interface React/Tauri apenas como apresentação.

Contrato
--------
* ``stdin``: um objeto JSON por linha (comandos da interface);
* ``stdout``: um objeto JSON por linha (snapshots ~30 Hz e mensagens);
* ``stderr`` + ``logs/``: diagnóstico (nunca polui o stdout).

O processo é iniciado e encerrado pelo aplicativo Tauri.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import json
import logging
import os
import queue
import shutil
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

# Garante que os pacotes do projeto sejam encontrados mesmo quando o
# processo é iniciado com outro diretório de trabalho.
RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from config.loader import carregar_config, salvar_config, validar_config  # noqa: E402
from core import board, paths  # noqa: E402
from core import gaze_engine as ge  # noqa: E402
from core.board_calibration import GerenciadorPrancha, pontos_do_dados  # noqa: E402
from core.calibration import GerenciadorCalibracao  # noqa: E402
from core.feedback import FeedbackSonoro  # noqa: E402
from core.logging_config import configurar_logging  # noqa: E402
from core.model_loader import garantir_modelo_baixado  # noqa: E402
from core.selection import ControladorSelecao, DecisaoSelecao  # noqa: E402
from core.state_machine import AppState, EstadoApp  # noqa: E402

VERSAO = "2.2.5"

# Captura e detecção continuam em 1280x720 (custo baixo no MediaPipe).
LARGURA_PROJETO = 1280
ALTURA_PROJETO = 720

logger = logging.getLogger("eyetracking.ponte")


# Estados em que o detector realmente roda. Inclui as telas de preparação
# para que o ponto do olhar e os avisos de rosto/pose funcionem antes de a
# coleta começar (no motor real o detector é a única fonte desses dados).
ESTADOS_COM_DETECCAO = (
    EstadoApp.MENU,
    EstadoApp.CALIB_PREPARAR,
    EstadoApp.CALIB_COLETANDO,
    EstadoApp.ATIVO,
    EstadoApp.PRANCHA_CALIB_PREPARAR,
    EstadoApp.PRANCHA_CALIB_COLETANDO,
    EstadoApp.PRANCHA_ATIVO,
    EstadoApp.MODO_CUIDADOR,
)

# O aviso "Olhe para a tela" só faz sentido nas telas de uso/calibração;
# no Modo Cuidador o painel precisa continuar legível.
ESTADOS_AVISO_CABECA = (
    EstadoApp.CALIB_PREPARAR,
    EstadoApp.CALIB_COLETANDO,
    EstadoApp.ATIVO,
    EstadoApp.PRANCHA_CALIB_PREPARAR,
    EstadoApp.PRANCHA_CALIB_COLETANDO,
    EstadoApp.PRANCHA_ATIVO,
)

# Tempo mínimo que um novo cartão precisa permanecer como candidato antes
# de o foco trocar. Evita piscar entre dois cartões quando o olhar passa
# pela fronteira ou treme por um quadro.
HISTERESE_PRANCHA_MS = 120

# Tempo que o último rosto/olhar válido continua sendo exibido depois de
# um quadro sem detecção. O MediaPipe perde o rosto por um ou dois quadros
# ao piscar, falar ou mudar de expressão; sem essa retenção o status e o
# ponto do olhar piscavam entre "Rosto detectado" e "Sem rosto". A seleção
# NÃO usa este valor -- ela continua exigindo o rosto no quadro atual.
ROSTO_GRACE_MS = 700

# Piscadas duram ~120 ms. O status "Olhos fechados" só aparece quando os
# olhos permanecem fechados de verdade; assim o selo não pisca a cada
# piscada (a seleção continua usando a detecção imediata).
OLHOS_FECHADOS_EXIBICAO_MS = 350


# =====================================================================
# Protocolo (stdout)
# =====================================================================
def emitir(mensagem: dict) -> None:
    """Escreve uma mensagem JSON de uma linha no stdout, com flush."""
    try:
        linha = json.dumps(
            mensagem,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        logger.exception("Mensagem não serializável para a interface.")
        return
    sys.stdout.write(linha + "\n")
    sys.stdout.flush()


def emitir_status(etapa: str, texto: str) -> None:
    emitir({"tipo": "status", "etapa": etapa, "texto": texto})


def emitir_erro(texto: str) -> None:
    emitir({"tipo": "erro_fatal", "texto": texto})


# =====================================================================
# Tradução dos ajustes da interface (camelCase) para o YAML (snake_case)
# =====================================================================
def _conv_int(valor, nome: str) -> int:
    if isinstance(valor, bool):
        raise ValueError(f"{nome} deve ser um número inteiro")
    return round(float(valor))


def _conv_float(valor, nome: str) -> float:
    if isinstance(valor, bool):
        raise ValueError(f"{nome} deve ser um número")
    return float(valor)


def _conv_bool(valor, nome: str) -> bool:
    if not isinstance(valor, bool):
        raise ValueError(f"{nome} deve ser true/false")
    return valor


def _conv_texto(valor, nome: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nome} deve ser um texto não vazio")
    return valor.strip()


# O aviso "Olhe para a tela" só aparece depois de um tempo contínuo de
# cabeça fora de posição e some depois de um tempo contínuo de pose boa.
# Isso evita o pisca-pisca quando o yaw oscila em torno do limite.
ATRASO_AVISO_CABECA_S = 0.45
ATRASO_RECUPERACAO_CABECA_S = 0.35


def histerese_aviso_cabeca(
    mostrar: bool,
    desde_ruim: float | None,
    desde_boa: float | None,
    ativo: bool,
    agora: float,
) -> tuple[bool, float | None, float | None]:
    """Aplica atraso de entrada e saída ao aviso de cabeça fora de posição."""
    if not ativo:
        desde_ruim = None
        if mostrar:
            if desde_boa is None:
                desde_boa = agora
            elif agora - desde_boa >= ATRASO_RECUPERACAO_CABECA_S:
                mostrar = False
                desde_boa = None
        else:
            desde_boa = None
        return mostrar, desde_ruim, desde_boa

    desde_boa = None
    if desde_ruim is None:
        desde_ruim = agora
    elif agora - desde_ruim >= ATRASO_AVISO_CABECA_S:
        mostrar = True
    return mostrar, desde_ruim, desde_boa


def histerese_aviso_distancia(
    mostrar: bool,
    desde_ruim: float | None,
    desde_boa: float | None,
    ativo: bool,
    agora: float,
    entrada_s: float,
    saida_s: float,
) -> tuple[bool, float | None, float | None]:
    """
    Histerese do aviso de distância do rosto.

    O aviso só aparece depois de ``entrada_s`` segundos contínuos fora da
    faixa e só some depois de ``saida_s`` segundos contínuos dentro dela.
    Assim como o aviso de cabeça, isso evita pisca-pisca quando a medida
    oscila perto do limite. Os tempos vêm da configuração e são apenas
    informativos: não bloqueiam seleção nem calibração.
    """
    entrada_s = max(0.0, float(entrada_s))
    saida_s = max(0.0, float(saida_s))

    if not ativo:
        desde_ruim = None
        if mostrar:
            if desde_boa is None:
                desde_boa = agora
            elif agora - desde_boa >= saida_s:
                mostrar = False
                desde_boa = None
        else:
            desde_boa = None
        return mostrar, desde_ruim, desde_boa

    desde_boa = None
    if desde_ruim is None:
        desde_ruim = agora
    elif agora - desde_ruim >= entrada_s:
        mostrar = True
    return mostrar, desde_ruim, desde_boa


def aplicar_ajustes_config(cfg: dict, ajustes: dict) -> dict:
    """Devolve uma cópia de ``cfg`` com os ajustes editáveis aplicados."""
    if not isinstance(ajustes, dict):
        raise ValueError("Os ajustes devem ser um objeto")

    novo = copy.deepcopy(cfg)

    def secao(nome: str) -> dict:
        valor = ajustes.get(nome)
        if valor is None:
            return {}
        if not isinstance(valor, dict):
            raise ValueError(f"'{nome}' deve ser um objeto")
        return valor

    det = secao("deteccao")
    if det:
        d = novo["deteccao"]
        if "dwellMs" in det:
            d["dwell_ms"] = _conv_int(det["dwellMs"], "deteccao.dwellMs")
        if "toleranciaPerdaMs" in det:
            d["tolerancia_perda_ms"] = _conv_int(
                det["toleranciaPerdaMs"], "deteccao.toleranciaPerdaMs"
            )
        if "exibicaoConfirmacaoMs" in det:
            d["exibicao_confirmacao_ms"] = _conv_int(
                det["exibicaoConfirmacaoMs"], "deteccao.exibicaoConfirmacaoMs"
            )
        if "alphaEma" in det:
            d["alpha_ema"] = _conv_float(det["alphaEma"], "deteccao.alphaEma")
        if "tamanhoHistoricoGrafico" in det:
            d["tamanho_historico_grafico"] = _conv_int(
                det["tamanhoHistoricoGrafico"], "deteccao.tamanhoHistoricoGrafico"
            )
        if "semRostoMs" in det:
            d["sem_rosto_ms"] = _conv_int(
                det["semRostoMs"], "deteccao.semRostoMs"
            )
        elif "limiteFramesSemRosto" in det:
            # Compatibilidade com interfaces antigas: converte frames (~30
            # fps) para milissegundos, que é a unidade atual.
            d["sem_rosto_ms"] = max(
                100,
                round(_conv_int(
                    det["limiteFramesSemRosto"], "deteccao.limiteFramesSemRosto"
                ) / 30.0 * 1000.0),
            )
        if "divergenciaMax" in det:
            d["divergencia_max"] = _conv_float(
                det["divergenciaMax"], "deteccao.divergenciaMax"
            )
        if "compensarYaw" in det:
            d["compensar_yaw"] = _conv_bool(
                det["compensarYaw"], "deteccao.compensarYaw"
            )
        if "yawSensibilidade" in det:
            d["yaw_sensibilidade"] = _conv_float(
                det["yawSensibilidade"], "deteccao.yawSensibilidade"
            )
        if "confiancaMinima" in det:
            d["confianca_minima"] = _conv_float(
                det["confiancaMinima"], "deteccao.confiancaMinima"
            )
        if "distanciaHabilitada" in det:
            d["distancia_habilitada"] = _conv_bool(
                det["distanciaHabilitada"], "deteccao.distanciaHabilitada"
            )
        if "distanciaLongeAbaixo" in det:
            d["distancia_longe_abaixo"] = _conv_float(
                det["distanciaLongeAbaixo"], "deteccao.distanciaLongeAbaixo"
            )
        if "distanciaPertoAcima" in det:
            d["distancia_perto_acima"] = _conv_float(
                det["distanciaPertoAcima"], "deteccao.distanciaPertoAcima"
            )
        if "distanciaEntradaMs" in det:
            d["distancia_entrada_ms"] = _conv_int(
                det["distanciaEntradaMs"], "deteccao.distanciaEntradaMs"
            )
        if "distanciaSaidaMs" in det:
            d["distancia_saida_ms"] = _conv_int(
                det["distanciaSaidaMs"], "deteccao.distanciaSaidaMs"
            )
        p = d["piscada"]
        if "piscadaHabilitada" in det:
            p["habilitada"] = _conv_bool(
                det["piscadaHabilitada"], "deteccao.piscadaHabilitada"
            )
        if "limiarEar" in det:
            p["limiar_ear"] = _conv_float(det["limiarEar"], "deteccao.limiarEar")
        if "piscadaMs" in det:
            p["piscada_ms"] = _conv_int(det["piscadaMs"], "deteccao.piscadaMs")
        if "focoMinimoMs" in det:
            p["foco_minimo_ms"] = _conv_int(
                det["focoMinimoMs"], "deteccao.focoMinimoMs"
            )

    calib = secao("calibracao")
    if calib:
        c = novo["calibracao"]
        if "duracaoMs" in calib:
            c["duracao_ms"] = _conv_int(calib["duracaoMs"], "calibracao.duracaoMs")
        if "minAmostras" in calib:
            c["min_amostras"] = _conv_int(
                calib["minAmostras"], "calibracao.minAmostras"
            )
        if "maxYawGraus" in calib:
            c["max_yaw_graus"] = _conv_float(
                calib["maxYawGraus"], "calibracao.maxYawGraus"
            )
        if "maxPitchGraus" in calib:
            c["max_pitch_graus"] = _conv_float(
                calib["maxPitchGraus"], "calibracao.maxPitchGraus"
            )
        if "maxRollGraus" in calib:
            c["max_roll_graus"] = _conv_float(
                calib["maxRollGraus"], "calibracao.maxRollGraus"
            )
        if "diferencaMinima" in calib:
            c["diferenca_minima"] = _conv_float(
                calib["diferencaMinima"], "calibracao.diferencaMinima"
            )

    prancha = secao("prancha")
    if prancha:
        p = novo["prancha"]
        if "distanciaMinimaBoa" in prancha:
            p["distancia_minima_boa"] = _conv_float(
                prancha["distanciaMinimaBoa"], "prancha.distanciaMinimaBoa"
            )
        if "raioMax" in prancha:
            p["raio_max"] = _conv_float(prancha["raioMax"], "prancha.raioMax")

    cam = secao("camera")
    if cam:
        c = novo["camera"]
        if "indice" in cam:
            c["indice"] = _conv_int(cam["indice"], "camera.indice")
        if "largura" in cam:
            c["largura"] = _conv_int(cam["largura"], "camera.largura")
        if "altura" in cam:
            c["altura"] = _conv_int(cam["altura"], "camera.altura")
        if "fps" in cam:
            c["fps"] = _conv_int(cam["fps"], "camera.fps")
        if "backend" in cam:
            c["backend"] = _conv_texto(cam["backend"], "camera.backend")
        if "timeoutInicialMs" in cam:
            c["timeout_inicial_ms"] = _conv_int(
                cam["timeoutInicialMs"], "camera.timeoutInicialMs"
            )

    perfis = secao("perfis")
    if perfis and "validadeDias" in perfis:
        novo["perfis"]["validade_dias"] = _conv_int(
            perfis["validadeDias"], "perfis.validadeDias"
        )

    feedback = secao("feedback")
    if feedback and "som" in feedback:
        novo["feedback"]["som"] = _conv_bool(feedback["som"], "feedback.som")

    aparencia = secao("aparencia")
    if aparencia and "tema" in aparencia:
        novo["aparencia"]["tema"] = _conv_texto(
            aparencia["tema"], "aparencia.tema"
        )

    janela = secao("janela")
    if janela:
        j = novo["janela"]
        if "resolucao" in janela:
            j["resolucao"] = _conv_texto(janela["resolucao"], "janela.resolucao")
        if "fullscreen" in janela:
            j["fullscreen"] = _conv_bool(janela["fullscreen"], "janela.fullscreen")

    return novo


# =====================================================================
# Entrada de comandos (stdin)
# =====================================================================
class LeitorComandos:
    """Lê linhas JSON do stdin em uma thread separada."""

    def __init__(self) -> None:
        self.fila: queue.Queue[dict] = queue.Queue()
        self._thread = threading.Thread(target=self._ler, name="stdin", daemon=True)
        self._thread.start()

    def _ler(self) -> None:
        try:
            for linha in sys.stdin:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    comando = json.loads(linha)
                except json.JSONDecodeError:
                    logger.warning("Comando inválido ignorado: %.120s", linha)
                    continue
                if isinstance(comando, dict):
                    self.fila.put(comando)
        except (OSError, ValueError):
            pass
        finally:
            # EOF: a interface fechou. Encerra o motor.
            self.fila.put({"tipo": "_fim"})

    def drenar(self) -> list[dict]:
        itens: list[dict] = []
        while True:
            try:
                itens.append(self.fila.get_nowait())
            except queue.Empty:
                return itens


# =====================================================================
# Motor
# =====================================================================
class Motor:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.rodando = True
        self.simulador = bool(args.simular)

        self.dados = (
            Path(args.dados).expanduser().resolve()
            if args.dados
            else paths.pasta_dados()
        )
        self.dados.mkdir(parents=True, exist_ok=True)

        self.config_path = self._preparar_config(args.config)
        self.cfg = carregar_config(self.config_path)

        configurar_logging(
            pasta=self.dados / self.cfg["logs"]["pasta"],
            nivel=self.cfg["logs"]["nivel"],
        )
        logger.info(
            "Ponte iniciada (versão=%s, simulação=%s, config=%s, dados=%s).",
            VERSAO,
            self.simulador,
            self.config_path,
            self.dados,
        )

        det_cfg = self.cfg["deteccao"]
        self.cam_cfg = self.cfg["camera"]
        self.calib_cfg = self.cfg["calibracao"]
        self.prancha_cfg = self.cfg["prancha"]
        self.piscada_cfg = det_cfg["piscada"]
        self.diferenca_minima = self.calib_cfg["diferenca_minima"]
        self.distancia_minima_prancha = self.prancha_cfg["distancia_minima_boa"]
        self.raio_max_prancha = self.prancha_cfg["raio_max"]

        # --- câmera e detector -------------------------------------
        self.detector = None
        self.camera = None
        self.backend_camera = "simulado" if self.simulador else "nenhum"
        self.timestamp_ms = 0
        self.ultimo_frame_em: float | None = None
        self._frame_recebido_agora = False
        self._modelo_sem_iris_avisado = False
        # Fator para normalizar a medida de distância pela largura real do
        # conteúdo (compensa barras pretas em câmeras 4:3).
        self._escala_conteudo = 1.0

        if self.simulador:
            emitir_status("pronto", "Motor em modo de demonstração.")
        else:
            self._iniciar_camera_e_detector()

        # --- estado e persistência ---------------------------------
        self.calibrador = GerenciadorCalibracao(pasta=self.dados / self.cfg["perfis"]["pasta"])
        self.prancha_gerenciador = GerenciadorPrancha(
            pasta=self.dados / self.cfg["perfis"]["pasta"],
            distancia_minima_boa=self.distancia_minima_prancha,
        )
        self.feedback = FeedbackSonoro(habilitado=self.cfg["feedback"]["som"])

        self.app = AppState()
        self.controlador = self._criar_controlador()
        self.suavizador_esq = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])
        self.suavizador_dir = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])
        self.suavizador_y = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])
        self.suavizador_distancia = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])
        # A mediana corta picos isolados antes do EMA; só o eixo vertical
        # precisa dela (o horizontal já tem separação folgada).
        self.mediana_y = ge.MedianaMovel(5)

        self.historico_esq: deque[float] = deque(maxlen=det_cfg["tamanho_historico_grafico"])
        self.historico_dir: deque[float] = deque(maxlen=det_cfg["tamanho_historico_grafico"])

        # Caches: evitam varrer a pasta de perfis e remontar a configuração
        # a cada snapshot (30 vezes por segundo).
        self._perfis_cache: list[str] | None = None
        self._config_resumo_cache: dict | None = None

        # Últimos valores de detecção, usados no snapshot.
        self.rosto_detectado = False
        self.pose_confiavel = True
        self.olhos_fechados = False
        self.ratio_esq = 0.5
        self.ratio_dir = 0.5
        self.ratio_valido = 0.5
        self.ratio_y_valido = 0.5
        self.divergencia = 0.0
        self.divergencia_ok = True
        self.distancia_rosto = 0.0
        self.distancia_estado = ge.DISTANCIA_INDEFINIDA
        self.distancia_aviso = False
        self._distancia_ruim_desde: float | None = None
        self._distancia_boa_desde: float | None = None
        self.lado_detectado: str | None = None
        # Último lado válido (Esquerda/Direita) para a piscada no SIM/NÃO.
        self.lado_estavel: str | None = None
        self.decisao = DecisaoSelecao()
        # Cartão estável do olhar na prancha, com histerese. É usado pela
        # seleção, pelo ponto do olhar e pelo Mapa do Cuidador.
        self.bloco_prancha: str | None = None
        self._bloco_prancha_estavel: str | None = None
        self._candidato_prancha: str | None = None
        self._candidato_prancha_desde: float | None = None
        self.aviso_sem_rosto = False
        self._sem_rosto_desde: float | None = None
        # Último quadro confiável, repetido por ROSTO_GRACE_MS no snapshot
        # para a interface não piscar quando o detector perde o rosto.
        self._rosto_visto_em: float | None = None
        self._gaze_exibicao = (0.5, 0.5)
        self._pose_exibicao = True
        self._distancia_estado_exibicao = ge.DISTANCIA_INDEFINIDA
        self._distancia_rosto_exibicao = 0.0
        self._olhos_fechados_desde: float | None = None
        self.aviso_cabeca = False
        self._cabeca_ruim_desde: float | None = None
        self._cabeca_boa_desde: float | None = None
        # Uma recentralização pode ser desfeita enquanto o perfil atual
        # não mudar nem passar por uma nova calibração completa.
        self._recentralizacao_anterior: dict[str, tuple[float, float]] | None = None

        # Simulação controlada por comandos (apenas para testes/demonstração).
        self.sim_camera_ok = True
        self.sim_rosto = True
        self.sim_pose = True
        self.sim_olhos = False
        self.sim_x = 0.5
        self.sim_y = 0.5
        self.sim_distancia = 0.20

        # Perfil "padrao" carregado automaticamente, como no main.py.
        dados_sim_padrao = self.calibrador.carregar("padrao")
        dados_prancha_padrao = self.prancha_gerenciador.carregar("padrao")
        if dados_sim_padrao is not None or dados_prancha_padrao is not None:
            self._aplicar_perfil("padrao", dados_sim_padrao, dados_prancha_padrao)
            logger.info("Perfil padrão carregado.")

        self.leitor = LeitorComandos()
        emitir({"tipo": "pronto", "versao": VERSAO, "simulacao": self.simulador})

    # -----------------------------------------------------------------
    # Inicialização
    # -----------------------------------------------------------------
    def _preparar_config(self, caminho: str | None) -> Path | None:
        if not caminho:
            return None
        destino = Path(caminho).expanduser()
        if destino.exists():
            return destino
        origem = paths.resolver_recurso("config/settings.yaml")
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            if origem.exists():
                shutil.copyfile(origem, destino)
                logger.info("Configuração padrão copiada para '%s'.", destino)
        except OSError as e:
            logger.warning("Não foi possível criar '%s': %s", destino, e)
            return None
        return destino

    def _iniciar_camera_e_detector(self) -> None:
        emitir_status("modelo", "Carregando o modelo de rastreamento...")
        modelo_cfg = self.cfg["modelo"]
        caminho_modelo = paths.resolver_modelo(modelo_cfg["caminho"])
        try:
            if not caminho_modelo.exists():
                caminho_modelo = garantir_modelo_baixado(
                    caminho_modelo,
                    modelo_cfg["url"],
                    modelo_cfg.get("sha256_esperado", ""),
                )
            self.detector = self._montar_detector(
                str(caminho_modelo),
                self.cfg["deteccao"]["confianca_minima"],
            )
        except Exception as e:
            logger.exception("Falha ao carregar o detector.")
            emitir_erro(
                "Não foi possível carregar o modelo do MediaPipe.\n"
                f"Arquivo: {caminho_modelo}\nErro: {e}"
            )
            raise SystemExit(1) from e

        emitir_status("camera", "Abrindo a câmera...")
        from core.camera_thread import CameraStream

        try:
            self.camera = CameraStream(
                self.cam_cfg["indice"],
                self.cam_cfg["largura"],
                self.cam_cfg["altura"],
                self.cam_cfg["fps"],
                backend=self.cam_cfg["backend"],
                timeout_inicial_s=self.cam_cfg["timeout_inicial_ms"] / 1000.0,
                tolerante=True,
            )
            self.backend_camera = self.camera.backend_em_uso
        except Exception:
            logger.exception("Falha inesperada ao abrir a câmera.")
            self.camera = None
            self.backend_camera = "nenhum"
        if self.backend_camera == "nenhum":
            logger.warning("Iniciando sem imagens da câmera.")

    @staticmethod
    def _montar_detector(caminho_modelo: str, confianca_minima: float = 0.5):
        # O MediaPipe importa matplotlib (para desenho de resultados), mas o
        # aplicativo nunca exibe gráficos. Força um backend headless para
        # não depender de Tk/Qt no Windows empacotado.
        os.environ.setdefault("MPLBACKEND", "Agg")
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        confianca = min(max(float(confianca_minima), 0.05), 1.0)
        base_options = mp_python.BaseOptions(model_asset_path=caminho_modelo)
        opcoes = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=confianca,
            min_face_presence_confidence=confianca,
            min_tracking_confidence=confianca,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
        )
        detector = mp_vision.FaceLandmarker.create_from_options(opcoes)
        logger.info(
            "MediaPipe %s carregado (confiança mínima=%.2f).",
            mp.__version__,
            confianca,
        )
        return detector

    def _criar_controlador(self) -> ControladorSelecao:
        det = self.cfg["deteccao"]
        return ControladorSelecao(
            dwell_ms=det["dwell_ms"],
            tolerancia_perda_ms=det["tolerancia_perda_ms"],
            piscada_habilitada=det["piscada"]["habilitada"],
            piscada_ms=det["piscada"]["piscada_ms"],
            foco_minimo_ms=det["piscada"]["foco_minimo_ms"],
            exibicao_confirmacao_ms=det["exibicao_confirmacao_ms"],
        )

    # -----------------------------------------------------------------
    # Utilidades de estado
    # -----------------------------------------------------------------
    def camera_pronta(self) -> bool:
        if self.simulador:
            return self.sim_camera_ok
        if self.camera is None:
            return False
        return self.camera.backend_em_uso != "nenhum" and self.camera.segundos_sem_frame() <= 2.0

    def segundos_sem_frame(self) -> float | None:
        if self.simulador:
            return 0.0 if self.sim_camera_ok else 999.0
        if self.camera is None:
            return None
        segundos = self.camera.segundos_sem_frame()
        if segundos == float("inf"):
            return None
        return float(segundos)

    def _reiniciar_filtros(self) -> None:
        self.suavizador_esq.reset()
        self.suavizador_dir.reset()
        self.suavizador_y.reset()
        self.mediana_y.reset()
        self.suavizador_distancia.reset()
        self.historico_esq.clear()
        self.historico_dir.clear()
        self.bloco_prancha = None
        self._bloco_prancha_estavel = None
        self._candidato_prancha = None
        self._candidato_prancha_desde = None
        self.lado_estavel = None
        self.distancia_rosto = 0.0
        self.distancia_estado = ge.DISTANCIA_INDEFINIDA
        self.distancia_aviso = False
        self._distancia_ruim_desde = None
        self._distancia_boa_desde = None

    def _perfis_disponiveis(self) -> list[str]:
        if self._perfis_cache is None:
            self._perfis_cache = sorted(
                set(self.calibrador.listar_perfis())
                | set(self.prancha_gerenciador.listar_perfis())
            )
        return list(self._perfis_cache)

    def _restaurar_calibracao_salva(self) -> None:
        """Recarrega do disco a calibração do perfil ativo, se houver."""
        nome = self.app.perfil_ativo
        if not nome:
            return
        try:
            dados_sim = self.calibrador.carregar(nome)
            dados_prancha = self.prancha_gerenciador.carregar(nome)
        except (ValueError, OSError) as e:
            logger.warning("Falha ao recarregar a calibração de '%s': %s", nome, e)
            return
        self._aplicar_perfil(nome, dados_sim, dados_prancha)

    def _aplicar_perfil(self, nome: str, dados_sim: dict | None, dados_prancha: dict | None) -> None:
        self.app.perfil_ativo = nome
        self._recentralizacao_anterior = None

        if dados_sim is not None:
            self.app.media_esquerda_calibrada = float(dados_sim["media_esquerda"])
            self.app.media_direita_calibrada = float(dados_sim["media_direita"])
            self.app.calibracao_ja_feita = True
            diferenca = abs(
                self.app.media_direita_calibrada - self.app.media_esquerda_calibrada
            )
            self.app.calibracao_fraca = diferenca < self.diferenca_minima
            if self.calibrador.calibracao_esta_vencida(
                dados_sim, self.cfg["perfis"]["validade_dias"]
            ):
                logger.info("Calibração SIM/NÃO de '%s' vencida.", nome)
        else:
            self.app.media_esquerda_calibrada = 0.35
            self.app.media_direita_calibrada = 0.65
            self.app.calibracao_ja_feita = False
            self.app.calibracao_fraca = False

        if dados_prancha is not None:
            self.app.referencias_prancha = pontos_do_dados(dados_prancha)
            self.app.prancha_fraca = dados_prancha["qualidade"] != "boa"
            self.app.prancha_calibrada = not self.app.prancha_fraca
            if self.prancha_gerenciador.calibrar_vencida(
                dados_prancha, self.cfg["perfis"]["validade_dias"]
            ):
                logger.info("Prancha de '%s' vencida.", nome)
        else:
            self.app.referencias_prancha = {}
            self.app.prancha_calibrada = False
            self.app.prancha_fraca = False

    # -----------------------------------------------------------------
    # Ações (equivalentes às teclas do main.py)
    # -----------------------------------------------------------------
    def entrar_na_prancha(self, agora: float) -> None:
        if not self.camera_pronta():
            self.app.avisar("Sem sinal da câmera. Verifique a webcam.", agora)
            return
        if not self.app.prancha_valida(self.distancia_minima_prancha):
            self.app.avisar("Prancha sem calibração. Use Calibração para calibrar.", agora)
            return
        self.app.resetar_selecao()
        self.controlador.reset()
        self._reiniciar_filtros()
        self.app.transicionar(EstadoApp.PRANCHA_ATIVO)
        logger.info("Prancha iniciada (perfil=%s).", self.app.perfil_ativo or "padrão")

    def iniciar_calibracao_prancha(self, agora: float) -> None:
        if not self.camera_pronta():
            self.app.avisar("Sem sinal da câmera. Verifique a webcam.", agora)
            return
        self._recentralizacao_anterior = None
        self.app.resetar_prancha()
        self._reiniciar_filtros()
        self.app.transicionar(EstadoApp.PRANCHA_CALIB_PREPARAR)
        logger.info("Calibração da prancha iniciada.")

    def _salvar_prancha_atual(self, agora: float) -> bool:
        """Persiste as referências atuais e recalcula a qualidade da prancha."""
        try:
            self.prancha_gerenciador.salvar(
                self.app.perfil_ativo or "padrao",
                self.app.referencias_prancha,
            )
        except (ValueError, OSError) as e:
            logger.error("Falha ao salvar o ajuste da prancha: %s", e)
            self.app.avisar("Não foi possível salvar o ajuste da prancha.", agora)
            self.feedback.erro()
            return False

        distancia = board.distancia_minima_entre_pontos(self.app.referencias_prancha)
        self.app.prancha_fraca = distancia < self.distancia_minima_prancha
        self.app.prancha_calibrada = not self.app.prancha_fraca
        self._perfis_cache = None
        return True

    def recentralizar_prancha(self, dx: float, dy: float, agora: float) -> None:
        """
        Desloca todas as referências por ``(dx, dy)``.

        O cuidador coleta um único cartão conhecido no Modo Cuidador. Se o
        olhar medido ficou deslocado do ponto salvo, somar esse deslocamento
        a todos os cartões recentraliza o mapa sem refazer a calibração
        completa. A operação é persistida e pode ser desfeita uma vez.
        """
        if len(self.app.referencias_prancha) < len(board.BLOCOS):
            self.app.avisar("Calibre a prancha antes de recentralizar.", agora)
            self.feedback.erro()
            return
        try:
            novas = board.transladar_referencias(
                self.app.referencias_prancha, dx, dy
            )
        except (TypeError, ValueError) as e:
            logger.warning("Recentralização recusada: %s", e)
            self.app.avisar(f"Recentralização recusada: {e}.", agora, 4.0)
            self.feedback.erro()
            return

        anterior = dict(self.app.referencias_prancha)
        self.app.referencias_prancha = novas
        if not self._salvar_prancha_atual(agora):
            self.app.referencias_prancha = anterior
            return

        self._recentralizacao_anterior = anterior
        logger.info(
            "Prancha recentralizada (dx=%.4f, dy=%.4f, perfil=%s).",
            float(dx),
            float(dy),
            self.app.perfil_ativo or "padrao",
        )
        self.app.avisar("Olhar recentralizado.", agora)
        self.feedback.confirmar()

    def desfazer_recentralizacao(self, agora: float) -> None:
        """Restaura as referências anteriores à última recentralização."""
        anterior = self._recentralizacao_anterior
        if not anterior:
            self.app.avisar("Nada para desfazer.", agora)
            return

        atual = dict(self.app.referencias_prancha)
        self.app.referencias_prancha = dict(anterior)
        if not self._salvar_prancha_atual(agora):
            self.app.referencias_prancha = atual
            return

        self._recentralizacao_anterior = None
        logger.info("Recentralização desfeita (perfil=%s).", self.app.perfil_ativo or "padrao")
        self.app.avisar("Recentralização desfeita.", agora)
        self.feedback.confirmar()

    def entrar_no_modo_ativo(self, agora: float) -> None:
        if not self.camera_pronta():
            self.app.avisar("Sem sinal da câmera. Verifique a webcam.", agora)
            return
        if not self.app.calibracao_valida(self.diferenca_minima):
            self.app.avisar("Calibração ausente ou fraca. Use Calibração SIM/NÃO.", agora)
            return
        self.app.resetar_selecao()
        self.controlador.reset()
        self._reiniciar_filtros()
        self.app.transicionar(EstadoApp.ATIVO)
        logger.info("Modo SIM/NÃO iniciado (perfil=%s).", self.app.perfil_ativo or "padrão")

    def iniciar_calibracao(self, agora: float) -> None:
        if not self.camera_pronta():
            self.app.avisar("Sem sinal da câmera. Verifique a webcam.", agora)
            return
        self.app.resetar_calibracao()
        self._reiniciar_filtros()
        self.app.transicionar(EstadoApp.CALIB_PREPARAR)
        logger.info("Calibração SIM/NÃO iniciada.")

    def iniciar_coleta(self, agora: float) -> None:
        if self.app.estado == EstadoApp.PRANCHA_CALIB_PREPARAR:
            self.app.coletas_prancha = []
            self.app.amostras_ignoradas = 0
            self.app.tempo_inicio_coleta_prancha = agora
            self._reiniciar_filtros()
            self.app.transicionar(EstadoApp.PRANCHA_CALIB_COLETANDO)
        elif self.app.estado == EstadoApp.CALIB_PREPARAR:
            self.app.transicionar(EstadoApp.CALIB_COLETANDO)
            self.app.coletas_calibracao = []
            self.app.amostras_ignoradas = 0
            self.app.tempo_inicio_coleta = agora
            self.app.calibracao_ja_feita = False
            self._reiniciar_filtros()

    def voltar_menu(self) -> None:
        estado = self.app.estado
        if estado == EstadoApp.NOVO_PERFIL:
            self.app.nome_digitado = ""
            self.app.transicionar(EstadoApp.SELECIONAR_PERFIL)
            return

        if estado in (
            EstadoApp.PRANCHA_CALIB_COLETANDO,
            EstadoApp.PRANCHA_CALIB_PREPARAR,
            EstadoApp.CALIB_COLETANDO,
            EstadoApp.CALIB_PREPARAR,
        ):
            # Sair no meio da coleta não pode apagar a calibração que já
            # estava salva no perfil: descarta a coleta e recarrega o disco.
            self.app.resetar_prancha()
            self.app.resetar_calibracao()
            self._recentralizacao_anterior = None
            self._restaurar_calibracao_salva()
        if estado in (EstadoApp.ATIVO, EstadoApp.PRANCHA_ATIVO):
            self.controlador.reset()
            self.app.resetar_selecao()
        if estado in (
            EstadoApp.PRANCHA_CALIB_COLETANDO,
            EstadoApp.PRANCHA_CALIB_PREPARAR,
            EstadoApp.CALIB_COLETANDO,
            EstadoApp.CALIB_PREPARAR,
        ):
            self._reiniciar_filtros()
        self.app.transicionar(EstadoApp.MENU)

    def selecionar_perfil(self, nome: str, agora: float) -> None:
        nome = (nome or "").strip()
        if nome not in self._perfis_disponiveis():
            self.app.avisar(f"Perfil '{nome}' não encontrado.", agora)
            self.feedback.erro()
            return
        dados_sim = self.calibrador.carregar(nome)
        dados_prancha = self.prancha_gerenciador.carregar(nome)
        if dados_sim is None and dados_prancha is None:
            self.app.avisar(f"Perfil '{nome}' inválido ou corrompido.", agora)
            self.feedback.erro()
            return
        self._aplicar_perfil(nome, dados_sim, dados_prancha)
        if self.app.prancha_fraca:
            self.app.avisar(
                f"Prancha fraca em '{nome}' -- recalibre a prancha.",
                agora,
                4.0,
            )
            self.feedback.erro()
        logger.info("Perfil '%s' carregado.", nome)
        self.app.transicionar(EstadoApp.MENU)

    def criar_perfil(self, nome: str, agora: float) -> None:
        nome = (nome or "").strip()
        if not nome:
            self.app.avisar("Digite um nome para o perfil.", agora)
            self.feedback.erro()
            return
        if not all(c.isalnum() or c in ("_", "-") for c in nome) or len(nome) > 20:
            self.app.avisar("Use letras, números, '_' ou '-' (máximo 20).", agora)
            self.feedback.erro()
            return
        if nome in self._perfis_disponiveis():
            self.app.avisar(f"O perfil '{nome}' já existe.", agora)
            self.feedback.erro()
            return

        self.app.perfil_ativo = nome
        self.app.nome_digitado = ""
        self.app.media_esquerda_calibrada = 0.35
        self.app.media_direita_calibrada = 0.65
        self.app.calibracao_ja_feita = False
        self._recentralizacao_anterior = None
        self.app.resetar_calibracao()
        self.app.resetar_prancha()
        self._reiniciar_filtros()
        self._perfis_cache = None
        self.app.transicionar(EstadoApp.PRANCHA_CALIB_PREPARAR)
        logger.info("Novo perfil '%s' criado.", nome)

    def definir_simulacao(self, ativa: bool) -> None:
        if ativa == self.simulador:
            return
        if not ativa and self.detector is None:
            # Sem câmera/detector real não há como desligar a simulação.
            self.app.avisar("Simulação só pode ser desligada com câmera disponível.", time.monotonic())
            return
        self.simulador = ativa
        self.backend_camera = "simulado" if ativa else (
            self.camera.backend_em_uso if self.camera else "nenhum"
        )
        self.controlador.reset()
        self.app.resetar_selecao()
        self._reiniciar_filtros()
        logger.info("Simulação %s.", "ativada" if ativa else "desativada")

    def atualizar_config(self, ajustes: dict, agora: float) -> None:
        """Valida, persiste e aplica os ajustes editados na interface."""
        try:
            novo = aplicar_ajustes_config(self.cfg, ajustes)
            validar_config(novo)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Ajustes rejeitados: %s", e)
            self.app.avisar(f"Configuração inválida: {e}", agora)
            self.feedback.erro()
            return

        caminho = self.config_path or (self.dados / "settings.yaml")
        try:
            salvar_config(novo, caminho)
        except (OSError, ValueError) as e:
            logger.error("Falha ao salvar a configuração: %s", e)
            self.app.avisar("Não foi possível salvar as configurações.", agora)
            self.feedback.erro()
            return

        camera_mudou = novo["camera"] != self.cfg["camera"]
        self.config_path = Path(caminho)
        self.cfg = novo
        self._aplicar_config_em_memoria()

        if camera_mudou:
            self.app.avisar(
                "Configurações salvas. Reinicie o aplicativo para aplicar "
                "as mudanças de câmera.",
                agora,
                duracao=5.0,
            )
        else:
            self.app.avisar("Configurações salvas.", agora)
        self.feedback.confirmar()

    def _aplicar_config_em_memoria(self) -> None:
        """Atualiza os componentes vivos depois de salvar a configuração."""
        det = self.cfg["deteccao"]
        self.cam_cfg = self.cfg["camera"]
        self.calib_cfg = self.cfg["calibracao"]
        self.prancha_cfg = self.cfg["prancha"]
        self.piscada_cfg = det["piscada"]
        self.diferenca_minima = self.calib_cfg["diferenca_minima"]
        self.distancia_minima_prancha = self.prancha_cfg["distancia_minima_boa"]
        self.raio_max_prancha = self.prancha_cfg["raio_max"]

        self.controlador.dwell_ms = int(det["dwell_ms"])
        self.controlador.tolerancia_perda_ms = int(det["tolerancia_perda_ms"])
        self.controlador.piscada_habilitada = bool(self.piscada_cfg["habilitada"])
        self.controlador.piscada_ms = int(self.piscada_cfg["piscada_ms"])
        self.controlador.foco_minimo_ms = int(self.piscada_cfg["foco_minimo_ms"])
        self.controlador.exibicao_confirmacao_ms = int(
            det["exibicao_confirmacao_ms"]
        )
        self.controlador.reset()
        self.app.resetar_selecao()
        self.decisao = DecisaoSelecao()

        alpha = float(det["alpha_ema"])
        for suavizador in (
            self.suavizador_esq,
            self.suavizador_dir,
            self.suavizador_y,
            self.suavizador_distancia,
        ):
            suavizador.alpha = alpha

        tamanho = int(det["tamanho_historico_grafico"])
        if self.historico_esq.maxlen != tamanho:
            self.historico_esq = deque(list(self.historico_esq)[-tamanho:], maxlen=tamanho)
            self.historico_dir = deque(list(self.historico_dir)[-tamanho:], maxlen=tamanho)

        self.feedback.habilitado = bool(self.cfg["feedback"]["som"])
        self.prancha_gerenciador.distancia_minima_boa = (
            self.distancia_minima_prancha
        )
        if not det["distancia_habilitada"]:
            self.distancia_estado = ge.DISTANCIA_INDEFINIDA
            self.distancia_aviso = False
            self._distancia_ruim_desde = None
            self._distancia_boa_desde = None
        self._config_resumo_cache = None
        logger.info(
            "Configuração aplicada (dwell=%dms, câmera=%dx%d@%d, resolução=%s).",
            int(det["dwell_ms"]),
            int(self.cam_cfg["largura"]),
            int(self.cam_cfg["altura"]),
            int(self.cam_cfg["fps"]),
            self.cfg["janela"]["resolucao"],
        )

    # -----------------------------------------------------------------
    # Comandos
    # -----------------------------------------------------------------
    def aplicar_comando(self, comando: dict, agora: float) -> None:
        tipo = comando.get("tipo")
        if tipo == "_fim" or tipo == "sair":
            self.rodando = False
        elif tipo == "abrir_prancha":
            self.entrar_na_prancha(agora)
        elif tipo == "abrir_sim_nao":
            self.entrar_no_modo_ativo(agora)
        elif tipo == "abrir_calibracao":
            self.app.transicionar(EstadoApp.ESCOLHER_CALIBRACAO)
        elif tipo == "calibrar_prancha":
            self.iniciar_calibracao_prancha(agora)
        elif tipo == "calibrar_sim_nao":
            self.iniciar_calibracao(agora)
        elif tipo == "abrir_perfis":
            self.app.transicionar(EstadoApp.SELECIONAR_PERFIL)
        elif tipo == "novo_perfil":
            self.app.nome_digitado = str(comando.get("nome", ""))[:20]
            self.app.transicionar(EstadoApp.NOVO_PERFIL)
        elif tipo == "modo_cuidador":
            self.app.transicionar(EstadoApp.MODO_CUIDADOR)
        elif tipo == "configuracoes":
            self.app.transicionar(EstadoApp.CONFIGURACOES)
        elif tipo == "iniciar_coleta":
            self.iniciar_coleta(agora)
        elif tipo == "recentralizar":
            try:
                dx = float(comando.get("dx", 0.0))
                dy = float(comando.get("dy", 0.0))
            except (TypeError, ValueError):
                dx = dy = float("nan")
            self.recentralizar_prancha(dx, dy, agora)
        elif tipo == "desfazer_recentralizacao":
            self.desfazer_recentralizacao(agora)
        elif tipo == "atualizar_config":
            self.atualizar_config(comando.get("config") or {}, agora)
        elif tipo == "voltar":
            self.voltar_menu()
        elif tipo == "selecionar_perfil":
            self.selecionar_perfil(str(comando.get("nome", "")), agora)
        elif tipo == "criar_perfil":
            self.criar_perfil(str(comando.get("nome", "")), agora)
        elif tipo == "definir_simulacao":
            self.definir_simulacao(bool(comando.get("ativa")))
        elif tipo == "simular_camera":
            self.sim_camera_ok = bool(comando.get("ok", True))
        elif tipo == "simular_rosto":
            self.sim_rosto = bool(comando.get("ok", True))
            self.sim_pose = bool(comando.get("poseOk", self.sim_pose))
            self.sim_olhos = bool(comando.get("olhosFechados", self.sim_olhos))
        elif tipo == "simular_olhar":
            self.sim_x = float(comando.get("x", self.sim_x))
            self.sim_y = float(comando.get("y", self.sim_y))
        elif tipo == "simular_distancia":
            self.sim_distancia = float(comando.get("valor", self.sim_distancia))
        else:
            logger.debug("Comando desconhecido: %s", tipo)

    # -----------------------------------------------------------------
    # Detecção
    # -----------------------------------------------------------------
    def _preparar_frame(self, frame):
        import cv2

        altura_atual, largura_atual = frame.shape[:2]
        if (largura_atual, altura_atual) == (LARGURA_PROJETO, ALTURA_PROJETO):
            self._escala_conteudo = 1.0
            return frame
        escala = min(LARGURA_PROJETO / largura_atual, ALTURA_PROJETO / altura_atual)
        nova_largura = max(1, round(largura_atual * escala))
        nova_altura = max(1, round(altura_atual * escala))
        self._escala_conteudo = LARGURA_PROJETO / nova_largura
        redimensionado = cv2.resize(
            frame, (nova_largura, nova_altura), interpolation=cv2.INTER_LINEAR
        )
        canvas = np.zeros((ALTURA_PROJETO, LARGURA_PROJETO, 3), dtype=frame.dtype)
        x = (LARGURA_PROJETO - nova_largura) // 2
        y = (ALTURA_PROJETO - nova_altura) // 2
        canvas[y:y + nova_altura, x:x + nova_largura] = redimensionado
        return canvas

    def _ler_frame(self):
        if self.simulador:
            self._frame_recebido_agora = self.sim_camera_ok
            return None
        if self.camera is None:
            self._frame_recebido_agora = False
            return None
        try:
            quadro = self.camera.ler(timeout=0.02)
        except queue.Empty:
            self._frame_recebido_agora = False
            return None
        self._frame_recebido_agora = True
        import cv2

        return self._preparar_frame(cv2.flip(quadro, 1))

    def _detectar(self, frame_proc) -> None:
        import cv2
        import mediapipe as mp

        self.rosto_detectado = False
        self.pose_confiavel = True
        self.olhos_fechados = False
        self.ratio_esq = 0.5
        self.ratio_dir = 0.5
        self.ratio_valido = 0.5
        self.ratio_y_valido = 0.5
        self.divergencia = 0.0
        self.divergencia_ok = True
        self.distancia_estado = ge.DISTANCIA_INDEFINIDA
        self.lado_detectado = None
        self.bloco_prancha = None

        rgb = cv2.cvtColor(frame_proc, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # O MediaPipe espera milissegundos reais e estritamente crescentes
        # no modo VIDEO. O relógio monotônico evita o grafo achar que roda
        # a 1000 fps (o antigo +1 por frame) sem repetir valores.
        timestamp = int(time.monotonic() * 1000)
        if timestamp <= self.timestamp_ms:
            timestamp = self.timestamp_ms + 1
        self.timestamp_ms = timestamp
        resultado = self.detector.detect_for_video(mp_image, timestamp)

        if not resultado.face_landmarks:
            return

        landmarks = resultado.face_landmarks[0]
        # Os índices de íris (469..477) exigem o modelo com 478 pontos.
        # Um modelo antigo/sem íris estouraria IndexError e encerraria o
        # motor; aqui o quadro é ignorado e o aviso aparece uma única vez.
        if len(landmarks) < 478:
            if not self._modelo_sem_iris_avisado:
                logger.error(
                    "Modelo facial com %d pontos (esperado >= 478, com íris). "
                    "Atualize models/face_landmarker.task.",
                    len(landmarks),
                )
                self._modelo_sem_iris_avisado = True
            return

        self.rosto_detectado = True

        ratio_esq_bruto = ge.calcular_ratio_iris_x(
            landmarks,
            ge.OLHO_ESQUERDO_CANTOS,
            ge.IRIS_ESQUERDA,
            LARGURA_PROJETO,
            ALTURA_PROJETO,
        )
        ratio_dir_bruto = ge.calcular_ratio_iris_x(
            landmarks,
            ge.OLHO_DIREITO_CANTOS,
            ge.IRIS_DIREITA,
            LARGURA_PROJETO,
            ALTURA_PROJETO,
        )

        det_cfg = self.cfg["deteccao"]
        yaw = pitch = roll = 0.0
        if resultado.facial_transformation_matrixes:
            yaw, pitch, roll = ge.extrair_angulos_da_matriz(
                resultado.facial_transformation_matrixes[0]
            )
            self.pose_confiavel = ge.pose_dentro_dos_limites(
                yaw,
                pitch,
                roll,
                self.calib_cfg["max_yaw_graus"],
                self.calib_cfg["max_pitch_graus"],
                self.calib_cfg["max_roll_graus"],
            )
            # Compensação opcional: desligada por padrão para não somar uma
            # correção à normalização que o ratio já faz dentro do olho.
            if det_cfg["compensar_yaw"]:
                sensibilidade = det_cfg["yaw_sensibilidade"]
                ratio_esq_bruto = ge.compensar_ratio_por_yaw(
                    ratio_esq_bruto, yaw, sensibilidade
                )
                ratio_dir_bruto = ge.compensar_ratio_por_yaw(
                    ratio_dir_bruto, yaw, sensibilidade
                )

        # Indicador informativo de distância: usa os cantos externos dos
        # olhos e compensa o yaw. Não entra em nenhuma regra de seleção ou
        # calibração -- serve apenas para orientar o cuidador.
        if det_cfg["distancia_habilitada"] and self.pose_confiavel:
            medida = ge.distancia_rosto_normalizada(
                landmarks,
                LARGURA_PROJETO,
                ALTURA_PROJETO,
                yaw,
            )
            self.distancia_rosto = self.suavizador_distancia.atualizar(
                medida * self._escala_conteudo
            )
            self.distancia_estado = ge.classificar_distancia(
                self.distancia_rosto,
                det_cfg["distancia_longe_abaixo"],
                det_cfg["distancia_perto_acima"],
            )
        else:
            self.distancia_rosto = 0.0
            self.distancia_estado = ge.DISTANCIA_INDEFINIDA

        self.ratio_esq = self.suavizador_esq.atualizar(ratio_esq_bruto)
        self.ratio_dir = self.suavizador_dir.atualizar(ratio_dir_bruto)
        self.ratio_valido = (self.ratio_esq + self.ratio_dir) / 2

        # Quadro confiável: os dois olhos precisam apontar para o mesmo
        # lugar. Divergência grande costuma ser piscada, oclusão, reflexo
        # ou ruído -- não deve mover o dwell nem entrar na calibração.
        self.divergencia = ge.divergencia_entre_olhos(self.ratio_esq, self.ratio_dir)
        try:
            self.divergencia_ok = ge.divergencia_dentro_do_limite(
                self.ratio_esq,
                self.ratio_dir,
                self.cfg["deteccao"]["divergencia_max"],
            )
        except ValueError:
            self.divergencia_ok = False

        ratio_y_bruto = (
            ge.calcular_ratio_iris_y_cantos(
                landmarks,
                ge.OLHO_ESQUERDO_CANTOS,
                ge.IRIS_ESQUERDA,
                LARGURA_PROJETO,
                ALTURA_PROJETO,
            )
            + ge.calcular_ratio_iris_y_cantos(
                landmarks,
                ge.OLHO_DIREITO_CANTOS,
                ge.IRIS_DIREITA,
                LARGURA_PROJETO,
                ALTURA_PROJETO,
            )
        ) / 2
        # Mediana antes do EMA: descarta o pico de um quadro sem atrasar
        # o movimento como faria uma média longa.
        self.ratio_y_valido = self.suavizador_y.atualizar(
            self.mediana_y.atualizar(ratio_y_bruto)
        )

        ear_esq = ge.calcular_ear(
            landmarks,
            ge.OLHO_ESQUERDO_VERTICAL,
            ge.OLHO_ESQUERDO_CANTOS,
            LARGURA_PROJETO,
            ALTURA_PROJETO,
        )
        ear_dir = ge.calcular_ear(
            landmarks,
            ge.OLHO_DIREITO_VERTICAL,
            ge.OLHO_DIREITO_CANTOS,
            LARGURA_PROJETO,
            ALTURA_PROJETO,
        )
        ear_medio = (ear_esq + ear_dir) / 2
        self.olhos_fechados = ge.olho_fechado(ear_medio, self.piscada_cfg["limiar_ear"])

        # Cartão da prancha: projeta o olhar na grade calibrada e aplica
        # histerese. Com os olhos fechados mantém o último cartão estável,
        # para a piscada confirmar o que a pessoa já estava olhando em vez
        # de zerar o foco (a íris se mexe durante a piscada).
        agora_deteccao = timestamp / 1000.0
        if self.olhos_fechados:
            self.bloco_prancha = self._bloco_prancha_estavel
        else:
            bruto = None
            if (
                self.pose_confiavel
                and self.divergencia_ok
                and self.app.referencias_prancha
            ):
                bruto = board.classificar_unidade(
                    self.ratio_valido,
                    self.ratio_y_valido,
                    self.app.referencias_prancha,
                )
            self.bloco_prancha = self._estabilizar_bloco(bruto, agora_deteccao)

        if self.pose_confiavel:
            self.lado_detectado = ge.classificar_lado(
                self.ratio_valido,
                self.app.media_esquerda_calibrada,
                self.app.media_direita_calibrada,
            )
            if self.lado_detectado in ("Esquerda", "Direita") and not self.olhos_fechados:
                self.lado_estavel = self.lado_detectado

        self.historico_esq.append(self.ratio_esq)
        self.historico_dir.append(self.ratio_dir)

        if self.app.estado == EstadoApp.CALIB_COLETANDO:
            if self.pose_confiavel and not self.olhos_fechados and self.divergencia_ok:
                self.app.coletas_calibracao.append(self.ratio_valido)
            else:
                self.app.amostras_ignoradas += 1

        if self.app.estado == EstadoApp.PRANCHA_CALIB_COLETANDO:
            if self.pose_confiavel and not self.olhos_fechados and self.divergencia_ok:
                self.app.coletas_prancha.append((self.ratio_valido, self.ratio_y_valido))
            else:
                self.app.amostras_ignoradas += 1

        self._memorizar_rastreamento()

    def _detectar_simulado(self) -> None:
        self.rosto_detectado = self.sim_rosto
        self.pose_confiavel = self.sim_pose
        self.olhos_fechados = self.sim_olhos
        self.ratio_esq = min(max(self.sim_x, 0.0), 1.0)
        self.ratio_dir = self.ratio_esq
        self.ratio_valido = self.ratio_esq
        self.ratio_y_valido = min(max(self.sim_y, 0.0), 1.0)
        self.divergencia = 0.0
        self.divergencia_ok = True
        self.lado_detectado = None
        if self.olhos_fechados:
            self.bloco_prancha = self._bloco_prancha_estavel
        else:
            bruto = (
                board.classificar_unidade(
                    self.ratio_valido,
                    self.ratio_y_valido,
                    self.app.referencias_prancha,
                )
                if self.app.referencias_prancha
                else None
            )
            self.bloco_prancha = self._estabilizar_bloco(bruto, time.monotonic())

        det_cfg = self.cfg["deteccao"]
        if det_cfg["distancia_habilitada"] and self.rosto_detectado and self.pose_confiavel:
            self.distancia_rosto = max(0.0, float(self.sim_distancia))
            self.distancia_estado = ge.classificar_distancia(
                self.distancia_rosto,
                det_cfg["distancia_longe_abaixo"],
                det_cfg["distancia_perto_acima"],
            )
        else:
            self.distancia_rosto = 0.0
            self.distancia_estado = ge.DISTANCIA_INDEFINIDA

        if not self.rosto_detectado:
            return

        self.historico_esq.append(self.ratio_esq)
        self.historico_dir.append(self.ratio_dir)
        if self.pose_confiavel:
            self.lado_detectado = ge.classificar_lado(
                self.ratio_valido,
                self.app.media_esquerda_calibrada,
                self.app.media_direita_calibrada,
            )
            if self.lado_detectado in ("Esquerda", "Direita") and not self.olhos_fechados:
                self.lado_estavel = self.lado_detectado
        if self.app.estado == EstadoApp.CALIB_COLETANDO:
            if self.pose_confiavel and not self.olhos_fechados and self.divergencia_ok:
                self.app.coletas_calibracao.append(self.ratio_valido)
            else:
                self.app.amostras_ignoradas += 1
        if self.app.estado == EstadoApp.PRANCHA_CALIB_COLETANDO:
            if self.pose_confiavel and not self.olhos_fechados and self.divergencia_ok:
                self.app.coletas_prancha.append((self.ratio_valido, self.ratio_y_valido))
            else:
                self.app.amostras_ignoradas += 1

    # -----------------------------------------------------------------
    # Atualização de seleção e calibração
    # -----------------------------------------------------------------
    def _memorizar_rastreamento(self) -> None:
        """
        Guarda o último quadro confiável para a retenção de exibição.

        Só entra aqui com rosto e pose válidos. O ponto do olhar só é
        atualizado sem piscada e sem divergência -- assim a retenção não
        "congela" a posição errada de uma piscada.
        """
        if not (self.rosto_detectado and self.pose_confiavel):
            return
        self._rosto_visto_em = time.monotonic()
        self._pose_exibicao = True
        self._distancia_estado_exibicao = self.distancia_estado
        self._distancia_rosto_exibicao = self.distancia_rosto
        if not self.olhos_fechados and self.divergencia_ok:
            self._gaze_exibicao = (self.ratio_valido, self.ratio_y_valido)

    def _atualizar_aviso_sem_rosto(self, agora: float, em_deteccao: bool) -> None:
        """
        Histerese por TEMPO do aviso "reposicione o rosto".

        Antes a contagem era em frames, então o mesmo valor esperava 2 s a
        30 fps e 4 s a 15 fps. Agora usa ``deteccao.sem_rosto_ms`` e o
        relógio monotônico. O contador também é zerado ao sair das telas
        de detecção -- entrar na prancha sem rosto não dispara o aviso na
        hora.
        """
        if not em_deteccao:
            self._sem_rosto_desde = None
            self.aviso_sem_rosto = False
            return

        if self.rosto_detectado:
            self._sem_rosto_desde = None
            self.aviso_sem_rosto = False
            return

        # Sem frames chegando, o problema é a câmera (tratado por
        # semSinal), não a posição do rosto. O relógio é reiniciado, mas o
        # aviso atual é mantido para não piscar numa perda isolada de frame.
        if not self._frame_recebido_agora:
            self._sem_rosto_desde = None
            return

        if self._sem_rosto_desde is None:
            self._sem_rosto_desde = agora
            return

        limite_s = self.cfg["deteccao"]["sem_rosto_ms"] / 1000.0
        if agora - self._sem_rosto_desde >= limite_s:
            self.aviso_sem_rosto = True

    def _atualizar_aviso_cabeca(self, agora: float) -> None:
        """Mantém o aviso de cabeça estável, sem piscar a cada frame."""
        estado = self.app.estado
        ativo = (
            self.rosto_detectado
            and not self.pose_confiavel
            and estado in ESTADOS_AVISO_CABECA
        )
        (
            self.aviso_cabeca,
            self._cabeca_ruim_desde,
            self._cabeca_boa_desde,
        ) = histerese_aviso_cabeca(
            self.aviso_cabeca,
            self._cabeca_ruim_desde,
            self._cabeca_boa_desde,
            ativo,
            agora,
        )

    def _atualizar_aviso_distancia(self, agora: float) -> None:
        """
        Histerese do indicador de distância.

        É só informativo: não mexe em seleção, dwell nem calibração. O
        aviso aparece quando o rosto fica fora da faixa configurada por
        tempo suficiente e some após um período contínuo dentro dela.
        """
        det_cfg = self.cfg["deteccao"]
        ativo = bool(
            det_cfg["distancia_habilitada"]
            and self.rosto_detectado
            and self.pose_confiavel
            and self.distancia_estado
            in (ge.DISTANCIA_LONGE, ge.DISTANCIA_PERTO)
        )
        (
            self.distancia_aviso,
            self._distancia_ruim_desde,
            self._distancia_boa_desde,
        ) = histerese_aviso_distancia(
            self.distancia_aviso,
            self._distancia_ruim_desde,
            self._distancia_boa_desde,
            ativo,
            agora,
            det_cfg["distancia_entrada_ms"] / 1000.0,
            det_cfg["distancia_saida_ms"] / 1000.0,
        )

    def _estabilizar_bloco(self, bruto: str | None, agora: float) -> str | None:
        """
        Troca de cartão só depois que o novo candidato se mantém estável.

        ``bruto`` é o quadrante do quadro atual (pode ser ``None`` na zona
        morta). O valor devolvido é o cartão que o motor deve considerar
        focado agora. A histerese evita piscar entre dois cartões quando o
        olhar cruza a fronteira ou treme por um quadro.
        """
        if bruto == self._bloco_prancha_estavel:
            self._candidato_prancha = None
            self._candidato_prancha_desde = None
            return bruto

        if bruto != self._candidato_prancha or self._candidato_prancha_desde is None:
            self._candidato_prancha = bruto
            self._candidato_prancha_desde = agora
            return self._bloco_prancha_estavel

        decorrido_ms = (agora - self._candidato_prancha_desde) * 1000.0
        if decorrido_ms >= HISTERESE_PRANCHA_MS:
            self._bloco_prancha_estavel = bruto
            self._candidato_prancha = None
            self._candidato_prancha_desde = None
            return bruto
        return self._bloco_prancha_estavel

    def _atualizar_selecao(self, agora: float) -> None:
        self.decisao = DecisaoSelecao()
        if self.app.estado not in (EstadoApp.ATIVO, EstadoApp.PRANCHA_ATIVO):
            self._bloco_prancha_estavel = None
            self._candidato_prancha = None
            self._candidato_prancha_desde = None
            return

        opcao_atual = None
        if self.olhos_fechados:
            # A íris se mexe durante a piscada; manter o último alvo é o
            # que permite a piscada CONFIRMAR em vez de cancelar o foco.
            if self.app.estado == EstadoApp.ATIVO:
                opcao_atual = {"Esquerda": "SIM", "Direita": "NAO"}.get(
                    self.lado_estavel
                )
            else:
                opcao_atual = self._bloco_prancha_estavel
        elif self.rosto_detectado and self.pose_confiavel and self.divergencia_ok:
            if self.app.estado == EstadoApp.ATIVO:
                opcao_atual = {"Esquerda": "SIM", "Direita": "NAO"}.get(self.lado_detectado)
            else:
                # O cartão já vem estável de _detectar (com histerese).
                opcao_atual = self.bloco_prancha

        self.decisao = self.controlador.atualizar(opcao_atual, self.olhos_fechados, agora)
        self.app.opcao_focada = self.decisao.opcao_focada

        if self.decisao.opcao_confirmada and self.app.opcao_confirmada is None:
            self.app.opcao_confirmada = self.decisao.opcao_confirmada
            self.app.tempo_selecionado = agora
            logger.info(
                "Seleção confirmada: %s (método=%s)",
                self.app.opcao_confirmada,
                self.decisao.metodo,
            )
            self.feedback.confirmar()

        if self.controlador.deve_limpar_confirmacao(agora) and not self.olhos_fechados:
            self.controlador.reset()
            self.app.resetar_selecao()

    def _finalizar_calibracao_prancha(self, agora: float) -> None:
        if self.app.estado != EstadoApp.PRANCHA_CALIB_COLETANDO:
            return
        if not self.app.tempo_inicio_coleta_prancha:
            return
        decorrido = max(0.0, agora - self.app.tempo_inicio_coleta_prancha)
        if decorrido < self.calib_cfg["duracao_ms"] / 1000.0:
            return
        if len(self.app.coletas_prancha) < self.calib_cfg["min_amostras"]:
            return

        bloco_id = self.app.bloco_calib_atual()
        xs = [p[0] for p in self.app.coletas_prancha]
        ys = [p[1] for p in self.app.coletas_prancha]
        self.app.referencias_prancha[bloco_id] = (
            float(np.median(xs)),
            float(np.median(ys)),
        )
        logger.info(
            "Prancha: bloco '%s' calibrado (x=%.3f, y=%.3f, %d amostras).",
            bloco_id,
            self.app.referencias_prancha[bloco_id][0],
            self.app.referencias_prancha[bloco_id][1],
            len(self.app.coletas_prancha),
        )

        self.app.coletas_prancha = []
        self.app.amostras_ignoradas = 0
        self.app.tempo_inicio_coleta_prancha = 0.0
        self._reiniciar_filtros()
        self.app.indice_bloco_calib += 1

        if self.app.indice_bloco_calib < len(board.BLOCOS):
            self.app.transicionar(EstadoApp.PRANCHA_CALIB_PREPARAR)
            return

        distancia = board.distancia_minima_entre_pontos(self.app.referencias_prancha)
        self._recentralizacao_anterior = None
        if distancia < self.distancia_minima_prancha:
            self.app.prancha_calibrada = False
            self.app.prancha_fraca = True
            logger.warning("Prancha fraca (separação mínima %.3f).", distancia)
            self.feedback.erro()
        else:
            try:
                self.prancha_gerenciador.salvar(
                    self.app.perfil_ativo or "padrao",
                    self.app.referencias_prancha,
                )
                self.app.prancha_calibrada = True
                self.app.prancha_fraca = False
                self._perfis_cache = None
                self.feedback.confirmar()
            except (ValueError, OSError) as e:
                self.app.prancha_calibrada = False
                self.app.prancha_fraca = True
                logger.error("Falha ao salvar a prancha: %s", e)
                self.feedback.erro()
        self.app.transicionar(EstadoApp.PRANCHA_CALIB_CONCLUIDA)

    def _finalizar_calibracao_sim_nao(self, agora: float) -> None:
        if self.app.estado != EstadoApp.CALIB_COLETANDO:
            return
        if not self.app.tempo_inicio_coleta:
            return
        decorrido = max(0.0, agora - self.app.tempo_inicio_coleta)
        if decorrido < self.calib_cfg["duracao_ms"] / 1000.0:
            return
        if len(self.app.coletas_calibracao) < self.calib_cfg["min_amostras"]:
            return

        media = float(np.median(self.app.coletas_calibracao))
        if self.app.calib_fase == "ESQUERDA":
            self.app.media_esquerda_calibrada = media
            self.app.calib_fase = "DIREITA"
            self.app.coletas_calibracao = []
            self.app.amostras_ignoradas = 0
            self.app.tempo_inicio_coleta = 0.0
            self._reiniciar_filtros()
            self.app.transicionar(EstadoApp.CALIB_PREPARAR)
            logger.info("Calibração SIM concluída: %.3f", media)
            return

        self.app.media_direita_calibrada = media
        self.app.coletas_calibracao = []
        self.app.amostras_ignoradas = 0
        self.app.tempo_inicio_coleta = 0.0
        diferenca = abs(
            self.app.media_direita_calibrada - self.app.media_esquerda_calibrada
        )
        logger.info(
            "Calibrado! SIM: %.3f | NÃO: %.3f | separação: %.3f",
            self.app.media_esquerda_calibrada,
            self.app.media_direita_calibrada,
            diferenca,
        )
        if diferenca < self.diferenca_minima:
            self.app.calibracao_ja_feita = False
            self.app.calibracao_fraca = True
            logger.warning("Calibração fraca (separação %.3f).", diferenca)
            self.feedback.erro()
        else:
            try:
                self.calibrador.salvar(
                    self.app.perfil_ativo or "padrao",
                    self.app.media_esquerda_calibrada,
                    self.app.media_direita_calibrada,
                )
                self.app.calibracao_ja_feita = True
                self.app.calibracao_fraca = False
                self._perfis_cache = None
                self.feedback.confirmar()
            except (ValueError, OSError) as e:
                self.app.calibracao_ja_feita = False
                self.app.calibracao_fraca = True
                logger.error("Falha ao salvar a calibração: %s", e)
                self.feedback.erro()
        self.app.transicionar(EstadoApp.CALIB_CONCLUIDA)

    # -----------------------------------------------------------------
    # Snapshot
    # -----------------------------------------------------------------
    @staticmethod
    def _limitar(valor: float) -> float:
        return round(float(min(max(valor, 0.0), 1.0)), 4)

    def _progresso(self, inicio: float, amostras: int, agora: float, minimo: int) -> float:
        if not inicio:
            return 0.0
        decorrido = max(0.0, agora - inicio)
        progresso_tempo = min(decorrido / (self.calib_cfg["duracao_ms"] / 1000.0), 1.0)
        progresso_amostras = min(amostras / max(1, minimo), 1.0)
        return round(min(progresso_tempo, progresso_amostras), 3)

    def _snapshot(self, agora: float) -> dict:
        estado = self.app.estado
        sem_sinal = not self.camera_pronta()

        foco = None
        progresso = 0.0
        if estado in (EstadoApp.ATIVO, EstadoApp.PRANCHA_ATIVO):
            foco = self.decisao.opcao_focada or self.app.opcao_focada
            progresso = round(self.decisao.progresso, 3)

        distancia_prancha = (
            board.distancia_minima_entre_pontos(self.app.referencias_prancha)
            if self.app.referencias_prancha
            else 0.0
        )
        calib_valida = self.app.calibracao_valida(self.diferenca_minima)
        prancha_valida = self.app.prancha_valida(self.distancia_minima_prancha)

        calib_progresso = 0.0
        if estado == EstadoApp.CALIB_COLETANDO:
            calib_progresso = self._progresso(
                self.app.tempo_inicio_coleta,
                len(self.app.coletas_calibracao),
                agora,
                self.calib_cfg["min_amostras"],
            )
        elif estado == EstadoApp.CALIB_CONCLUIDA:
            calib_progresso = 1.0

        prancha_progresso = 0.0
        if estado == EstadoApp.PRANCHA_CALIB_COLETANDO:
            prancha_progresso = self._progresso(
                self.app.tempo_inicio_coleta_prancha,
                len(self.app.coletas_prancha),
                agora,
                self.calib_cfg["min_amostras"],
            )
        elif estado == EstadoApp.PRANCHA_CALIB_CONCLUIDA:
            prancha_progresso = 1.0

        det_cfg = self.cfg["deteccao"]
        # Retenção de exibição: quando o detector perde o rosto agora, mas o
        # último quadro confiável é recente, a interface repete o ponto e o
        # status anteriores em vez de piscar. A seleção NÃO usa estes
        # valores -- ela continua lendo self.rosto_detectado.
        segurando = bool(
            not self.simulador
            and not self.rosto_detectado
            and self._rosto_visto_em is not None
            and (agora - self._rosto_visto_em) * 1000.0 <= ROSTO_GRACE_MS
        )
        rosto_ok = bool(self.rosto_detectado or segurando)
        pose_ok = bool(
            self.pose_confiavel
            if self.rosto_detectado
            else (self._pose_exibicao if segurando else True)
        )
        if segurando:
            gaze_x, gaze_y = self._gaze_exibicao
            distancia_rosto = self._distancia_rosto_exibicao
            distancia_estado = self._distancia_estado_exibicao
        else:
            gaze_x, gaze_y = self.ratio_valido, self.ratio_y_valido
            distancia_rosto = self.distancia_rosto
            distancia_estado = self.distancia_estado

        # Só anuncia "olhos fechados" quando não é uma piscada curta.
        olhos_fechados = bool(
            self.olhos_fechados
            and self._olhos_fechados_desde is not None
            and (agora - self._olhos_fechados_desde) * 1000.0
            >= OLHOS_FECHADOS_EXIBICAO_MS
        )

        return {
            "tipo": "snapshot",
            "versao": VERSAO,
            "tela": estado.name,
            "perfil": self.app.perfil_ativo,
            "perfilAtivo": self.app.perfil_ativo,
            "perfis": self._perfis_disponiveis(),
            "nomeDigitado": self.app.nome_digitado,
            "cameraOk": not sem_sinal,
            "backend": "simulado" if self.simulador else self.backend_camera,
            "semSinal": sem_sinal,
            "segundosSemFrame": self.segundos_sem_frame(),
            "rostoOk": rosto_ok,
            "poseOk": pose_ok,
            "olhosFechados": olhos_fechados,
            "avisoSemRosto": bool(self.aviso_sem_rosto),
            "avisoCabeca": bool(
                self.aviso_cabeca and estado in ESTADOS_AVISO_CABECA
            ),
            "distanciaRosto": round(float(distancia_rosto), 4),
            "distanciaEstado": distancia_estado,
            # É só informativo: expõe o estado da histerese também no Modo
            # Cuidador, onde o painel do olhar mostra o indicador.
            "distanciaAviso": bool(self.distancia_aviso),
            "podeDesfazerRecentralizacao": bool(self._recentralizacao_anterior),
            "gaze": {
                "x": self._limitar(gaze_x),
                "y": self._limitar(gaze_y),
                "esq": self._limitar(self.ratio_esq),
                "dir": self._limitar(self.ratio_dir),
                "valido": bool(rosto_ok and pose_ok),
                "divergencia": round(float(self.divergencia), 4),
                "divergenciaOk": bool(self.divergencia_ok),
                # Cartão estável (com histerese) usado pela seleção e pelo
                # Mapa do Cuidador. None = zona morta ou sem calibração.
                "bloco": self.bloco_prancha,
            },
            "foco": foco,
            "progresso": progresso,
            "confirmado": self.app.opcao_confirmada,
            "aviso": self.app.aviso if self.app.aviso_ativo(agora) else None,
            "pranchaCalibrada": prancha_valida,
            "pranchaFraca": bool(self.app.prancha_fraca),
            "calibracaoSimNao": calib_valida,
            "calibracaoFraca": bool(self.app.calibracao_fraca),
            "dwellMs": int(det_cfg["dwell_ms"]),
            "piscadaHabilitada": bool(det_cfg["piscada"]["habilitada"]),
            "simulacao": bool(self.simulador),
            "calibracao": {
                "fase": self.app.calib_fase,
                "alvo": "SIM" if self.app.calib_fase == "ESQUERDA" else "NAO",
                "coletando": estado == EstadoApp.CALIB_COLETANDO,
                "progresso": calib_progresso,
                "amostras": len(self.app.coletas_calibracao),
                "minimo": int(self.calib_cfg["min_amostras"]),
                "descartadas": int(self.app.amostras_ignoradas),
                "mediaEsq": round(float(self.app.media_esquerda_calibrada), 4),
                "mediaDir": round(float(self.app.media_direita_calibrada), 4),
                "diferenca": round(
                    abs(
                        self.app.media_direita_calibrada
                        - self.app.media_esquerda_calibrada
                    ),
                    4,
                ),
                "sucesso": bool(calib_valida),
            },
            "pranchaCalib": {
                "blocoId": self.app.bloco_calib_atual()
                if estado
                in (
                    EstadoApp.PRANCHA_CALIB_PREPARAR,
                    EstadoApp.PRANCHA_CALIB_COLETANDO,
                )
                else None,
                "indice": int(self.app.indice_bloco_calib),
                "total": len(board.BLOCOS),
                "coletando": estado == EstadoApp.PRANCHA_CALIB_COLETANDO,
                "aguardando": estado == EstadoApp.PRANCHA_CALIB_PREPARAR,
                "progresso": prancha_progresso,
                "amostras": len(self.app.coletas_prancha),
                "minimo": int(self.calib_cfg["min_amostras"]),
                "descartadas": int(self.app.amostras_ignoradas),
                "distancia": round(float(distancia_prancha), 4),
                "sucesso": bool(prancha_valida),
                "referencias": {
                    bloco_id: [round(float(p[0]), 4), round(float(p[1]), 4)]
                    for bloco_id, p in self.app.referencias_prancha.items()
                },
            },
            "historico": {
                "esq": [round(float(v), 4) for v in list(self.historico_esq)[-80:]],
                "dir": [round(float(v), 4) for v in list(self.historico_dir)[-80:]],
            },
            "config": self._config_resumo(),
        }

    def _config_resumo(self) -> dict:
        if self._config_resumo_cache is not None:
            return self._config_resumo_cache
        det = self.cfg["deteccao"]
        piscada = det["piscada"]
        calib = self.cfg["calibracao"]
        cam = self.cfg["camera"]
        perfis = self.cfg["perfis"]
        janela = self.cfg["janela"]
        resumo = {
            "deteccao": {
                "dwellMs": int(det["dwell_ms"]),
                "toleranciaPerdaMs": int(det["tolerancia_perda_ms"]),
                "exibicaoConfirmacaoMs": int(det["exibicao_confirmacao_ms"]),
                "alphaEma": float(det["alpha_ema"]),
                "tamanhoHistoricoGrafico": int(det["tamanho_historico_grafico"]),
                "semRostoMs": int(det["sem_rosto_ms"]),
                "divergenciaMax": float(det["divergencia_max"]),
                "compensarYaw": bool(det["compensar_yaw"]),
                "yawSensibilidade": float(det["yaw_sensibilidade"]),
                "confiancaMinima": float(det["confianca_minima"]),
                "distanciaHabilitada": bool(det["distancia_habilitada"]),
                "distanciaLongeAbaixo": float(det["distancia_longe_abaixo"]),
                "distanciaPertoAcima": float(det["distancia_perto_acima"]),
                "distanciaEntradaMs": int(det["distancia_entrada_ms"]),
                "distanciaSaidaMs": int(det["distancia_saida_ms"]),
                "piscadaHabilitada": bool(piscada["habilitada"]),
                "limiarEar": float(piscada["limiar_ear"]),
                "piscadaMs": int(piscada["piscada_ms"]),
                "focoMinimoMs": int(piscada["foco_minimo_ms"]),
            },
            "calibracao": {
                "duracaoMs": int(calib["duracao_ms"]),
                "minAmostras": int(calib["min_amostras"]),
                "maxYawGraus": float(calib["max_yaw_graus"]),
                "maxPitchGraus": float(calib["max_pitch_graus"]),
                "maxRollGraus": float(calib["max_roll_graus"]),
                "diferencaMinima": float(calib["diferenca_minima"]),
            },
            "prancha": {
                "distanciaMinimaBoa": float(self.prancha_cfg["distancia_minima_boa"]),
                "raioMax": float(self.prancha_cfg["raio_max"]),
            },
            "camera": {
                "indice": int(cam["indice"]),
                "largura": int(cam["largura"]),
                "altura": int(cam["altura"]),
                "fps": int(cam["fps"]),
                "backend": str(cam["backend"]),
                "timeoutInicialMs": int(cam["timeout_inicial_ms"]),
            },
            "perfis": {"validadeDias": int(perfis["validade_dias"])},
            "feedback": {"som": bool(self.cfg["feedback"]["som"])},
            "aparencia": {"tema": str(self.cfg["aparencia"]["tema"])},
            "janela": {
                "resolucao": str(janela["resolucao"]),
                "fullscreen": bool(janela["fullscreen"]),
            },
            "configPath": str(self.config_path) if self.config_path else "",
        }
        self._config_resumo_cache = resumo
        return resumo

    # -----------------------------------------------------------------
    # Loop principal
    # -----------------------------------------------------------------
    def executar(self) -> int:
        ultimo_envio = 0.0
        try:
            while self.rodando:
                agora = time.monotonic()

                for comando in self.leitor.drenar():
                    self.aplicar_comando(comando, agora)
                if not self.rodando:
                    break

                frame_proc = self._ler_frame()

                estados_com_deteccao = ESTADOS_COM_DETECCAO
                em_deteccao = self.app.estado in estados_com_deteccao
                if em_deteccao:
                    if self.simulador:
                        self._detectar_simulado()
                    elif frame_proc is not None and self.detector is not None:
                        self._detectar(frame_proc)
                    else:
                        self.rosto_detectado = False
                else:
                    self.rosto_detectado = False
                    self.olhos_fechados = False
                    self.bloco_prancha = None

                self._atualizar_aviso_sem_rosto(agora, em_deteccao)
                if self.olhos_fechados:
                    if self._olhos_fechados_desde is None:
                        self._olhos_fechados_desde = agora
                else:
                    self._olhos_fechados_desde = None
                self._atualizar_aviso_cabeca(agora)
                self._atualizar_aviso_distancia(agora)
                self._atualizar_selecao(agora)
                self._finalizar_calibracao_prancha(agora)
                self._finalizar_calibracao_sim_nao(agora)

                if agora - ultimo_envio >= (1.0 / 30.0):
                    ultimo_envio = agora
                    try:
                        emitir(self._snapshot(agora))
                    except Exception:
                        logger.exception("Falha ao montar o snapshot.")

                # Limita o loop a ~60 Hz. Sem isso, a simulação (e o modo
                # sem câmera) giraria a CPU e acumularia milhares de
                # amostras de calibração por segundo.
                duracao = time.monotonic() - agora
                intervalo = 1.0 / 60.0
                if duracao < intervalo:
                    time.sleep(intervalo - duracao)
        except KeyboardInterrupt:
            logger.info("Encerrando por Ctrl+C.")
        except Exception as e:
            logger.exception("Erro inesperado no motor.")
            emitir_erro(f"Ocorreu um erro inesperado:\n{type(e).__name__}: {e}")
            return 1
        finally:
            self.encerrar()
        return 0

    def encerrar(self) -> None:
        logger.info("Encerrando motor.")
        if self.camera is not None:
            try:
                self.camera.parar()
            except Exception:
                logger.exception("Falha ao encerrar a câmera.")
        if self.detector is not None:
            try:
                self.detector.close()
            except Exception:
                logger.exception("Falha ao encerrar o detector.")
        emitir({"tipo": "encerrado"})


def principal(argv: list[str] | None = None) -> int:
    # O protocolo é sempre UTF-8, independentemente da página de código do
    # Windows (o console padrão costuma usar cp1252).
    for fluxo in (sys.stdin, sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            fluxo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    parser = argparse.ArgumentParser(description="Ponte do Eye-Tracking Assistivo para a interface Tauri")
    parser.add_argument("--config", type=str, default=None, help="caminho do settings.yaml")
    parser.add_argument("--dados", type=str, default=None, help="pasta gravável (perfis e logs)")
    parser.add_argument("--simular", action="store_true", help="modo de demonstração sem câmera")
    args = parser.parse_args(argv)

    try:
        motor = Motor(args)
    except SystemExit:
        raise
    except Exception as e:
        logger.exception("Falha ao iniciar o motor.")
        emitir_erro(f"Não foi possível iniciar o motor:\n{type(e).__name__}: {e}")
        return 1
    return motor.executar()


if __name__ == "__main__":
    raise SystemExit(principal())
