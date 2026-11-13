import { AlertTriangle, Check } from "lucide-react";
import type { SnapshotApp } from "../types";
import { GazeChart } from "./GazeChart";
import { ScreenHeader } from "./ScreenHeader";

interface Props {
  snapshot: SnapshotApp;
  onIniciar: () => void;
  onVoltar: () => void;
}

/**
 * Calibração SIM/NÃO em três estados: preparar, coletando e concluída.
 * Mantém o painel de duas metades e o gráfico temporal do _v2.
 */
export function CalibrationSimNaoScreen({ snapshot, onIniciar, onVoltar }: Props) {
  const calib = snapshot.calibracao;
  const concluida = snapshot.tela === "CALIB_CONCLUIDA";
  const coletando = snapshot.tela === "CALIB_COLETANDO";
  const alvo = calib.alvo;
  const ativoSim = alvo === "SIM";

  if (concluida) {
    return (
      <div className="anim-entrada absolute inset-0 bg-fundo">
        <ScreenHeader titulo="Calibração SIM/NÃO" subtitulo="Modo legado" />

        <div className="absolute left-1/2 top-[250px] -translate-x-1/2 -translate-y-1/2">
          {calib.sucesso ? (
            <span className="grid size-[56px] place-items-center rounded-full bg-confirmado text-fundo">
              <Check size={30} strokeWidth={3.2} />
            </span>
          ) : (
            <span className="grid size-[56px] place-items-center rounded-full bg-atencao-fundo text-atencao">
              <AlertTriangle size={30} strokeWidth={2.4} />
            </span>
          )}
        </div>

        <h1 className="absolute left-1/2 top-[288px] w-full -translate-x-1/2 -translate-y-1/2 text-center text-[40px] font-bold tracking-tight text-texto">
          {calib.sucesso ? "Calibração concluída" : "Calibração fraca"}
        </h1>
        <p className="absolute left-1/2 top-[328px] w-full -translate-x-1/2 -translate-y-1/2 text-center text-[20px] text-apoio">
          {calib.sucesso
            ? "Perfil salvo. O modo SIM/NÃO está pronto."
            : "Repita olhando mais para os cantos da tela."}
        </p>

        <div className="absolute left-1/2 top-[380px] flex h-[90px] w-[560px] -translate-x-1/2 items-center rounded-[18px] border border-borda bg-superficie">
          <Valor rotulo="SIM" valor={calib.mediaEsq.toFixed(2)} cor="text-confirmado" />
          <Valor rotulo="NÃO" valor={calib.mediaDir.toFixed(2)} cor="text-atencao" />
          <Valor
            rotulo="Separação"
            valor={calib.diferenca.toFixed(3)}
            cor={calib.sucesso ? "text-confirmado" : "text-atencao"}
          />
        </div>

        <button
          onClick={onVoltar}
          className="absolute left-1/2 top-[560px] -translate-x-1/2 rounded-lg px-3 py-1 text-[16px] font-semibold text-texto transition hover:bg-neutro"
        >
          Aperte [ENTER] para voltar ao menu
        </button>
      </div>
    );
  }

  return (
    <div className="anim-entrada absolute inset-0 overflow-hidden">
      <div className="absolute inset-y-0 left-0 w-[640px] bg-confirmado-fundo" />
      <div className="absolute inset-y-0 left-[640px] w-[640px] bg-atencao-fundo" />

      <ScreenHeader
        titulo="Calibração SIM/NÃO"
        subtitulo={`Perfil: ${snapshot.perfil || "padrão"} · modo legado`}
        direita={
          <span className="text-[16px] font-semibold text-texto">
            Olhe para {alvo}
          </span>
        }
      />

      <span
        className="absolute text-[110px] font-bold leading-none tracking-tight"
        style={{
          left: 320,
          top: 322,
          transform: "translate(-50%, -50%)",
          color: ativoSim
            ? "var(--color-confirmado)"
            : "color-mix(in srgb, var(--color-confirmado) 55%, var(--color-fundo))",
        }}
      >
        SIM
      </span>
      <span
        className="absolute text-[110px] font-bold leading-none tracking-tight"
        style={{
          left: 960,
          top: 322,
          transform: "translate(-50%, -50%)",
          color: ativoSim
            ? "color-mix(in srgb, var(--color-atencao) 55%, var(--color-fundo))"
            : "var(--color-atencao)",
        }}
      >
        NÃO
      </span>
      <span
        className="absolute top-[414px] -translate-x-1/2 text-[18px] text-apoio"
        style={{ left: ativoSim ? 320 : 960 }}
      >
        olhe para este lado
      </span>

      <div className="absolute inset-y-0 left-[639px] w-[2px] bg-borda" />

      {coletando ? (
        <>
          <div className="absolute left-[56px] right-[56px] top-[86px] h-[10px] overflow-hidden rounded-[5px] bg-neutro">
            <span
              className="block h-full rounded-[5px] bg-texto transition-[width] duration-100"
              style={{ width: `${Math.min(100, Math.max(0, calib.progresso * 100))}%` }}
            />
          </div>
          <p className="absolute left-1/2 top-[122px] -translate-x-1/2 -translate-y-1/2 text-[15px] text-apoio">
            {calib.amostras}/{calib.minimo} amostras válidas ·{" "}
            {calib.descartadas} descartadas
          </p>
          <button
            onClick={onVoltar}
            className="absolute left-[56px] top-[700px] -translate-y-1/2 rounded-lg px-2 py-1 text-[15px] text-apoio transition hover:bg-superficie/60"
          >
            [M] Cancelar calibração
          </button>
          <GazeChart
            historico={snapshot.historico}
            mediaEsq={calib.mediaEsq}
            mediaDir={calib.mediaDir}
          />
        </>
      ) : (
        <>
          <p className="absolute left-1/2 top-[108px] -translate-x-1/2 -translate-y-1/2 text-[18px] text-apoio">
            Posicione o olhar fixo para o lado {alvo}.
          </p>
          <p className="absolute left-[56px] top-[700px] -translate-y-1/2 text-[14px] text-apoio">
            SIM {calib.mediaEsq.toFixed(2)} · NÃO {calib.mediaDir.toFixed(2)}
          </p>
          <button
            onClick={onIniciar}
            className="absolute left-1/2 top-[700px] -translate-x-1/2 -translate-y-1/2 rounded-lg px-3 py-1 text-[15px] text-apoio transition hover:bg-superficie/70"
          >
            Aperte ESPAÇO para começar a coleta · [M] Voltar ao menu
          </button>
        </>
      )}
    </div>
  );
}

function Valor({ rotulo, valor, cor }: { rotulo: string; valor: string; cor: string }) {
  return (
    <div className="flex-1 text-center">
      <p className="text-[14px] text-apoio">{rotulo}</p>
      <p className={`mt-2 text-[24px] font-semibold leading-none ${cor}`}>{valor}</p>
    </div>
  );
}
