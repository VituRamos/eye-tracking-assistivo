import { AlertTriangle, Check } from "lucide-react";
import { BLOCOS, bloco, type BlocoId, type SnapshotApp } from "../types";
import { ALVOS_CALIBRACAO, referenciasCompletas } from "./mapaOlhar";
import { OlharCursor, type CentroCartao } from "./OlharCursor";
import { Pictograma } from "./Pictograma";
import { ScreenHeader } from "./ScreenHeader";

interface Props {
  snapshot: SnapshotApp;
  onIniciar: () => void;
  onVoltar: () => void;
  /**
   * Referências da calibração anterior. A calibração em andamento começa
   * com as referências vazias, mas o ponto do olhar ainda pode usar as
   * antigas para se posicionar sobre os cartões.
   */
  referenciasAntigas?: Record<string, [number, number]>;
}

const TOPO = 124;
const BASE = 66;
const MARGEM = 56;
const ESPACAMENTO = 22;
const LARGURA_UTIL = 1280 - 2 * MARGEM - ESPACAMENTO;
const ALTURA_UTIL = 720 - TOPO - BASE - ESPACAMENTO;
const CELULA_L = Math.floor(LARGURA_UTIL / 2);
const CELULA_A = Math.floor(ALTURA_UTIL / 2);

function caixa(indice: number) {
  const coluna = indice % 2;
  const linha = Math.floor(indice / 2);
  const x = MARGEM + coluna * (CELULA_L + ESPACAMENTO);
  const y = TOPO + linha * (CELULA_A + ESPACAMENTO);
  return { left: x, top: y, width: CELULA_L, height: CELULA_A };
}

/** Alvos de calibração: o canto externo de cada caixa. */
const CENTROS: Record<BlocoId, CentroCartao> = ALVOS_CALIBRACAO;

