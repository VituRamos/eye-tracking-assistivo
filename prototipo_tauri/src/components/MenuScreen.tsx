import {
  AlertTriangle,
  ChevronRight,
  Crosshair,
  LogOut,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { ComponentType } from "react";
import type { SnapshotApp } from "../types";
import { IconePrancha, IconeSimNao } from "./Icones";
import { Marca } from "./Marca";
import { StatusPill } from "./StatusPill";

type AcaoMenu = "perfis" | "calibracao" | "cuidador" | "config";

interface Props {
  snapshot: SnapshotApp;
  onIniciar: () => void;
  onSimNao: () => void;
  onAcao: (acao: AcaoMenu) => void;
  onSair: () => void;
}

interface ItemMenu {
  id: AcaoMenu | "iniciar" | "sim_nao" | "sair";
  rotulo: string;
  atalho: string;
  Icone: ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  ativo?: boolean;
  cor?: string;
}

const ITENS: ItemMenu[] = [
  { id: "iniciar", rotulo: "Prancha", atalho: "[I]", Icone: IconePrancha, ativo: true },
  { id: "sim_nao", rotulo: "SIM / NÃO", atalho: "[S]", Icone: IconeSimNao },
  { id: "perfis", rotulo: "Perfis", atalho: "[P]", Icone: Users },
  { id: "calibracao", rotulo: "Calibração", atalho: "[C]", Icone: Crosshair },
  { id: "cuidador", rotulo: "Modo Cuidador", atalho: "[F2]", Icone: ShieldCheck },
  { id: "config", rotulo: "Configurações", atalho: "[F3]", Icone: Settings },
];

/** Resumo do rosto para a tela inicial (item pedido no teste de 15/11). */
function estadoRosto(snapshot: SnapshotApp): { valor: string; cor: string } {
  if (!snapshot.cameraOk) return { valor: "Sem câmera", cor: "text-atencao" };
  if (!snapshot.rostoOk) return { valor: "Sem rosto", cor: "text-atencao" };
  if (snapshot.olhosFechados)
    return { valor: "Olhos fechados", cor: "text-apoio" };
  if (!snapshot.poseOk) return { valor: "Cabeça virada", cor: "text-atencao" };
  if (snapshot.config.deteccao.distanciaHabilitada) {
    if (snapshot.distanciaEstado === "longe")
      return { valor: "Rosto longe", cor: "text-atencao" };
    if (snapshot.distanciaEstado === "perto")
      return { valor: "Rosto perto", cor: "text-atencao" };
    if (snapshot.distanciaEstado === "boa")
      return { valor: "Rosto na distância", cor: "text-confirmado" };
  }
  return { valor: "Rosto detectado", cor: "text-confirmado" };
}

export function MenuScreen({ snapshot, onIniciar, onSimNao, onAcao, onSair }: Props) {
  const semCalibracao = !snapshot.pranchaCalibrada;
  const statusPrancha = snapshot.pranchaCalibrada
    ? { texto: "Concluída", cor: "text-confirmado" }
    : snapshot.pranchaFraca
      ? { texto: "Fraca", cor: "text-atencao" }
      : { texto: "Pendente", cor: "text-atencao" };
  const rosto = estadoRosto(snapshot);

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <aside className="absolute inset-y-0 left-0 w-[300px] border-r border-borda bg-superficie">
        <Marca x={32} y={36} />
        <span className="absolute left-[70px] top-[48px] -translate-y-1/2 text-[20px] font-semibold tracking-tight text-texto">
          Prancha
        </span>
        <span className="absolute left-[32px] top-[80px] -translate-y-1/2 text-[13px] text-apoio">
          Comunicação pelo olhar
        </span>

        <nav className="absolute left-0 top-[136px] w-full">
          {ITENS.map((item) => (
            <Item
              key={item.id}
              item={item}
              onClick={() => {
                if (item.id === "iniciar") onIniciar();
                else if (item.id === "sim_nao") onSimNao();
                else onAcao(item.id as AcaoMenu);
              }}
            />
          ))}
          <div className="my-[22px] h-px bg-borda" />
          <button
            onClick={onSair}
            className="group relative flex h-[56px] w-full items-center gap-2 rounded-r-[12px] pl-[44px] pr-3 text-left transition hover:bg-atencao-fundo"
          >
            <LogOut size={22} strokeWidth={2.1} className="text-atencao" />
            <span className="text-[18px] text-atencao">Sair</span>
            <span className="ml-auto text-[12px] text-apoio">[Q]</span>
          </button>
        </nav>

        <span className="absolute bottom-[24px] left-[32px] text-[12px] text-apoio">
          v{snapshot.versao} · aplicativo
        </span>
      </aside>

      <main className="absolute inset-y-0 left-[300px] w-[980px]">
        <span className="absolute left-[44px] top-[44px] -translate-y-1/2 text-[14px] text-apoio">
          Início
        </span>

        <div className="absolute right-[56px] top-[26px] flex items-center gap-[10px]">
          <StatusPill
            ativo={snapshot.cameraOk}
            texto={snapshot.cameraOk ? "Câmera pronta" : "Sem câmera"}
          />
          <StatusPill
            ativo={snapshot.rostoOk && !snapshot.olhosFechados && snapshot.poseOk}
            texto={
              !snapshot.rostoOk
                ? "Sem rosto"
                : snapshot.olhosFechados
                  ? "Olhos fechados"
                  : !snapshot.poseOk
                    ? "Cabeça virada"
                    : "Rosto detectado"
            }
          />
        </div>

        <h1 className="absolute left-[44px] top-[110px] -translate-y-1/2 text-[42px] font-bold leading-none tracking-tight text-texto">
          Olá, {snapshot.perfil || "sem perfil"}
        </h1>
        <p className="absolute left-[44px] top-[152px] -translate-y-1/2 text-[20px] text-apoio">
          O que você quer fazer?
        </p>

        {semCalibracao && (
          <div className="absolute left-[44px] top-[188px] flex -translate-y-1/2 items-center gap-2 text-atencao">
            <AlertTriangle size={18} strokeWidth={2.2} />
            <span className="text-[15px]">
              {snapshot.pranchaFraca
                ? "Calibração fraca. Pressione [C] para refazer."
                : "Prancha sem calibração. Pressione [C] para calibrar."}
            </span>
          </div>
        )}

        <button
          onClick={onIniciar}
          aria-label="Abrir a prancha de comunicação"
          className="group absolute left-[44px] top-[214px] h-[306px] w-[600px] overflow-hidden rounded-[30px] bg-destaque text-left transition duration-200 hover:-translate-y-[1px] hover:shadow-[0_22px_60px_rgba(27,36,48,0.30)] active:translate-y-0"
        >
          <IconePrancha
            size={132}
            strokeWidth={0.85}
            className="absolute left-[110px] top-[153px] -translate-x-1/2 -translate-y-1/2 text-destaque-texto"
          />
          <span className="absolute left-[216px] top-[126px] -translate-y-1/2 text-[54px] font-bold leading-none tracking-tight text-destaque-texto">
            Prancha
          </span>
          <span className="absolute left-[218px] top-[172px] -translate-y-1/2 text-[18px] text-destaque-texto/70">
            {semCalibracao
              ? "Calibre a prancha para começar"
              : "Abrir a prancha de comunicação"}
          </span>
          <ChevronRight
            size={38}
            strokeWidth={2}
            className="absolute right-[20px] top-[153px] -translate-y-1/2 text-destaque-texto/70 transition-transform duration-200 group-hover:translate-x-1"
          />
        </button>

        <section className="absolute right-[56px] top-[214px] h-[306px] w-[256px] rounded-[22px] border border-borda bg-superficie p-6">
          <p className="text-[13px] text-apoio">Perfil ativo</p>
          <p className="mt-1 text-[26px] font-semibold leading-tight text-texto">
            {snapshot.perfil || "Nenhum"}
          </p>
          <div className="my-3 h-px bg-borda" />

          <div className="space-y-[13px]">
            <Linha rotulo="Prancha" valor={statusPrancha.texto} cor={statusPrancha.cor} />
            <Linha
              rotulo="SIM / NÃO"
              valor={snapshot.calibracaoSimNao ? "Calibrado" : "Pendente"}
              cor={snapshot.calibracaoSimNao ? "text-confirmado" : "text-atencao"}
            />
            <Linha
              rotulo="Câmera"
              valor={snapshot.cameraOk ? "Pronta" : "Sem sinal"}
              cor={snapshot.cameraOk ? "text-confirmado" : "text-atencao"}
            />
            <Linha
              rotulo="Rosto"
              valor={rosto.valor}
              cor={rosto.cor}
            />
          </div>
        </section>

        <p className="absolute left-[44px] right-[56px] top-[690px] -translate-y-1/2 text-center text-[14px] text-apoio">
          Use as teclas indicadas para escolher uma opção.
        </p>
      </main>
    </div>
  );
}

