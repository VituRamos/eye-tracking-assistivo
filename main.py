"""
Eye-Tracking Assistivo V2.1 -- ponto de entrada principal.

Este arquivo só ORQUESTRA os módulos abaixo; a lógica pesada vive em
cada um deles:

  config/loader.py        -> configuração externa (YAML)
  core/paths.py           -> caminhos em dev e no executável
  core/logging_config.py  -> logging estruturado
  core/model_loader.py    -> download/verificação do modelo MediaPipe
  core/camera_thread.py   -> captura de câmera em thread separada
  core/state_machine.py   -> estado da aplicação (Enum + AppState)
  core/gaze_engine.py     -> cálculo puro de gaze (ratio, EMA, EAR, pose)
  core/board.py           -> blocos da prancha e classificação 2D
  core/board_calibration.py -> persistência da calibração da prancha
  core/selection.py       -> decisão de seleção (dwell + piscada)
  core/calibration.py     -> persistência de calibração SIM/NÃO
  ui/design.py            -> tokens visuais, Lona Pillow, SVG e componentes
  ui/renderer_cv2.py      -> menu, perfis, SIM/NÃO e telas auxiliares
  ui/board_renderer.py    -> prancha de comunicação e calibração

Rode com: python main.py
Diagnóstico sem câmera: python main.py --check
Diagnóstico da webcam:  python main.py --check-camera
"""
from __future__ import annotations

import argparse
import logging
import queue
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from config.loader import carregar_config
from core import board, paths
from core import gaze_engine as ge
from core.board_calibration import GerenciadorPrancha, pontos_do_dados
from core.calibration import GerenciadorCalibracao
from core.camera_thread import (
    CameraIndisponivelError,
    CameraStream,
    diagnosticar_camera,
)
from core.erros import mostrar_erro_fatal
from core.feedback import FeedbackSonoro
from core.logging_config import configurar_logging
from core.model_loader import garantir_modelo_baixado
from core.selection import ControladorSelecao, DecisaoSelecao
from core.state_machine import AppState, EstadoApp
from ui import board_renderer as ui_prancha
from ui import renderer_cv2 as ui

VERSAO = "2.2.4"

# Captura e detecção continuam em 1280x720 (custo baixo no MediaPipe).
# A interface é desenhada nativamente em 1920x1080 e só então exibida.
LARGURA_PROJETO = 1280
ALTURA_PROJETO = 720
LARGURA_TELA = 1920
ALTURA_TELA = 1080

# Códigos de teclas especiais no formato devolvido pelo OpenCV no Windows
# (VK << 16). As letras G/O funcionam como alternativa em qualquer backend.
TECLA_F2 = 0x71 << 16
TECLA_F3 = 0x72 << 16

logger = logging.getLogger("eyetracking")


# =====================================================================
# Inicialização
# =====================================================================
def montar_detector(caminho_modelo: str):
    base_options = mp_python.BaseOptions(model_asset_path=caminho_modelo)
    opcoes = mp_vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,  # necessário p/ compensação de pose
    )
    return mp_vision.FaceLandmarker.create_from_options(opcoes)


def criar_controlador(cfg) -> ControladorSelecao:
    det = cfg["deteccao"]
    return ControladorSelecao(
        dwell_ms=det["dwell_ms"],
        tolerancia_perda_ms=det["tolerancia_perda_ms"],
        piscada_habilitada=det["piscada"]["habilitada"],
        piscada_ms=det["piscada"]["piscada_ms"],
        foco_minimo_ms=det["piscada"]["foco_minimo_ms"],
        exibicao_confirmacao_ms=det["exibicao_confirmacao_ms"],
    )