/** Calibração da prancha: destaca o bloco alvo e mostra a coleta. */
export function BoardCalibrationScreen({
  snapshot,
  onIniciar,
  onVoltar,
  referenciasAntigas,
}: Props) {
  const calib = snapshot.pranchaCalib;
  const concluida = snapshot.tela === "PRANCHA_CALIB_CONCLUIDA";
  const alvo = calib.blocoId;

  const antigas = referenciasCompletas(referenciasAntigas)
    ? referenciasAntigas
    : undefined;
  const atuais = referenciasCompletas(snapshot.pranchaCalib.referencias)
    ? snapshot.pranchaCalib.referencias
    : undefined;
  const referenciasOlhar = antigas ?? atuais;

  if (concluida) {
    return (
      <div className="anim-entrada absolute inset-0 bg-fundo">
        <ScreenHeader titulo="Calibração da prancha" subtitulo="Modo cuidador" />

        <div className="absolute left-1/2 top-[218px] -translate-x-1/2 -translate-y-1/2">
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

        <h1 className="absolute left-1/2 top-[286px] w-full -translate-x-1/2 -translate-y-1/2 text-center text-[40px] font-bold tracking-tight text-texto">
          {calib.sucesso ? "Calibração concluída" : "Calibração fraca"}
        </h1>
        <p className="absolute left-1/2 top-[326px] w-[980px] -translate-x-1/2 -translate-y-1/2 text-center text-[19px] text-apoio">
          {calib.sucesso
            ? "Qualidade boa. A prancha já está pronta."
            : "Os cartões ficaram muito próximos. Repita olhando bem para cada um."}
        </p>

        <div className="absolute left-1/2 top-[374px] flex -translate-x-1/2 gap-[14px]">
          {BLOCOS.map((b) => {
            const ponto = calib.referencias[b.id];
            return (
              <div
                key={b.id}
                className="w-[176px] rounded-[16px] border border-borda bg-superficie py-[14px] text-center"
              >
                <p className="text-[16px] font-semibold text-texto">{b.rotulo}</p>
                <p
                  className={`mt-1 text-[14px] font-semibold ${
                    ponto
                      ? calib.sucesso
                        ? "text-confirmado"
                        : "text-atencao"
                      : "text-atencao"
                  }`}
                >
                  {ponto
                    ? `x=${ponto[0].toFixed(2)}  y=${ponto[1].toFixed(2)}`
                    : "não coletado"}
                </p>
              </div>
            );
          })}
        </div>

        <p className="absolute left-1/2 top-[486px] -translate-x-1/2 -translate-y-1/2 text-[15px] text-apoio">
          Separação mínima entre cartões: {calib.distancia.toFixed(3)}
        </p>

        <button
          onClick={onVoltar}
          className="absolute left-1/2 top-[572px] -translate-x-1/2 rounded-lg px-3 py-1 text-[15px] text-apoio transition hover:bg-neutro"
        >
          Cuidador: [ENTER] para voltar ao menu
        </button>
      </div>
    );
  }

  return (
    <div className="anim-entrada absolute inset-0 bg-fundo">
      <ScreenHeader
        titulo={`Bloco ${calib.indice + 1} de ${calib.total}: olhe para o ponto de ${
          bloco(alvo ?? "oi").rotulo
        }`}
        subtitulo="Calibração da prancha · olhe para o ponto no canto do cartão"
        direita={
          <span className="text-[13px] text-apoio">
            Cuidador: {calib.amostras} amostras válidas · mínimo {calib.minimo}
          </span>
        }
      />

      {BLOCOS.map((b, indice) => {
        const alvoAgora = b.id === alvo;
        const pos = caixa(indice);
        return (
          <div
            key={b.id}
            className={`absolute rounded-[28px] ${
              alvoAgora ? "z-10" : "overflow-hidden"
            }`}
            style={{
              ...pos,
              backgroundColor: alvoAgora ? b.cor : "var(--cor-cartao-inativo)",
              border: `1px solid ${
                alvoAgora
                  ? "color-mix(in srgb, " + b.cor + " 88%, #1B2430)"
                  : "var(--cor-cartao-inativo-borda)"
              }`,
              boxShadow: alvoAgora
                ? "0 0 0 6px var(--color-texto), 0 0 0 13px var(--cor-anel-externo)"
                : undefined,
            }}
          >
            {alvoAgora ? (
              <>
                <Pictograma
                  id={b.id}
                  tamanho={Math.min(pos.width, pos.height) * 0.44}
                  cor="#1B2430"
                  className="absolute left-1/2 top-[40%] -translate-x-1/2 -translate-y-1/2"
                />
                <span className="absolute left-1/2 top-[80%] -translate-x-1/2 -translate-y-1/2 text-[46px] font-bold leading-none tracking-tight text-[#1B2430]">
                  {b.rotulo}
                </span>
                {/* Alvo da calibração: canto externo do cartão. */}
                <span
                  className="absolute z-20 grid size-[34px] -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-[4px] border-[#1B2430] bg-white shadow-[0_3px_12px_rgba(0,0,0,0.30)]"
                  style={{
                    left: ALVOS_CALIBRACAO[b.id].x - pos.left,
                    top: ALVOS_CALIBRACAO[b.id].y - pos.top,
                  }}
                >
                  <span className="size-[9px] rounded-full bg-[#1B2430]" />
                </span>
              </>
            ) : (
              <span className="absolute inset-0 grid place-items-center text-[40px] font-semibold text-apoio">
                {b.rotulo}
              </span>
            )}
          </div>
        );
      })}

      <div className="absolute left-[56px] right-[56px] top-[676px] h-[10px] overflow-hidden rounded-[5px] bg-neutro">
        <span
          className="block h-full rounded-[5px] bg-texto transition-[width] duration-100"
          style={{ width: `${Math.min(100, Math.max(0, calib.progresso * 100))}%` }}
        />
      </div>

      {referenciasOlhar && (
        <OlharCursor
          snapshot={snapshot}
          centros={CENTROS}
          referencias={referenciasOlhar}
          progresso={calib.progresso}
        />
      )}

      {calib.aguardando ? (
        <button
          onClick={onIniciar}
          className="absolute left-1/2 top-[704px] -translate-x-1/2 -translate-y-1/2 rounded-lg px-3 py-1 text-[14px] text-apoio transition hover:bg-neutro"
        >
          Aperte ESPAÇO para começar a coleta · [M] Voltar ao menu
        </button>
      ) : (
        <p className="absolute left-1/2 top-[704px] -translate-x-1/2 -translate-y-1/2 text-[14px] text-apoio">
          {calib.amostras} amostras válidas · {calib.descartadas} descartadas
          (piscada/pose) ·{" "}
          <button
            onClick={onVoltar}
            className="rounded px-1 underline-offset-2 hover:underline"
          >
            [M] Cancelar
          </button>
        </p>
      )}
    </div>
  );
}
