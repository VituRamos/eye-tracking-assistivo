import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { BoardCalibrationScreen } from "./components/BoardCalibrationScreen";
import { BoardScreen } from "./components/BoardScreen";
import { BootScreen, ErrorScreen } from "./components/BootScreens";
import { CalibrationChoiceScreen } from "./components/CalibrationChoiceScreen";
import { CalibrationSimNaoScreen } from "./components/CalibrationSimNaoScreen";
import { CaregiverScreen, type AcaoCuidador } from "./components/CaregiverScreen";
import { ExitConfirmScreen } from "./components/ExitConfirmScreen";
import { MenuScreen } from "./components/MenuScreen";
import { NewProfileScreen } from "./components/NewProfileScreen";
import { NoSignalScreen } from "./components/NoSignalScreen";
import { ProfilesScreen } from "./components/ProfilesScreen";
import { RecenterModal } from "./components/RecenterModal";
import { SettingsScreen } from "./components/SettingsScreen";
import { SimNaoScreen } from "./components/SimNaoScreen";
import { Stage } from "./components/Stage";
import { Toast } from "./components/Toast";
import { WarningBanner } from "./components/WarningBanner";
import { useBackend } from "./hooks/useBackend";
import { alternarTelaCheia, aplicarJanela, fecharJanela } from "./lib/tauri";
import type { BlocoId } from "./types";