def configurar_janela(cfg, sem_fullscreen: bool) -> None:
    titulo = cfg["janela"]["titulo"]
    cv2.namedWindow(titulo, cv2.WINDOW_NORMAL)
    if cfg["janela"]["fullscreen"] and not sem_fullscreen:
        cv2.setWindowProperty(titulo, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


# =====================================================================
# Diagnóstico (--check) -- útil para validar o .exe sem webcam
# =====================================================================
def _salvar_diagnostico(nome_arquivo: str, linhas: list[str]) -> None:
    texto = "\n".join(linhas)
    print(texto)
    try:
        destino = paths.resolver_dados(nome_arquivo)
        destino.write_text(texto + "\n", encoding="utf-8")
        print(f"\nDiagnóstico salvo em: {destino}")
    except OSError as e:
        print(f"Não foi possível salvar o diagnóstico: {e}")


def executar_check_camera(cfg) -> int:
    """Testa cada backend de captura e explica exatamente onde falhou."""
    cam_cfg = cfg["camera"]
    linhas = [
        f"Diagnóstico de câmera (índice {cam_cfg['indice']}, "
        f"{cam_cfg['largura']}x{cam_cfg['altura']} @ {cam_cfg['fps']} fps)",
        f"Backend configurado: {cam_cfg['backend']}",
        f"OpenCV: {cv2.__version__}",
        "",
    ]
    try:
        resultados = diagnosticar_camera(
            indice=cam_cfg["indice"],
            largura=cam_cfg["largura"],
            altura=cam_cfg["altura"],
            fps=cam_cfg["fps"],
            backend=cam_cfg["backend"],
        )
    except Exception as e:  # noqa: BLE001 - diagnóstico deve reportar qualquer falha
        linhas.append(f"ERRO: {type(e).__name__}: {e}")
        _salvar_diagnostico("diagnostico_camera.txt", linhas)
        return 1

    funcionou = False
    for r in resultados:
        if r.recebeu_frame:
            funcionou = True
            linhas.append(f"  {r.backend:5s}  OK      ({r.segundos:.2f}s) entregou frames")
        elif r.abriu:
            linhas.append(
                f"  {r.backend:5s}  FALHOU  ({r.segundos:.2f}s) {r.erro or 'sem frames'}"
            )
        else:
            linhas.append(f"  {r.backend:5s}  FALHOU  ({r.segundos:.2f}s) {r.erro or 'não abriu'}")

    linhas.append("")
    if funcionou:
        linhas.append("RESULTADO: a câmera funciona. O aplicativo usará o backend marcado como OK.")
    else:
        linhas.append("RESULTADO: nenhum backend entregou imagens.")
        linhas.append("")
        linhas.append("Verifique, nesta ordem:")
        linhas.append("  1. Feche Teams/Zoom/Navegador/app Câmera que possam estar usando a webcam.")
        linhas.append("  2. Desconecte e reconecte a webcam (ou troque a porta USB).")
        linhas.append("  3. Configurações > Privacidade e segurança > Câmera: acesso permitido.")
        linhas.append("  4. Abra o app Câmera do Windows e confirme que a imagem aparece.")
        linhas.append("  5. Se funcionar em outro programa mas não aqui, tente "
                      "camera.backend: \"dshow\" no settings.yaml.")

    _salvar_diagnostico("diagnostico_camera.txt", linhas)
    return 0 if funcionou else 1


def executar_check(cfg, caminho_modelo: Path) -> int:
    linhas: list[str] = []
    ok = True
    try:
        import platform

        linhas.append(f"Eye-Tracking Assistivo v{VERSAO}")
        linhas.append(f"Python: {platform.python_version()} ({platform.platform()})")
        linhas.append(f"Congelado (PyInstaller): {paths.congelado()}")
        linhas.append(f"Pasta de recursos: {paths.pasta_recurso()}")
        linhas.append(f"Pasta de dados: {paths.pasta_dados()}")
        linhas.append(f"OpenCV: {cv2.__version__}")
        linhas.append(f"MediaPipe: {mp.__version__}")
        linhas.append(f"NumPy: {np.__version__}")
        linhas.append(f"Modelo: {caminho_modelo}")
        linhas.append(f"Modelo existe: {caminho_modelo.exists()}")
        if caminho_modelo.exists():
            linhas.append(f"Tamanho do modelo: {caminho_modelo.stat().st_size} bytes")
        else:
            ok = False
            linhas.append("ERRO: modelo não encontrado")

        linhas.append(f"Config carregada: {cfg}")
        detector = montar_detector(str(caminho_modelo))
        detector.close()
        linhas.append("Detector MediaPipe: OK")
    except Exception as e:  # noqa: BLE001 - diagnóstico deve reportar qualquer falha
        ok = False
        linhas.append(f"ERRO: {type(e).__name__}: {e}")

    texto = "\n".join(linhas)
    print(texto)
    try:
        destino = paths.resolver_dados("diagnostico.txt")
        destino.write_text(texto + "\n", encoding="utf-8")
        print(f"\nDiagnóstico salvo em: {destino}")
    except OSError as e:
        print(f"Não foi possível salvar o diagnóstico: {e}")
    return 0 if ok else 1

# =====================================================================
# Loop principal
# =====================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eye-Tracking Assistivo v2.1")
    parser.add_argument("--config", type=str, default=None, help="caminho alternativo do settings.yaml")
    parser.add_argument("--sem-fullscreen", action="store_true", help="abre em janela")
    parser.add_argument("--check", action="store_true", help="valida instalação/modelo e encerra")
    parser.add_argument(
        "--check-camera",
        action="store_true",
        help="testa a webcam em cada backend e encerra (sem abrir a interface)",
    )
    args = parser.parse_args(argv)

    cfg = carregar_config(args.config)
    logger_raiz = configurar_logging(
        pasta=paths.resolver_dados(cfg["logs"]["pasta"]), nivel=cfg["logs"]["nivel"]
    )

    det_cfg = cfg["deteccao"]
    cam_cfg = cfg["camera"]
    modelo_cfg = cfg["modelo"]
    janela_cfg = cfg["janela"]
    calib_cfg = cfg["calibracao"]
    prancha_cfg = cfg["prancha"]
    piscada_cfg = det_cfg["piscada"]
    diferenca_minima = calib_cfg["diferenca_minima"]
    distancia_minima_prancha = prancha_cfg["distancia_minima_boa"]
    raio_max_prancha = prancha_cfg["raio_max"]

    caminho_modelo = paths.resolver_modelo(modelo_cfg["caminho"])
    try:
        caminho_modelo = garantir_modelo_baixado(
            caminho_modelo, modelo_cfg["url"], modelo_cfg.get("sha256_esperado", "")
        )
    except RuntimeError as e:
        mostrar_erro_fatal(str(e))
        return 1

    if args.check:
        return executar_check(cfg, caminho_modelo)

    if args.check_camera:
        return executar_check_camera(cfg)

    try:
        detector = montar_detector(str(caminho_modelo))
    except Exception as e:  # noqa: BLE001 - erro de modelo/driver deve ser mostrado ao usuário
        mostrar_erro_fatal(
            "Não foi possível carregar o modelo do MediaPipe.\n"
            f"Arquivo: {caminho_modelo}\nErro: {e}"
        )
        return 1

    try:
        camera = CameraStream(
            cam_cfg["indice"],
            cam_cfg["largura"],
            cam_cfg["altura"],
            cam_cfg["fps"],
            backend=cam_cfg["backend"],
            timeout_inicial_s=cam_cfg["timeout_inicial_ms"] / 1000.0,
            # Tolerante: se a webcam não abrir, a janela mostra a tela de
            # "sem sinal" com instruções e o app segue tentando reconectar.
            tolerante=True,
        )
    except CameraIndisponivelError as e:
        logger_raiz.error("Falha ao abrir a câmera: %s", e)
        mostrar_erro_fatal(str(e))
        detector.close()
        return 1
    if camera.backend_em_uso == "nenhum":
        logger_raiz.warning(
            "Iniciando sem imagens da câmera; use --check-camera para diagnosticar."
        )

    calibrador = GerenciadorCalibracao(pasta=paths.resolver_dados(cfg["perfis"]["pasta"]))
    prancha_gerenciador = GerenciadorPrancha(
        pasta=paths.resolver_dados(cfg["perfis"]["pasta"]),
        distancia_minima_boa=distancia_minima_prancha,
    )
    feedback = FeedbackSonoro(habilitado=cfg["feedback"]["som"])

    app = AppState()
    controlador = criar_controlador(cfg)
    suavizador_esq = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])
    suavizador_dir = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])
    suavizador_y = ge.SuavizadorEMA(alpha=det_cfg["alpha_ema"])

    historico_esq: deque[float] = deque(maxlen=det_cfg["tamanho_historico_grafico"])
    historico_dir: deque[float] = deque(maxlen=det_cfg["tamanho_historico_grafico"])
    largura_grafico, altura_grafico = 280, 160
    # O gráfico é desenhado em pixels reais; acompanha a tela nativa.
    largura_grafico = round(largura_grafico * LARGURA_TELA / LARGURA_PROJETO)
    altura_grafico = round(altura_grafico * ALTURA_TELA / ALTURA_PROJETO)

    # -----------------------------------------------------------------
    def camera_pronta() -> bool:
        """True quando a webcam está entregando imagens agora."""
        return (
            camera.backend_em_uso != "nenhum"
            and camera.segundos_sem_frame() <= 2.0
        )

    def reiniciar_filtros() -> None:
        suavizador_esq.reset()
        suavizador_dir.reset()
        suavizador_y.reset()
        historico_esq.clear()
        historico_dir.clear()

    def perfis_disponiveis() -> list[str]:
        """Perfis que têm calibração SIM/NÃO ou prancha salva."""
        return sorted(
            set(calibrador.listar_perfis()) | set(prancha_gerenciador.listar_perfis())
        )

    def aplicar_perfil(
        nome: str,
        dados_sim: dict | None,
        dados_prancha: dict | None,
    ) -> None:
        """Leva para o estado os dados de um perfil já carregado do disco."""
        app.perfil_ativo = nome

        if dados_sim is not None:
            app.media_esquerda_calibrada = float(dados_sim["media_esquerda"])
            app.media_direita_calibrada = float(dados_sim["media_direita"])
            app.calibracao_ja_feita = True
            diferenca = abs(
                app.media_direita_calibrada - app.media_esquerda_calibrada
            )
            app.calibracao_fraca = diferenca < diferenca_minima
            if calibrador.calibracao_esta_vencida(
                dados_sim, cfg["perfis"]["validade_dias"]
            ):
                logger_raiz.info("Calibração SIM/NAO de '%s' vencida.", nome)
        else:
            app.media_esquerda_calibrada = 0.35
            app.media_direita_calibrada = 0.65
            app.calibracao_ja_feita = False
            app.calibracao_fraca = False

        if dados_prancha is not None:
            app.referencias_prancha = pontos_do_dados(dados_prancha)
            app.prancha_fraca = dados_prancha["qualidade"] != "boa"
            app.prancha_calibrada = not app.prancha_fraca
            if prancha_gerenciador.calibrar_vencida(
                dados_prancha, cfg["perfis"]["validade_dias"]
            ):
                logger_raiz.info(
                    "Prancha de '%s' vencida -- considere recalibrar.", nome
                )
        else:
            app.referencias_prancha = {}
            app.prancha_calibrada = False
            app.prancha_fraca = False

    def entrar_na_prancha(agora: float) -> None:
        if not camera_pronta():
            app.avisar("Sem sinal da camera. Verifique a webcam.", agora)
            return
        if not app.prancha_valida(distancia_minima_prancha):
            app.avisar("Prancha sem calibracao. Pressione [C] para calibrar.", agora)
            return
        app.resetar_selecao()
        controlador.reset()
        reiniciar_filtros()
        app.transicionar(EstadoApp.PRANCHA_ATIVO)
        logger_raiz.info(
            "Prancha iniciada (perfil=%s).", app.perfil_ativo or "padrao"
        )

    def iniciar_calibracao_prancha(agora: float) -> None:
        if not camera_pronta():
            app.avisar("Sem sinal da camera. Verifique a webcam.", agora)
            return
        app.resetar_prancha()
        reiniciar_filtros()
        app.transicionar(EstadoApp.PRANCHA_CALIB_PREPARAR)
        logger_raiz.info(
            "Calibração da prancha iniciada (perfil=%s).",
            app.perfil_ativo or "padrao",
        )

    def entrar_no_modo_ativo(agora: float) -> None:
        if not camera_pronta():
            app.avisar("Sem sinal da camera. Verifique a webcam.", agora)
            return
        if not app.calibracao_valida(diferenca_minima):
            app.avisar("Calibracao ausente ou fraca. Pressione [C] para calibrar.", agora)
            return
        app.resetar_selecao()
        controlador.reset()
        reiniciar_filtros()
        app.transicionar(EstadoApp.ATIVO)
        logger_raiz.info("Modo ativo iniciado (perfil=%s).", app.perfil_ativo or "padrao")

    def iniciar_calibracao(agora: float) -> None:
        if not camera_pronta():
            app.avisar("Sem sinal da camera. Verifique a webcam.", agora)
            return
        app.resetar_calibracao()
        reiniciar_filtros()
        app.transicionar(EstadoApp.CALIB_PREPARAR)
        logger_raiz.info("Calibração iniciada (perfil=%s).", app.perfil_ativo or "padrao")

    configurar_janela(cfg, args.sem_fullscreen)

    # Abre já utilizável: se existir um perfil "padrao" no disco (o usado
    # quando nenhum perfil foi escolhido), carrega prancha e/ou SIM/NÃO.
    dados_sim_padrao = calibrador.carregar("padrao")
    dados_prancha_padrao = prancha_gerenciador.carregar("padrao")
    if dados_sim_padrao is not None or dados_prancha_padrao is not None:
        aplicar_perfil("padrao", dados_sim_padrao, dados_prancha_padrao)
        logger_raiz.info(
            "Perfil padrão carregado (SIM/NAO=%s, prancha=%s).",
            "ok" if app.calibracao_ja_feita else "ausente",
            "ok" if app.prancha_calibrada else "ausente",
        )

    logger_raiz.info("Aplicação iniciada. Estado inicial: %s", app.estado)

    largura_proc, altura_proc = LARGURA_PROJETO, ALTURA_PROJETO
    largura, altura = LARGURA_TELA, ALTURA_TELA
    escala_tela = largura / LARGURA_PROJETO
    metade_x = largura // 2
    pos_x = largura - largura_grafico - round(20 * escala_tela)
    pos_y = altura - altura_grafico - round(40 * escala_tela)
    timestamp_ms = 0
    ultimo_aviso_camera = time.monotonic()
    sem_rosto_desde: float | None = None
    modelo_sem_iris_avisado = False

    # Canvas nativo da interface. As telas sempre pintam o quadro inteiro;
    # ele é reaproveitado para não alocar 6 MB a cada iteração.
    frame = np.zeros((altura, largura, 3), dtype=np.uint8)

    try:
        while True:
            agora = time.monotonic()

            try:
                quadro = camera.ler(timeout=0.2)
            except queue.Empty:
                quadro = None

            frame_recebido = quadro is not None
            if not frame_recebido:
                frame_proc = np.zeros((altura_proc, largura_proc, 3), dtype=np.uint8)
                # Log a cada 10s, não a cada iteração (evita poluir o log).
                if agora - ultimo_aviso_camera >= 10.0:
                    ultimo_aviso_camera = agora
                    logger_raiz.warning(
                        "Sem imagens da câmera há %.1fs.", camera.segundos_sem_frame()
                    )
            else:
                ultimo_aviso_camera = agora
                frame_proc = ui.preparar_frame(
                    cv2.flip(quadro, 1), largura_proc, altura_proc
                )

            ratio_esq, ratio_dir = 0.5, 0.5
            ratio_valido = (ratio_esq + ratio_dir) / 2
            ratio_y_valido = 0.5
            lado_detectado: str | None = None
            rosto_detectado = False
            pose_confiavel = True
            olhos_fechados = False
            avisar_sem_rosto = False

            rodar_deteccao = app.estado in (
                EstadoApp.CALIB_COLETANDO,
                EstadoApp.ATIVO,
                EstadoApp.PRANCHA_CALIB_COLETANDO,
                EstadoApp.PRANCHA_ATIVO,
            )

            # ---------------------------------------------------------
            # Detecção e cálculo de gaze
            # ---------------------------------------------------------
            if rodar_deteccao:
                rgb = cv2.cvtColor(frame_proc, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                # Milissegundos reais e estritamente crescentes: o MediaPipe
                # usa o timestamp para o rastreamento no modo VIDEO. O +1
                # por frame antigo fazia o grafo achar que rodava a 1000 fps.
                agora_ms = int(time.monotonic() * 1000)
                if agora_ms <= timestamp_ms:
                    agora_ms = timestamp_ms + 1
                timestamp_ms = agora_ms
                resultado = detector.detect_for_video(mp_image, timestamp_ms)

                landmarks = resultado.face_landmarks[0] if resultado.face_landmarks else None
                if landmarks is not None and len(landmarks) < 478:
                    if not modelo_sem_iris_avisado:
                        logger_raiz.error(
                            "Modelo facial com %d pontos (esperado >= 478, com íris). "
                            "Atualize models/face_landmarker.task.",
                            len(landmarks),
                        )
                        modelo_sem_iris_avisado = True
                    landmarks = None

                if landmarks is not None:
                    rosto_detectado = True

                    ratio_esq_bruto = ge.calcular_ratio_iris_x(
                        landmarks, ge.OLHO_ESQUERDO_CANTOS, ge.IRIS_ESQUERDA,
                        largura_proc, altura_proc)
                    ratio_dir_bruto = ge.calcular_ratio_iris_x(
                        landmarks, ge.OLHO_DIREITO_CANTOS, ge.IRIS_DIREITA,
                        largura_proc, altura_proc)

                    # Pose de cabeça: yaw, pitch e roll. A compensação do
                    # ratio é opcional (desligada por padrão) para não somar
                    # uma correção à normalização que o ratio já faz.
                    if resultado.facial_transformation_matrixes:
                        yaw, pitch, roll = ge.extrair_angulos_da_matriz(
                            resultado.facial_transformation_matrixes[0]
                        )
                        pose_confiavel = ge.pose_dentro_dos_limites(
                            yaw, pitch, roll,
                            calib_cfg["max_yaw_graus"],
                            calib_cfg["max_pitch_graus"],
                            calib_cfg["max_roll_graus"],
                        )
                        if det_cfg["compensar_yaw"]:
                            ratio_esq_bruto = ge.compensar_ratio_por_yaw(
                                ratio_esq_bruto, yaw, det_cfg["yaw_sensibilidade"]
                            )
                            ratio_dir_bruto = ge.compensar_ratio_por_yaw(
                                ratio_dir_bruto, yaw, det_cfg["yaw_sensibilidade"]
                            )

                    ratio_esq = suavizador_esq.atualizar(ratio_esq_bruto)
                    ratio_dir = suavizador_dir.atualizar(ratio_dir_bruto)
                    ratio_valido = (ratio_esq + ratio_dir) / 2

                    ratio_y_bruto = (
                        ge.calcular_ratio_iris_y(
                            landmarks, ge.OLHO_ESQUERDO_VERTICAL, ge.IRIS_ESQUERDA,
                            largura_proc, altura_proc)
                        + ge.calcular_ratio_iris_y(
                            landmarks, ge.OLHO_DIREITO_VERTICAL, ge.IRIS_DIREITA,
                            largura_proc, altura_proc)
                    ) / 2
                    ratio_y_valido = suavizador_y.atualizar(ratio_y_bruto)

                    # EAR: usado para piscada E para descartar amostras de
                    # calibração com os olhos fechados (íris instável).
                    ear_esq = ge.calcular_ear(
                        landmarks, ge.OLHO_ESQUERDO_VERTICAL, ge.OLHO_ESQUERDO_CANTOS,
                        largura_proc, altura_proc)
                    ear_dir = ge.calcular_ear(
                        landmarks, ge.OLHO_DIREITO_VERTICAL, ge.OLHO_DIREITO_CANTOS,
                        largura_proc, altura_proc)
                    ear_medio = (ear_esq + ear_dir) / 2
                    olhos_fechados = ge.olho_fechado(ear_medio, piscada_cfg["limiar_ear"])

                    if pose_confiavel:
                        # Classificação sobre a MESMA grandeza que foi
                        # calibrada: a média dos dois olhos.
                        lado_detectado = ge.classificar_lado(
                            ratio_valido,
                            app.media_esquerda_calibrada,
                            app.media_direita_calibrada,
                        )

                    historico_esq.append(ratio_esq)
                    historico_dir.append(ratio_dir)

                    if app.estado == EstadoApp.CALIB_COLETANDO:
                        if pose_confiavel and not olhos_fechados:
                            app.coletas_calibracao.append(ratio_valido)
                        else:
                            app.amostras_ignoradas += 1

                    if app.estado == EstadoApp.PRANCHA_CALIB_COLETANDO:
                        if pose_confiavel and not olhos_fechados:
                            app.coletas_prancha.append((ratio_valido, ratio_y_valido))
                        else:
                            app.amostras_ignoradas += 1

                if rosto_detectado or not frame_recebido:
                    sem_rosto_desde = None
                elif sem_rosto_desde is None:
                    sem_rosto_desde = agora
                elif (agora - sem_rosto_desde) * 1000 >= det_cfg["sem_rosto_ms"]:
                    avisar_sem_rosto = True
            else:
                # Fora das telas de detecção o relógio do aviso é zerado,
                # para não disparar na hora ao entrar na prancha.
                sem_rosto_desde = None

            # ---------------------------------------------------------
            # Decisão de seleção (sempre atualizada no modo ativo, mesmo
            # sem rosto, para que a tolerância de perda de foco funcione).
            # ---------------------------------------------------------
            decisao = DecisaoSelecao()
            if app.estado in (EstadoApp.ATIVO, EstadoApp.PRANCHA_ATIVO):
                opcao_atual = None
                if rosto_detectado and pose_confiavel:
                    if app.estado == EstadoApp.ATIVO:
                        opcao_atual = {"Esquerda": "SIM", "Direita": "NAO"}.get(
                            lado_detectado
                        )
                    else:
                        opcao_atual = board.classificar(
                            ratio_valido,
                            ratio_y_valido,
                            app.referencias_prancha,
                            raio_max_prancha,
                        )

                decisao = controlador.atualizar(opcao_atual, olhos_fechados, agora)
                app.opcao_focada = decisao.opcao_focada

                if decisao.opcao_confirmada and app.opcao_confirmada is None:
                    app.opcao_confirmada = decisao.opcao_confirmada
                    app.tempo_selecionado = agora
                    logger_raiz.info(
                        "Seleção confirmada: %s (método=%s)",
                        app.opcao_confirmada, decisao.metodo,
                    )
                    feedback.confirmar()

                if controlador.deve_limpar_confirmacao(agora) and not olhos_fechados:
                    # Só libera a próxima seleção depois que os olhos
                    # abrirem, evitando confirmação dupla com a piscada.
                    controlador.reset()
                    app.resetar_selecao()

            tecla = cv2.waitKey(1) & 0xFF

            # =========================================================
            if app.estado == EstadoApp.MENU:
                ui.desenhar_menu(
                    frame, largura, altura,
                    app.calibracao_valida(diferenca_minima),
                    app.media_esquerda_calibrada, app.media_direita_calibrada,
                    app.perfil_ativo, diferenca_minima,
                    prancha_valida=app.prancha_valida(distancia_minima_prancha),
                    prancha_fraca=app.prancha_fraca,
                    camera_ok=camera_pronta(),
                )
                if tecla in (ord('p'), ord('P')):
                    app.transicionar(EstadoApp.SELECIONAR_PERFIL)
                elif tecla in (ord('c'), ord('C')):
                    iniciar_calibracao_prancha(agora)
                elif tecla in (ord('i'), ord('I')):
                    entrar_na_prancha(agora)
                elif tecla in (ord('s'), ord('S')):
                    entrar_no_modo_ativo(agora)
                elif tecla in (ord('v'), ord('V')):
                    iniciar_calibracao(agora)
                elif tecla in (TECLA_F2, ord('g'), ord('G')):
                    app.transicionar(EstadoApp.MODO_CUIDADOR)
                elif tecla in (TECLA_F3, ord('o'), ord('O')):
                    app.transicionar(EstadoApp.CONFIGURACOES)

            # =========================================================
            elif app.estado == EstadoApp.MODO_CUIDADOR:
                ui.desenhar_modo_cuidador(
                    frame, largura, altura,
                    perfil=app.perfil_ativo,
                    prancha_valida=app.prancha_valida(distancia_minima_prancha),
                    prancha_fraca=app.prancha_fraca,
                    calibracao_valida=app.calibracao_valida(diferenca_minima),
                    camera_ok=camera_pronta(),
                    versao=VERSAO,
                )
                if tecla in (27, TECLA_F2, ord('m'), ord('M')):
                    app.transicionar(EstadoApp.MENU)
                elif tecla in (ord('p'), ord('P')):
                    app.transicionar(EstadoApp.SELECIONAR_PERFIL)
                elif tecla in (ord('c'), ord('C')):
                    iniciar_calibracao_prancha(agora)
                elif tecla in (ord('v'), ord('V')):
                    iniciar_calibracao(agora)
                elif tecla in (TECLA_F3, ord('o'), ord('O')):
                    app.transicionar(EstadoApp.CONFIGURACOES)

            # =========================================================
            elif app.estado == EstadoApp.CONFIGURACOES:
                ui.desenhar_configuracoes(
                    frame, largura, altura, cfg, app.perfil_ativo, VERSAO,
                )
                if tecla in (27, TECLA_F3, ord('m'), ord('M')):
                    app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.SELECIONAR_PERFIL:
                perfis = perfis_disponiveis()
                ui.desenhar_selecao_perfil(frame, largura, altura, perfis, app.perfil_ativo)
                if tecla == ord('m'):
                    app.transicionar(EstadoApp.MENU)
                elif tecla == ord('n'):
                    app.nome_digitado = ""
                    app.transicionar(EstadoApp.NOVO_PERFIL)
                elif ord('1') <= tecla <= ord('9'):
                    idx = tecla - ord('1')
                    if idx < len(perfis):
                        nome = perfis[idx]
                        dados_sim = calibrador.carregar(nome)
                        dados_prancha = prancha_gerenciador.carregar(nome)
                        if dados_sim is None and dados_prancha is None:
                            app.avisar(f"Perfil '{nome}' invalido ou corrompido.", agora)
                            feedback.erro()
                        else:
                            aplicar_perfil(nome, dados_sim, dados_prancha)

                            if app.prancha_fraca:
                                app.avisar(
                                    f"Prancha fraca em '{nome}' -- recalibre com [C].",
                                    agora, 4.0,
                                )
                                feedback.erro()
                            logger_raiz.info(
                                "Perfil '%s' carregado (SIM/NAO=%s, prancha=%s).",
                                nome,
                                "ok" if app.calibracao_ja_feita else "ausente",
                                "ok" if app.prancha_calibrada else "ausente",
                            )
                            app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.NOVO_PERFIL:
                ui.desenhar_novo_perfil(frame, largura, altura, app.nome_digitado)
                if tecla == 27:  # ESC
                    app.transicionar(EstadoApp.SELECIONAR_PERFIL)
                elif tecla in (8, 127):  # backspace
                    app.nome_digitado = app.nome_digitado[:-1]
                elif tecla in (13, 10):
                    nome = app.nome_digitado.strip()
                    if not nome:
                        app.avisar("Digite um nome para o perfil.", agora)
                        feedback.erro()
                    elif nome in perfis_disponiveis():
                        app.avisar(f"O perfil '{nome}' ja existe.", agora)
                        feedback.erro()
                    else:
                        app.perfil_ativo = nome
                        app.nome_digitado = ""
                        app.media_esquerda_calibrada = 0.35
                        app.media_direita_calibrada = 0.65
                        app.calibracao_ja_feita = False
                        app.resetar_calibracao()
                        app.resetar_prancha()
                        reiniciar_filtros()
                        app.transicionar(EstadoApp.PRANCHA_CALIB_PREPARAR)
                        logger_raiz.info("Novo perfil '%s' criado.", nome)
                else:
                    caractere = chr(tecla) if tecla else ""
                    if (
                        len(app.nome_digitado) < 20
                        and caractere
                        and (caractere.isascii() and (caractere.isalnum() or caractere in ("_", "-")))
                    ):
                        app.nome_digitado += caractere

            # =========================================================
            # Prancha de comunicação: calibração dos 4 blocos
            # =========================================================
            elif app.estado == EstadoApp.PRANCHA_CALIB_PREPARAR:
                bloco_id = app.bloco_calib_atual()
                ui_prancha.desenhar_calibracao_prancha(
                    frame, largura, altura, bloco_id,
                    app.indice_bloco_calib, len(board.BLOCOS),
                    progresso=0.0,
                    amostras=0,
                    minimo_amostras=calib_cfg["min_amostras"],
                    aguardando=True,
                )

                if tecla == 32:  # ESPAÇO
                    app.coletas_prancha = []
                    app.amostras_ignoradas = 0
                    app.tempo_inicio_coleta_prancha = agora
                    reiniciar_filtros()
                    app.transicionar(EstadoApp.PRANCHA_CALIB_COLETANDO)
                elif tecla == ord('m'):
                    app.resetar_prancha()
                    app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.PRANCHA_CALIB_COLETANDO:
                bloco_id = app.bloco_calib_atual()
                decorrido = (
                    max(0.0, agora - app.tempo_inicio_coleta_prancha)
                    if app.tempo_inicio_coleta_prancha
                    else 0.0
                )
                progresso_tempo = min(
                    decorrido / (calib_cfg["duracao_ms"] / 1000.0), 1.0
                )
                progresso_amostras = min(
                    len(app.coletas_prancha) / calib_cfg["min_amostras"], 1.0
                )
                progresso = min(progresso_tempo, progresso_amostras)

                ui_prancha.desenhar_calibracao_prancha(
                    frame, largura, altura, bloco_id,
                    app.indice_bloco_calib, len(board.BLOCOS),
                    progresso=progresso,
                    amostras=len(app.coletas_prancha),
                    minimo_amostras=calib_cfg["min_amostras"],
                    descartadas=app.amostras_ignoradas,
                )

                if rosto_detectado and not pose_confiavel:
                    ui.desenhar_aviso_cabeca(frame, largura, altura, deslocado=True)

                if (
                    app.tempo_inicio_coleta_prancha
                    and decorrido >= calib_cfg["duracao_ms"] / 1000.0
                    and len(app.coletas_prancha) >= calib_cfg["min_amostras"]
                ):
                    # Mediana por eixo: piscadas residuais e frames ruins
                    # não deslocam o ponto de referência do bloco.
                    xs = [p[0] for p in app.coletas_prancha]
                    ys = [p[1] for p in app.coletas_prancha]
                    app.referencias_prancha[bloco_id] = (
                        float(np.median(xs)),
                        float(np.median(ys)),
                    )
                    logger_raiz.info(
                        "Prancha: bloco '%s' calibrado (x=%.3f, y=%.3f, %d amostras).",
                        bloco_id,
                        app.referencias_prancha[bloco_id][0],
                        app.referencias_prancha[bloco_id][1],
                        len(app.coletas_prancha),
                    )

                    app.coletas_prancha = []
                    app.amostras_ignoradas = 0
                    app.tempo_inicio_coleta_prancha = 0.0
                    reiniciar_filtros()
                    app.indice_bloco_calib += 1

                    if app.indice_bloco_calib >= len(board.BLOCOS):
                        distancia = board.distancia_minima_entre_pontos(
                            app.referencias_prancha
                        )
                        if distancia < distancia_minima_prancha:
                            app.prancha_calibrada = False
                            app.prancha_fraca = True
                            logger_raiz.warning(
                                "Prancha fraca (separação mínima %.3f < %.3f). "
                                "Perfil não será salvo; repita olhando bem para cada cartão.",
                                distancia, distancia_minima_prancha,
                            )
                            feedback.erro()
                        else:
                            try:
                                prancha_gerenciador.salvar(
                                    app.perfil_ativo or "padrao",
                                    app.referencias_prancha,
                                )
                                app.prancha_calibrada = True
                                app.prancha_fraca = False
                                feedback.confirmar()
                            except (ValueError, OSError) as e:
                                app.prancha_calibrada = False
                                app.prancha_fraca = True
                                logger_raiz.error(
                                    "Falha ao salvar calibração da prancha: %s", e
                                )
                                feedback.erro()
                        app.transicionar(EstadoApp.PRANCHA_CALIB_CONCLUIDA)
                    else:
                        app.transicionar(EstadoApp.PRANCHA_CALIB_PREPARAR)

                if tecla == ord('m') and app.estado == EstadoApp.PRANCHA_CALIB_COLETANDO:
                    app.resetar_prancha()
                    app.transicionar(EstadoApp.MENU)
                    logger_raiz.info("Calibração da prancha cancelada pelo usuário.")

            # =========================================================
            elif app.estado == EstadoApp.PRANCHA_CALIB_CONCLUIDA:
                sucesso = app.prancha_calibrada and not app.prancha_fraca
                distancia = (
                    board.distancia_minima_entre_pontos(app.referencias_prancha)
                    if app.referencias_prancha
                    else 0.0
                )
                ui_prancha.desenhar_prancha_concluida(
                    frame, largura, altura, sucesso,
                    app.referencias_prancha, distancia,
                )
                if tecla in (13, 10, ord('m')):
                    app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.PRANCHA_ATIVO:
                if not app.prancha_valida(distancia_minima_prancha):
                    app.avisar("Prancha invalida. Pressione [C].", agora)
                    app.transicionar(EstadoApp.MENU)
                else:
                    ui_prancha.desenhar_prancha(
                        frame, largura, altura,
                        foco=app.opcao_focada,
                        progresso=decisao.progresso,
                        confirmado=app.opcao_confirmada,
                        perfil=app.perfil_ativo,
                    )

                    if rosto_detectado and not pose_confiavel:
                        ui.desenhar_aviso_cabeca(frame, largura, altura, deslocado=True)

                    texto_debug = (
                        f"x:{ratio_valido:.2f} y:{ratio_y_valido:.2f}"
                    )
                    ui.desenhar_debug_gaze(frame, largura, altura, texto_debug)

                    if tecla == ord('m'):
                        controlador.reset()
                        app.resetar_selecao()
                        app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.CALIB_PREPARAR:
                alvo = "SIM" if app.calib_fase == "ESQUERDA" else "NAO"
                ui.desenhar_calibracao_sim_nao(
                    frame, largura, altura,
                    alvo=alvo,
                    coletando=False,
                    progresso=0.0,
                    amostras=0,
                    minimo=calib_cfg["min_amostras"],
                    descartadas=0,
                    media_esq=app.media_esquerda_calibrada,
                    media_dir=app.media_direita_calibrada,
                    historico_esq=historico_esq,
                    historico_dir=historico_dir,
                    tamanho_historico=det_cfg["tamanho_historico_grafico"],
                    perfil=app.perfil_ativo,
                )

                if tecla == 32:
                    app.transicionar(EstadoApp.CALIB_COLETANDO)
                    app.coletas_calibracao = []
                    app.amostras_ignoradas = 0
                    app.tempo_inicio_coleta = agora
                    app.calibracao_ja_feita = False
                    reiniciar_filtros()
                elif tecla == ord('m'):
                    app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.CALIB_COLETANDO:
                alvo = "SIM" if app.calib_fase == "ESQUERDA" else "NAO"

                decorrido = (
                    max(0.0, agora - app.tempo_inicio_coleta)
                    if app.tempo_inicio_coleta
                    else 0.0
                )
                progresso_tempo = min(decorrido / (calib_cfg["duracao_ms"] / 1000.0), 1.0)
                progresso_amostras = min(
                    len(app.coletas_calibracao) / calib_cfg["min_amostras"], 1.0
                )
                progresso = min(progresso_tempo, progresso_amostras)

                ui.desenhar_calibracao_sim_nao(
                    frame, largura, altura,
                    alvo=alvo,
                    coletando=True,
                    progresso=progresso,
                    amostras=len(app.coletas_calibracao),
                    minimo=calib_cfg["min_amostras"],
                    descartadas=app.amostras_ignoradas,
                    media_esq=app.media_esquerda_calibrada,
                    media_dir=app.media_direita_calibrada,
                    historico_esq=historico_esq,
                    historico_dir=historico_dir,
                    tamanho_historico=det_cfg["tamanho_historico_grafico"],
                    perfil=app.perfil_ativo,
                )

                if rosto_detectado and not pose_confiavel:
                    ui.desenhar_aviso_cabeca(frame, largura, altura, deslocado=True)

                if (
                    app.tempo_inicio_coleta
                    and decorrido >= calib_cfg["duracao_ms"] / 1000.0
                    and len(app.coletas_calibracao) >= calib_cfg["min_amostras"]
                ):
                    # Mediana em vez de média: piscadas residuais e frames
                    # ruins não deslocam a referência de calibração.
                    media = float(np.median(app.coletas_calibracao))
                    if app.calib_fase == "ESQUERDA":
                        app.media_esquerda_calibrada = media
                        app.calib_fase = "DIREITA"
                        app.coletas_calibracao = []
                        app.amostras_ignoradas = 0
                        app.tempo_inicio_coleta = 0.0
                        reiniciar_filtros()
                        app.transicionar(EstadoApp.CALIB_PREPARAR)
                        logger_raiz.info("Calibração SIM concluída: %.3f", media)
                    else:
                        app.media_direita_calibrada = media
                        app.coletas_calibracao = []
                        app.amostras_ignoradas = 0
                        app.tempo_inicio_coleta = 0.0
                        diferenca = abs(
                            app.media_direita_calibrada - app.media_esquerda_calibrada
                        )
                        logger_raiz.info(
                            "Calibrado! SIM: %.3f | NAO: %.3f | separação: %.3f",
                            app.media_esquerda_calibrada, app.media_direita_calibrada, diferenca,
                        )
                        if diferenca < diferenca_minima:
                            app.calibracao_ja_feita = False
                            app.calibracao_fraca = True
                            logger_raiz.warning(
                                "Calibração fraca (separação %.3f < %.3f). Perfil NÃO será salvo; "
                                "repita olhando mais para os cantos.",
                                diferenca, diferenca_minima,
                            )
                            feedback.erro()
                        else:
                            try:
                                calibrador.salvar(
                                    app.perfil_ativo or "padrao",
                                    app.media_esquerda_calibrada,
                                    app.media_direita_calibrada,
                                )
                                app.calibracao_ja_feita = True
                                app.calibracao_fraca = False
                                feedback.confirmar()
                            except (ValueError, OSError) as e:
                                app.calibracao_ja_feita = False
                                app.calibracao_fraca = True
                                logger_raiz.error("Falha ao salvar calibração: %s", e)
                                feedback.erro()
                        app.transicionar(EstadoApp.CALIB_CONCLUIDA)

                if tecla == ord('m') and app.estado == EstadoApp.CALIB_COLETANDO:
                    app.tempo_inicio_coleta = 0.0
                    app.coletas_calibracao = []
                    app.calibracao_ja_feita = False
                    app.calibracao_fraca = False
                    app.transicionar(EstadoApp.MENU)
                    logger_raiz.info("Calibração cancelada pelo usuário.")

            # =========================================================
            elif app.estado == EstadoApp.CALIB_CONCLUIDA:
                sucesso = app.calibracao_ja_feita and not app.calibracao_fraca
                ui.desenhar_calibracao_concluida(
                    frame, largura, altura, sucesso,
                    app.media_esquerda_calibrada, app.media_direita_calibrada,
                    abs(app.media_direita_calibrada - app.media_esquerda_calibrada),
                )
                if tecla in (13, 10, ord('m')):
                    app.transicionar(EstadoApp.MENU)

            # =========================================================
            elif app.estado == EstadoApp.ATIVO:
                if not app.calibracao_valida(diferenca_minima):
                    app.avisar("Calibracao invalida. Pressione [C].", agora)
                    app.transicionar(EstadoApp.MENU)
                else:
                    ui.desenhar_painel_sim_nao(
                        frame, largura, altura, metade_x,
                        ativo_sim=(lado_detectado != "Direita"),
                    )

                    texto_debug = (
                        f"esq:{ratio_esq:.2f} dir:{ratio_dir:.2f} | "
                        f"calib SIM:{app.media_esquerda_calibrada:.2f} "
                        f"NAO:{app.media_direita_calibrada:.2f}"
                    )
                    ui.desenhar_debug_gaze(frame, largura, altura, texto_debug)

                    if rosto_detectado and not pose_confiavel:
                        ui.desenhar_aviso_cabeca(frame, largura, altura)

                    ui.desenhar_grafico_temporal(frame, historico_esq, historico_dir,
                                                 app.media_esquerda_calibrada, app.media_direita_calibrada,
                                                 largura_grafico, altura_grafico, pos_x, pos_y,
                                                 det_cfg["tamanho_historico_grafico"])

                    if app.opcao_confirmada is not None:
                        ui.desenhar_selecionado(frame, largura, altura, app.opcao_confirmada)
                    elif decisao.opcao_focada:
                        ui.desenhar_progresso_sim_nao(
                            frame, largura, altura, decisao.opcao_focada,
                            decisao.progresso,
                        )

                    if tecla == ord('m'):
                        controlador.reset()
                        app.resetar_selecao()
                        app.transicionar(EstadoApp.MENU)

            # ---------------------------------------------------------
            # Avisos (desenhados por último, sobre qualquer tela)
            # ---------------------------------------------------------
            if not frame_recebido:
                backend_atual = camera.backend_em_uso
                ui.desenhar_sem_sinal(
                    frame, largura, altura, camera.segundos_sem_frame(),
                    "" if backend_atual == "nenhum" else backend_atual,
                )
            elif avisar_sem_rosto:
                ui.desenhar_aviso_sem_rosto(frame, largura, altura)
            if app.aviso_ativo(agora):
                ui.desenhar_aviso(frame, largura, altura, app.aviso)

            cv2.imshow(janela_cfg["titulo"], frame)

            if tecla == ord('q'):
                logger_raiz.info("Encerrando por solicitação do usuário.")
                break

            # Fecha ao clicar no X da janela (em vez de ficar em loop invisível)
            try:
                if cv2.getWindowProperty(janela_cfg["titulo"], cv2.WND_PROP_VISIBLE) == 0:
                    break
            except cv2.error:
                pass

    except KeyboardInterrupt:
        logger_raiz.info("Encerrando por Ctrl+C.")
    except Exception as e:
        logger_raiz.exception("Erro inesperado durante a execução.")
        mostrar_erro_fatal(f"Ocorreu um erro inesperado:\n{type(e).__name__}: {e}")
        return 1
    finally:
        camera.parar()
        detector.close()
        cv2.destroyAllWindows()
        logger_raiz.info("Sessão encerrada.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