function Item({ item, onClick }: { item: ItemMenu; onClick: () => void }) {
  const { Icone } = item;
  return (
    <button
      onClick={onClick}
      className={`group relative flex h-[56px] w-full items-center gap-2 rounded-r-[12px] pl-[44px] pr-3 text-left transition ${
        item.ativo ? "bg-neutro" : "hover:bg-neutro/60"
      }`}
    >
      {item.ativo && (
        <span className="absolute left-0 top-[12px] h-[32px] w-[4px] rounded-full bg-texto" />
      )}
      <Icone
        size={22}
        strokeWidth={2.1}
        className={item.cor ?? (item.ativo ? "text-texto" : "text-apoio")}
      />
      <span
        className={
          item.ativo
            ? "text-[19px] font-semibold text-texto"
            : "text-[18px] text-apoio"
        }
      >
        {item.rotulo}
      </span>
      <span className="ml-auto text-[12px] text-apoio">{item.atalho}</span>
    </button>
  );
}

function Linha({
  rotulo,
  valor,
  cor,
}: {
  rotulo: string;
  valor: string;
  cor: string;
}) {
  return (
    <div>
      <p className="text-[13px] leading-none text-apoio">{rotulo}</p>
      <p className={`mt-1 text-[15px] font-semibold leading-none ${cor}`}>
        {valor}
      </p>
    </div>
  );
}
