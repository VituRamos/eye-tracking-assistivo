"""
Camada de apresentação (OpenCV).

Tudo que desenha na tela mora aqui. Nada neste arquivo calcula gaze ou
decide transição de estado -- ele só recebe números/estado já prontos
e desenha. Isso permite, no futuro, trocar esse arquivo por uma UI Qt
ou por eventos WebSocket para um front-end web, sem tocar no restante
do sistema (ver core/gaze_engine.py e core/state_machine.py).
"""
from __future__ import annotations

import cv2
import numpy as np


def preparar_frame(frame, largura: int, altura: int):
    """
    Garante um canvas no tamanho de projeto (ex.: 1280x720).

    Se a câmera entregar outra resolução, redimensiona preservando a
    proporção e adiciona barras pretas. Assim o layout (que usa
    coordenadas fixas) nunca "estoura" a tela em webcams 640x480.
    """
    altura_atual, largura_atual = frame.shape[:2]
    if (largura_atual, altura_atual) == (largura, altura):
        return frame

    escala = min(largura / largura_atual, altura / altura_atual)
    nova_largura = max(1, round(largura_atual * escala))
    nova_altura = max(1, round(altura_atual * escala))
    redimensionado = cv2.resize(frame, (nova_largura, nova_altura), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((altura, largura, 3), dtype=frame.dtype)
    x = (largura - nova_largura) // 2
    y = (altura - nova_altura) // 2
    canvas[y:y + nova_altura, x:x + nova_largura] = redimensionado
    return canvas


def extrair_roi_do_olho(frame, landmarks, indices_cantos, indices_iris, largura, altura):
    """
    Monta um recorte (ROI) da região do olho para exibição de debug,
    com um marcador verde na posição estimada da íris.
    """
    p1 = landmarks[indices_cantos[0]]
    p2 = landmarks[indices_cantos[1]]
    x1_px, y1_px = p1.x * largura, p1.y * altura
    x2_px, y2_px = p2.x * largura, p2.y * altura

    xs_iris = [landmarks[i].x * largura for i in indices_iris]
    ys_iris = [landmarks[i].y * altura for i in indices_iris]
    iris_cx = float(np.mean(xs_iris))
    iris_cy = float(np.mean(ys_iris))

    x_esq, x_dir = min(x1_px, x2_px), max(x1_px, x2_px)
    largura_olho = max(x_dir - x_esq, 1e-3)
    cy_medio = (y1_px + y2_px) / 2
    margem_y = largura_olho * 0.7
    margem_x = largura_olho * 0.2

    x1c = int(max(0, x_esq - margem_x))
    x2c = int(min(largura, x_dir + margem_x))
    y1c = int(max(0, cy_medio - margem_y))
    y2c = int(min(altura, cy_medio + margem_y))

    roi = frame[y1c:y2c, x1c:x2c].copy()
    if roi.size > 0:
        px = int(min(max(iris_cx - x1c, 0), roi.shape[1] - 1))
        py = int(min(max(iris_cy - y1c, 0), roi.shape[0] - 1))
        cv2.circle(roi, (px, py), 2, (0, 255, 0), -1)
    return roi


def desenhar_recortes_debug(frame, roi_esq, roi_dir):
    if frame.shape[0] < 110 or frame.shape[1] < 310:
        return
    if roi_esq.size > 0:
        frame[20:110, 20:160] = cv2.resize(roi_esq, (140, 90))
        cv2.rectangle(frame, (20, 20), (160, 110), (255, 255, 255), 1)
    if roi_dir.size > 0:
        frame[20:110, 170:310] = cv2.resize(roi_dir, (140, 90))
        cv2.rectangle(frame, (170, 20), (310, 110), (255, 255, 255), 1)


def desenhar_grafico_temporal(frame, hist_esq, hist_dir, media_esq, media_dir,
                               largura_grafico, altura_grafico, x, y, tamanho_historico):
    cv2.rectangle(frame, (x, y), (x + largura_grafico, y + altura_grafico), (15, 15, 15), -1)
    cv2.rectangle(frame, (x, y), (x + largura_grafico, y + altura_grafico), (255, 255, 255), 1)

    def valor_para_y(v):
        v = min(max(v, 0.0), 1.0)
        return int(y + altura_grafico - (v * altura_grafico))

    ponto_medio = (media_esq + media_dir) / 2
    cv2.line(frame, (x, valor_para_y(media_esq)), (x + largura_grafico, valor_para_y(media_esq)), (0, 200, 0), 1)
    cv2.line(frame, (x, valor_para_y(media_dir)), (x + largura_grafico, valor_para_y(media_dir)), (0, 0, 220), 1)
    for xi in range(x, x + largura_grafico, 8):
        cv2.line(frame, (xi, valor_para_y(ponto_medio)),
                 (min(xi + 4, x + largura_grafico), valor_para_y(ponto_medio)),
                 (130, 130, 130), 1)

    def desenhar_serie(historico, cor):
        pontos = list(historico)
        n = len(pontos)
        if n < 2:
            return
        for i in range(1, n):
            x1 = int(x + (i - 1) * largura_grafico / tamanho_historico)
            x2 = int(x + i * largura_grafico / tamanho_historico)
            y1 = valor_para_y(pontos[i - 1])
            y2 = valor_para_y(pontos[i])
            cv2.line(frame, (x1, y1), (x2, y2), cor, 1)

    desenhar_serie(hist_esq, (255, 255, 0))
    desenhar_serie(hist_dir, (255, 0, 255))

    cv2.putText(frame, "Sinal temporal (ratio_x da iris)", (x, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
    cv2.putText(frame, "olho esq", (x + 8, y + altura_grafico - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (255, 255, 0), 1)
    cv2.putText(frame, "olho dir", (x + 90, y + altura_grafico - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (255, 0, 255), 1)
    cv2.putText(frame, "ref. SIM", (x + largura_grafico - 150, y + altura_grafico - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, (0, 200, 0), 1)
    cv2.putText(frame, "ref. NAO", (x + largura_grafico - 75, y + altura_grafico - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, (0, 0, 220), 1)


def desenhar_painel_sim_nao(frame, overlay, largura, altura, metade_x, cor_sim, cor_nao, intensidade=0.25):
    cv2.rectangle(overlay, (0, 0), (metade_x, altura), cor_sim, -1)
    cv2.rectangle(overlay, (metade_x, 0), (largura, altura), cor_nao, -1)
    cv2.addWeighted(overlay, intensidade, frame, 1 - intensidade, 0, frame)
    cv2.line(frame, (metade_x, 0), (metade_x, altura), (255, 255, 255), 2)
    cv2.putText(frame, "SIM", (metade_x // 2 - 50, altura // 2), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 3)
    cv2.putText(frame, "NAO", (metade_x + (metade_x // 2) - 50, altura // 2),
                cv2.FONT_HERSHEY_DUPLEX, 2, (255, 255, 255), 3)


def desenhar_aviso_sem_rosto(frame, largura, altura):
    cv2.rectangle(frame, (0, altura // 2 - 40), (largura, altura // 2 + 40), (0, 0, 100), -1)
    cv2.putText(frame, "Rosto nao detectado -- reposicione-se em frente a camera",
                (largura // 2 - 420, altura // 2 + 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2)


def desenhar_sem_sinal(frame, largura, altura, segundos: float, backend: str = ""):
    """
    Tela cheia de aviso quando a câmera parou de entregar imagens.

    Evita a pior experiência possível: uma janela preta que parece
    travada, sem dizer ao cuidador o que fazer.
    """
    cv2.rectangle(frame, (0, 0), (largura, altura), (18, 18, 18), -1)

    if segundos == float("inf"):
        detalhe = "A câmera não entregou nenhuma imagem desde a abertura."
    else:
        decorrido = "menos de 1 segundo" if segundos < 1 else f"{segundos:.0f} segundos"
        detalhe = f"Última imagem recebida há {decorrido}."

    cv2.putText(frame, "SEM SINAL DA CAMERA", (largura // 2 - 300, altura // 2 - 120),
                cv2.FONT_HERSHEY_DUPLEX, 1.4, (0, 200, 255), 3)
    cv2.putText(frame, detalhe, (largura // 2 - 340, altura // 2 - 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (230, 230, 230), 2)

    dicas = [
        "1. Feche outros programas que usam a webcam (Teams, Zoom, navegador).",
        "2. Verifique o cabo e tente outra porta USB.",
        "3. Confira Configuracoes > Privacidade > Camera.",
        "4. Pressione [Q] para sair e reabra o programa.",
    ]
    for i, dica in enumerate(dicas):
        cv2.putText(frame, dica, (largura // 2 - 360, altura // 2 + 10 + i * 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, (200, 200, 200), 1)

    if backend:
        cv2.putText(frame, f"Backend em uso: {backend}", (largura // 2 - 360, altura // 2 + 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (140, 140, 140), 1)


def desenhar_aviso(frame, largura, altura, texto):
    """Faixa de aviso temporário (ex.: calibração fraca, perfil inválido)."""
    (largura_texto, _altura_texto), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
    x1 = max(10, largura // 2 - largura_texto // 2 - 20)
    x2 = min(largura - 10, largura // 2 + largura_texto // 2 + 20)
    y1 = altura - 95
    y2 = altura - 55
    cv2.rectangle(frame, (x1, y1), (x2, y2), (20, 20, 20), -1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 255), 1)
    cv2.putText(frame, texto, (x1 + 14, y2 - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 2)


def desenhar_menu(frame, largura, altura, calibracao_valida, media_esq, media_dir,
                  perfil=None, diferenca_minima=0.03, prancha_valida=False,
                  prancha_fraca=False):
    cv2.rectangle(frame, (0, 0), (largura, altura), (30, 30, 30), -1)
    cv2.putText(frame, "EYE-TRACKING ASSISTIVO v2.1", (largura // 2 - 290, altura // 2 - 200),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)

    cor_prancha = (0, 255, 0) if prancha_valida else (120, 120, 120)
    cor_sim_nao = (0, 255, 0) if calibracao_valida else (120, 120, 120)
    itens = [
        ("[I]  Prancha de comunicacao", cor_prancha),
        ("[C]  Calibrar prancha (4 blocos)", (0, 255, 255)),
        ("[S]  Modo SIM / NAO (legado)", cor_sim_nao),
        ("[V]  Calibrar SIM / NAO", (0, 255, 255)),
        ("[P]  Selecionar perfil", (0, 255, 255)),
        ("[Q]  Sair", (0, 0, 255)),
    ]
    for i, (texto, cor) in enumerate(itens):
        cv2.putText(frame, texto, (largura // 2 - 230, altura // 2 - 100 + i * 48),
                    cv2.FONT_HERSHEY_DUPLEX, 0.85, cor, 2)

    if prancha_valida:
        texto_prancha = f"Prancha calibrada (perfil: {perfil or 'padrao'})"
        cor_status = (0, 220, 0)
    elif prancha_fraca:
        texto_prancha = "Prancha fraca -- recalibre os 4 blocos com [C]"
        cor_status = (0, 180, 255)
    else:
        texto_prancha = "Prancha sem calibracao -- pressione [C] para calibrar"
        cor_status = (0, 180, 255)
    cv2.putText(frame, texto_prancha, (largura // 2 - 380, altura // 2 + 175),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor_status, 1)

    if calibracao_valida:
        texto_sim_nao = (f"SIM/NAO (legado): calibrado  |  "
                         f"SIM {media_esq:.2f}  NAO {media_dir:.2f}")
        cor_sim_nao_status = (0, 200, 0)
    else:
        texto_sim_nao = "SIM/NAO (legado): sem calibracao -- use [V] se precisar"
        cor_sim_nao_status = (150, 150, 150)
    cv2.putText(frame, texto_sim_nao, (largura // 2 - 380, altura // 2 + 205),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, cor_sim_nao_status, 1)

    cv2.putText(frame, "Dica: mantenha o rosto enquadrado e a cabeca ereta",
                (largura // 2 - 300, altura - 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (170, 170, 170), 1)


def desenhar_selecao_perfil(frame, largura, altura, perfis: list[str], perfil_ativo: str | None = None):
    cv2.rectangle(frame, (0, 0), (largura, altura), (25, 25, 40), -1)
    cv2.putText(frame, "SELECIONAR PERFIL", (largura // 2 - 220, 80),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
    if not perfis:
        cv2.putText(frame, "Nenhum perfil salvo ainda.", (largura // 2 - 200, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 1)
    for i, nome in enumerate(perfis[:9]):
        marcador = "  <-- ativo" if nome == perfil_ativo else ""
        cv2.putText(frame, f"[{i + 1}]  {nome}{marcador}", (largura // 2 - 150, 150 + i * 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    if len(perfis) > 9:
        cv2.putText(frame, f"(mostrando 9 de {len(perfis)} perfis)", (largura // 2 - 150, 150 + 9 * 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
    cv2.putText(frame, "[N] Novo perfil    [M] Voltar ao menu", (largura // 2 - 260, altura - 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)


def desenhar_novo_perfil(frame, largura, altura, nome_digitado: str):
    cv2.rectangle(frame, (0, 0), (largura, altura), (25, 40, 25), -1)
    cv2.putText(frame, "NOVO PERFIL", (largura // 2 - 150, 100),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
    cv2.putText(frame, "Digite um nome (letras, numeros, '_' ou '-'):",
                (largura // 2 - 300, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
    cv2.rectangle(frame, (largura // 2 - 250, 220), (largura // 2 + 250, 290), (10, 10, 10), -1)
    cv2.rectangle(frame, (largura // 2 - 250, 220), (largura // 2 + 250, 290), (255, 255, 255), 2)
    cv2.putText(frame, nome_digitado + "_", (largura // 2 - 235, 268),
                cv2.FONT_HERSHEY_DUPLEX, 1.0, (0, 255, 255), 2)
    cv2.putText(frame, "[ENTER] Confirmar e calibrar    [ESC] Cancelar",
                (largura // 2 - 310, altura - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 180, 180), 1)


def desenhar_calibracao_concluida(frame, largura, altura, sucesso, media_esq, media_dir, diferenca):
    cor_fundo = (20, 60, 20) if sucesso else (60, 20, 20)
    cv2.rectangle(frame, (0, 0), (largura, altura), cor_fundo, -1)
    titulo = "CALIBRACAO CONCLUIDA!" if sucesso else "CALIBRACAO FRACA"
    cv2.putText(frame, titulo, (largura // 2 - 260, altura // 2 - 80),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
    cv2.putText(frame, f"SIM: {media_esq:.2f}   NAO: {media_dir:.2f}   Separacao: {diferenca:.3f}",
                (largura // 2 - 300, altura // 2 - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    if sucesso:
        mensagem = "Perfil salvo. Aperte ENTER para voltar ao menu."
    else:
        mensagem = ("Repita a calibracao olhando mais para os cantos da tela "
                    "(diferenca minima nao atingida).")
    cv2.putText(frame, mensagem, (largura // 2 - 420, altura // 2 + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 220, 255), 1)
    cv2.putText(frame, "Aperte [ENTER] para voltar ao menu",
                (largura // 2 - 230, altura // 2 + 100),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)


def desenhar_selecionado(frame, largura, altura, opcao_confirmada):
    texto = f"SELECIONADO: {opcao_confirmada}"
    fonte = cv2.FONT_HERSHEY_SIMPLEX
    escala = 0.7
    espessura = 2
    (largura_texto, altura_texto), _ = cv2.getTextSize(texto, fonte, escala, espessura)
    padding = 10

    x2 = largura - 20
    x1 = x2 - largura_texto - (padding * 2)
    y1 = 120
    y2 = y1 + altura_texto + (padding * 2)

    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), -1)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), 2)
    cv2.putText(frame, texto, (x1 + padding, y2 - padding - 5), fonte, escala, (0, 0, 0), espessura)
