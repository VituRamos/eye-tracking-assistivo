import type { SnapshotApp } from "../types";
import { GazeMap } from "./GazeMap";
import { ScreenHeader } from "./ScreenHeader";

export type AcaoCuidador =
  | "perfis"
  | "escolher_calibracao"
  | "calibrar_prancha"
  | "calibrar_sim_nao"
  | "recentralizar"
  | "desfazer_recentralizacao"
  | "configuracoes"
  | "voltar";

interface Props {
  snapshot: SnapshotApp;
  onAcao: (acao: AcaoCuidador) => void;
}

export function CaregiverScreen({ snapshot, onAcao }: Props) {
  const prancha = snapshot.pranchaCalibrada
    ? { texto: "Calibrada", cor: "text-confirmado" }
    : snapshot.pranchaFraca
      ? { texto: "Fraca", cor: "text-atencao" }
      : { texto: "Pendente", cor: "text-atencao" };

  const cartoes = [
    { titulo: "Perfil ativo", valor: snapshot.perfil || "Nenhum", cor: "text-texto" },
    { titulo: "Prancha", valor: prancha.texto, cor: prancha.cor },
    {
      titulo: "SIM / NÃO",
      valor: snapshot.calibracaoSimNao ? "Calibrado" : "Pendente",
      cor: snapshot.calibracaoSimNao ? "text-confirmado" : "text-atencao",
    },
    {
      titulo: "Câmera",
      valor: snapshot.cameraOk ? "Pronta" : "Sem sinal",
      cor: snapshot.cameraOk ? "text-confirmado" : "text-atencao",
    },
  ];

  const acoes: {
    tecla: string;
    titulo: string;
    descricao: string;
    acao: AcaoCuidador;
  }[] = [
    {
      tecla: "[P]",
      titulo: "Perfis",
      descricao: "Escolher ou criar o perfil do usuário",
      acao: "perfis",
    },
    {
      tecla: "[C]",
      titulo: "Calibrar a prancha",
      descricao: "Ensina os 4 cartões ao olhar do usuário",
      acao: "escolher_calibracao",
    },
    {
      tecla: "[V]",
      titulo: "Calibrar o SIM / NÃO",
      descricao: "Define o olhar para a esquerda e a direita",
      acao: "calibrar_sim_nao",
    },
    {
      tecla: "[R]",
      titulo: "Recentralizar",
      descricao: "Corrige o ponto com 1 olhar no centro",
      acao: "recentralizar",
    },
    {
      tecla: "[F3]",
      titulo: "Configurações",
      descricao: "Tempos, câmera e tamanho da tela",
      acao: "configuracoes",
    },
  ];

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader titulo="Modo cuidador" subtitulo={`Prancha · v${snapshot.versao}`} />

      <h1 className="absolute left-1/2 top-[166px] w-full -translate-x-1/2 -translate-y-1/2 text-center text-[34px] font-bold tracking-tight text-texto">
        Acompanhe e ajuste o uso
      </h1>
      <p className="absolute left-1/2 top-[206px] w-[1120px] -translate-x-1/2 -translate-y-1/2 text-center text-[17px] leading-snug text-apoio">
        O usuário escolhe mantendo o olhar no cartão — ou piscando. Use as
        ações abaixo para calibrar e ajustar; a prancha continua funcionando.
      </p>

      <div className="absolute left-1/2 top-[250px] flex -translate-x-1/2 gap-[18px]">
        {cartoes.map((c) => (
          <div
            key={c.titulo}
            className="h-[104px] w-[270px] rounded-[18px] border border-borda bg-superficie px-[24px] py-[22px]"
          >
            <p className="text-[13px] leading-none text-apoio">{c.titulo}</p>
            <p className={`mt-[12px] text-[22px] font-semibold leading-none ${c.cor}`}>
              {c.valor}
            </p>
          </div>
        ))}
      </div>

      <section className="absolute left-[56px] top-[386px] h-[252px] w-[572px] rounded-[20px] border border-borda bg-superficie px-[26px] py-[16px]">
        <h2 className="text-[18px] font-semibold leading-tight text-texto">
          Ações do cuidador
        </h2>
        <div className="mt-[6px] space-y-0">
          {acoes.map((item) => (
            <button
              key={item.tecla}
              onClick={() => onAcao(item.acao)}
              className="flex h-[37px] w-full items-center gap-3 rounded-lg px-1 text-left transition hover:bg-neutro/60"
            >
              <span className="inline-flex h-[24px] min-w-[46px] shrink-0 items-center justify-center rounded-full bg-neutro px-2 text-[11.5px] font-semibold text-texto">
                {item.tecla}
              </span>
              <span className="min-w-0">
                <span className="block text-[14px] font-semibold leading-tight text-texto">
                  {item.titulo}
                </span>
                <span className="block truncate text-[11.5px] leading-tight text-apoio">
                  {item.descricao}
                </span>
              </span>
            </button>
          ))}
        </div>
      </section>

      <GazeMap snapshot={snapshot} />

      {snapshot.podeDesfazerRecentralizacao && (
        <button
          onClick={() => onAcao("desfazer_recentralizacao")}
          className="absolute left-[652px] top-[646px] w-[572px] rounded-lg py-1 text-right text-[12px] font-semibold text-apoio transition hover:bg-neutro hover:text-texto"
        >
          [U] Desfazer recentralização
        </button>
      )}

      <button
        onClick={() => onAcao("voltar")}
        className="absolute left-1/2 top-[672px] -translate-x-1/2 rounded-lg px-2 py-1 text-[15px] text-apoio transition hover:bg-neutro"
      >
        [F2] ou [ESC] voltar ao menu
      </button>
    </div>
  );
}