export default function App() {
  const { snapshot, enviar, definirPointer } = useBackend();
  const [nomeNovo, setNomeNovo] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [confirmandoSaida, setConfirmandoSaida] = useState(false);
  const [recentralizando, setRecentralizando] = useState(false);
  const timerToast = useRef<number | undefined>(undefined);
  const ultimoAviso = useRef<string | null>(null);

  const mostrarToast = useCallback((texto: string) => {
    setToast(texto);
    if (timerToast.current) window.clearTimeout(timerToast.current);
    timerToast.current = window.setTimeout(() => setToast(null), 3200);
  }, []);

  const sair = useCallback(async () => {
    enviar({ tipo: "sair" });
    const ok = await fecharJanela();
    if (!ok) mostrarToast("No navegador, feche a aba para sair.");
  }, [enviar, mostrarToast]);

  const telaCheia = useCallback(async () => {
    const resultado = await alternarTelaCheia();
    if (resultado === null) {
      mostrarToast("Tela cheia disponível apenas no app desktop.");
    }
  }, [mostrarToast]);

  // Avisos vindos do motor (ex.: prancha sem calibração).
  useEffect(() => {
    if (snapshot.aviso && snapshot.aviso !== ultimoAviso.current) {
      ultimoAviso.current = snapshot.aviso;
      mostrarToast(snapshot.aviso);
    }
    if (!snapshot.aviso) ultimoAviso.current = null;
  }, [snapshot.aviso, mostrarToast]);

  // Limpa o nome ao sair da tela de criação.
  useEffect(() => {
    if (snapshot.tela !== "NOVO_PERFIL") setNomeNovo("");
  }, [snapshot.tela]);

  // Aplica a tela cheia/resolução salvas assim que o motor entrega a configuração.
  const janelaAplicada = useRef<string | null>(null);
  const resolucao = snapshot.config.janela.resolucao;
  const telaCheiaConfig = snapshot.config.janela.fullscreen;
  useEffect(() => {
    if (!snapshot.conectado || !snapshot.config.configPath) return;
    const assinatura = `${resolucao}|${telaCheiaConfig}`;
    if (janelaAplicada.current === assinatura) return;
    janelaAplicada.current = assinatura;
    void aplicarJanela(resolucao, telaCheiaConfig);
  }, [snapshot.conectado, snapshot.config.configPath, resolucao, telaCheiaConfig]);

  // Aplica o tema salvo e mantém um espelho local para evitar flash na abertura.
  const tema = snapshot.config.aparencia.tema;
  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    try {
      window.localStorage.setItem("prancha-tema", tema);
    } catch {
      // WebView sem armazenamento local: o tema ainda vale nesta sessão.
    }
  }, [tema]);

  // O diálogo de saída só existe sobre o menu e some se outra tela assumir.
  useEffect(() => {
    if (snapshot.tela !== "MENU" || snapshot.semSinal || snapshot.erroMotor) {
      setConfirmandoSaida(false);
    }
  }, [snapshot.tela, snapshot.semSinal, snapshot.erroMotor]);

  // Recentralização só existe sobre o Modo Cuidador; se a tela mudar
  // (ex.: o motor voltar ao menu), o modal fecha sem aplicar nada.
  useEffect(() => {
    if (snapshot.tela !== "MODO_CUIDADOR" || snapshot.semSinal || snapshot.erroMotor) {
      setRecentralizando(false);
    }
  }, [snapshot.tela, snapshot.semSinal, snapshot.erroMotor]);

  const confirmarNovoPerfil = useCallback(() => {
    const nome = nomeNovo.trim();
    if (!nome) {
      mostrarToast("Digite um nome para o perfil.");
      return;
    }
    enviar({ tipo: "criar_perfil", nome });
  }, [enviar, mostrarToast, nomeNovo]);

  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      // Enquanto o modal de recentralização está aberto, todos os atalhos
      // do aplicativo ficam bloqueados. O próprio modal trata o Escape.
      if (recentralizando) return;

      const alvo = e.target as HTMLElement | null;
      const digitando =
        !!alvo &&
        (alvo.tagName === "INPUT" ||
          alvo.tagName === "TEXTAREA" ||
          alvo.tagName === "SELECT" ||
          alvo.isContentEditable);

      if (e.key === "F11") {
        e.preventDefault();
        void telaCheia();
        return;
      }

      if (digitando) return;

      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const tecla = e.key.toLowerCase();
      const tela = snapshot.tela;

      if (confirmandoSaida) {
        if (e.key === "Escape" || tecla === "n") {
          e.preventDefault();
          setConfirmandoSaida(false);
        } else if (tecla === "q") {
          e.preventDefault();
          setConfirmandoSaida(false);
          void sair();
        }
        return;
      }

      if (tela === "NOVO_PERFIL") {
        if (e.key === "Escape") {
          e.preventDefault();
          enviar({ tipo: "voltar" });
        }
        return;
      }

      if (tecla === "q") {
        e.preventDefault();
        setConfirmandoSaida(true);
        return;
      }

      switch (tela) {
        case "MENU":
          if (tecla === "i") enviar({ tipo: "abrir_prancha" });
          else if (tecla === "s") enviar({ tipo: "abrir_sim_nao" });
          else if (tecla === "p") enviar({ tipo: "abrir_perfis" });
          else if (tecla === "c") enviar({ tipo: "abrir_calibracao" });
          else if (tecla === "v") enviar({ tipo: "calibrar_sim_nao" });
          else if (e.key === "F2" || tecla === "g")
            enviar({ tipo: "modo_cuidador" });
          else if (e.key === "F3" || tecla === "o")
            enviar({ tipo: "configuracoes" });
          break;

        case "ESCOLHER_CALIBRACAO":
          if (e.key === "Escape" || tecla === "m") enviar({ tipo: "voltar" });
          else if (tecla === "1" || tecla === "c" || tecla === "p")
            enviar({ tipo: "calibrar_prancha" });
          else if (tecla === "2" || tecla === "s" || tecla === "v")
            enviar({ tipo: "calibrar_sim_nao" });
          break;

        case "MODO_CUIDADOR":
          if (e.key === "Escape" || e.key === "F2" || tecla === "m")
            enviar({ tipo: "voltar" });
          else if (tecla === "p") enviar({ tipo: "abrir_perfis" });
          else if (tecla === "c") enviar({ tipo: "abrir_calibracao" });
          else if (tecla === "v") enviar({ tipo: "calibrar_sim_nao" });
          else if (tecla === "r") setRecentralizando(true);
          else if (tecla === "u" && snapshot.podeDesfazerRecentralizacao)
            enviar({ tipo: "desfazer_recentralizacao" });
          else if (e.key === "F3" || tecla === "o")
            enviar({ tipo: "configuracoes" });
          break;

        case "CONFIGURACOES":
          if (e.key === "Escape" || e.key === "F3" || tecla === "m")
            enviar({ tipo: "voltar" });
          break;

        case "SELECIONAR_PERFIL":
          if (tecla === "m") enviar({ tipo: "voltar" });
          else if (tecla === "n") enviar({ tipo: "novo_perfil" });
          else if (/^[1-9]$/.test(tecla)) {
            const nome = snapshot.perfis[Number(tecla) - 1];
            if (nome) enviar({ tipo: "selecionar_perfil", nome });
          }
          break;

        case "CALIB_PREPARAR":
        case "PRANCHA_CALIB_PREPARAR":
          if (e.key === " " || e.key === "Spacebar") {
            e.preventDefault();
            enviar({ tipo: "iniciar_coleta" });
          } else if (tecla === "m") enviar({ tipo: "voltar" });
          break;

        case "CALIB_COLETANDO":
        case "PRANCHA_CALIB_COLETANDO":
          if (tecla === "m") enviar({ tipo: "voltar" });
          break;

        case "CALIB_CONCLUIDA":
        case "PRANCHA_CALIB_CONCLUIDA":
          if (e.key === "Enter" || tecla === "m") enviar({ tipo: "voltar" });
          break;

        case "ATIVO":
        case "PRANCHA_ATIVO":
          if (tecla === "m") enviar({ tipo: "voltar" });
          break;

        default:
          break;
      }
    };

    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [
    enviar,
    mostrarToast,
    sair,
    snapshot.perfis,
    snapshot.tela,
    snapshot.podeDesfazerRecentralizacao,
    telaCheia,
    confirmandoSaida,
    recentralizando,
  ]);

  const aoAcaoMenu = (acao: "perfis" | "calibracao" | "cuidador" | "config") => {
    if (acao === "perfis") enviar({ tipo: "abrir_perfis" });
    else if (acao === "calibracao") enviar({ tipo: "abrir_calibracao" });
    else if (acao === "cuidador") enviar({ tipo: "modo_cuidador" });
    else enviar({ tipo: "configuracoes" });
  };

  const aoAcaoCuidador = (acao: AcaoCuidador) => {
    if (acao === "perfis") enviar({ tipo: "abrir_perfis" });
    else if (acao === "escolher_calibracao")
      enviar({ tipo: "abrir_calibracao" });
    else if (acao === "calibrar_prancha") enviar({ tipo: "calibrar_prancha" });
    else if (acao === "calibrar_sim_nao") enviar({ tipo: "calibrar_sim_nao" });
    else if (acao === "recentralizar") setRecentralizando(true);
    else if (acao === "desfazer_recentralizacao")
      enviar({ tipo: "desfazer_recentralizacao" });
    else if (acao === "configuracoes") enviar({ tipo: "configuracoes" });
    else enviar({ tipo: "voltar" });
  };

  const onPointer = definirPointer as ((id: BlocoId | null) => void) | undefined;

  let conteudo: ReactNode;
  switch (snapshot.tela) {
    case "MENU":
      conteudo = (
        <MenuScreen
          snapshot={snapshot}
          onIniciar={() => enviar({ tipo: "abrir_prancha" })}
          onSimNao={() => enviar({ tipo: "abrir_sim_nao" })}
          onAcao={aoAcaoMenu}
          onSair={() => setConfirmandoSaida(true)}
        />
      );
      break;
    case "PRANCHA_ATIVO":
      conteudo = (
        <BoardScreen
          snapshot={snapshot}
          onVoltar={() => enviar({ tipo: "voltar" })}
          onPointer={onPointer}
        />
      );
      break;
    case "ATIVO":
      conteudo = (
        <SimNaoScreen
          snapshot={snapshot}
          onVoltar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    case "SELECIONAR_PERFIL":
      conteudo = (
        <ProfilesScreen
          snapshot={snapshot}
          onSelecionar={(nome) => enviar({ tipo: "selecionar_perfil", nome })}
          onNovo={() => enviar({ tipo: "novo_perfil" })}
          onVoltar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    case "NOVO_PERFIL":
      conteudo = (
        <NewProfileScreen
          nome={nomeNovo}
          onChange={setNomeNovo}
          onConfirmar={confirmarNovoPerfil}
          onCancelar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    case "PRANCHA_CALIB_PREPARAR":
    case "PRANCHA_CALIB_COLETANDO":
    case "PRANCHA_CALIB_CONCLUIDA":
      conteudo = (
        <BoardCalibrationScreen
          snapshot={snapshot}
          onIniciar={() => enviar({ tipo: "iniciar_coleta" })}
          onVoltar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    case "CALIB_PREPARAR":
    case "CALIB_COLETANDO":
    case "CALIB_CONCLUIDA":
      conteudo = (
        <CalibrationSimNaoScreen
          snapshot={snapshot}
          onIniciar={() => enviar({ tipo: "iniciar_coleta" })}
          onVoltar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    case "MODO_CUIDADOR":
      conteudo = <CaregiverScreen snapshot={snapshot} onAcao={aoAcaoCuidador} />;
      break;
    case "ESCOLHER_CALIBRACAO":
      conteudo = (
        <CalibrationChoiceScreen
          snapshot={snapshot}
          onPrancha={() => enviar({ tipo: "calibrar_prancha" })}
          onSimNao={() => enviar({ tipo: "calibrar_sim_nao" })}
          onVoltar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    case "CONFIGURACOES":
      conteudo = (
        <SettingsScreen
          snapshot={snapshot}
          onSalvar={(config) => enviar({ tipo: "atualizar_config", config })}
          onVoltar={() => enviar({ tipo: "voltar" })}
        />
      );
      break;
    default:
      conteudo = (
        <MenuScreen
          snapshot={snapshot}
          onIniciar={() => enviar({ tipo: "abrir_prancha" })}
          onSimNao={() => enviar({ tipo: "abrir_sim_nao" })}
          onAcao={aoAcaoMenu}
          onSair={() => setConfirmandoSaida(true)}
        />
      );
  }

  const emDeteccao =
    snapshot.tela === "PRANCHA_ATIVO" ||
    snapshot.tela === "ATIVO" ||
    snapshot.tela === "PRANCHA_CALIB_COLETANDO" ||
    snapshot.tela === "CALIB_COLETANDO";
  const aviso =
    emDeteccao && !snapshot.semSinal
      ? snapshot.avisoSemRosto
        ? "Aproxime o rosto da câmera. A prancha continua aqui."
        : snapshot.avisoCabeca
          ? "Olhe para a tela."
          : snapshot.distanciaAviso && snapshot.distanciaEstado === "longe"
            ? "Aproxime o rosto da câmera."
            : snapshot.distanciaAviso && snapshot.distanciaEstado === "perto"
              ? "Afaste um pouco o rosto da câmera."
              : null
      : null;
  const iconeAviso = snapshot.avisoSemRosto
    ? "rosto"
    : snapshot.avisoCabeca
      ? "cabeca"
      : "alerta";
  const avisoDeslocado =
    snapshot.tela === "PRANCHA_ATIVO" ||
    snapshot.tela === "PRANCHA_CALIB_COLETANDO";

  return (
    <>
      <Stage>
        {conteudo}

        {aviso && (
          <WarningBanner
            texto={aviso}
            icone={iconeAviso}
            deslocado={avisoDeslocado}
          />
        )}

        {snapshot.semSinal && (
          <NoSignalScreen
            snapshot={snapshot}
            onVoltar={() => enviar({ tipo: "voltar" })}
          />
        )}

        {!snapshot.conectado && !snapshot.erroMotor && (
          <BootScreen
            texto={snapshot.bootTexto ?? "Conectando ao motor de rastreamento..."}
          />
        )}

        {snapshot.erroMotor && (
          <ErrorScreen texto={snapshot.erroMotor} onFechar={() => void sair()} />
        )}

        {recentralizando && snapshot.tela === "MODO_CUIDADOR" && (
          <RecenterModal
            snapshot={snapshot}
            onAplicar={(dx, dy) => {
              enviar({ tipo: "recentralizar", dx, dy });
              setRecentralizando(false);
            }}
            onFechar={() => setRecentralizando(false)}
          />
        )}

        {confirmandoSaida && (
          <ExitConfirmScreen
            onContinuar={() => setConfirmandoSaida(false)}
            onSair={() => {
              setConfirmandoSaida(false);
              void sair();
            }}
          />
        )}
      </Stage>

      {toast && <Toast texto={toast} />}
    </>
  );
}
