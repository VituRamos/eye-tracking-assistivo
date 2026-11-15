import { useEffect, useMemo, useRef, useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";
import { BLOCOS, bloco, type BlocoId, type SnapshotApp } from "../types";
import { criarProjecaoMapa } from "./mapaOlhar";

/**
 * Recentralização de 1 ponto.
 *
 * O cuidador escolhe um cartão conhecido, coleta o olhar por alguns
 * segundos e vê a prévia do deslocamento. Aplicar move todos os cartões
 * juntos; o motor salva o ajuste e oferece "desfazer" uma vez.
 *
 * A coleta acontece aqui na interface, quadro a quadro, para não criar
 * um novo estado no motor. O motor recebe apenas o deslocamento final.
 */

const DURACAO_COLETA_MS = 1500;
const MIN_AMOSTRAS = 12;
const TAM = 240;
const MARGEM = 18;
const UTIL = TAM - MARGEM * 2;

type Fase = "instrucao" | "coletando" | "previa";

interface Props {
  snapshot: SnapshotApp;
  onAplicar: (dx: number, dy: number) => void;
  onFechar: () => void;
}

interface Ponto {
  x: number;
  y: number;
}

function limitar(valor: number): number {
  return Math.min(1, Math.max(0, valor));
}

function porcentagem(valor: number): string {
  return `${Math.round(limitar(valor) * 100)}%`;
}

function mediana(valores: number[]): number {
  if (valores.length === 0) return 0;
  const ordenados = [...valores].sort((a, b) => a - b);
  const meio = Math.floor(ordenados.length / 2);
  return ordenados.length % 2
    ? ordenados[meio]
    : (ordenados[meio - 1] + ordenados[meio]) / 2;
}

function deslocamento(dx: number, dy: number): string {
  const sinal = (valor: number) => (valor > 0 ? "+" : "");
  return `${sinal(dx)}${(dx * 100).toFixed(1)}% / ${sinal(dy)}${(dy * 100).toFixed(1)}%`;
}

export function RecenterModal({ snapshot, onAplicar, onFechar }: Props) {
  const referencias = snapshot.pranchaCalib.referencias;
  const temReferencias = BLOCOS.every((b) => Boolean(referencias[b.id]));

  const [alvo, setAlvo] = useState<BlocoId>("oi");
  const [fase, setFase] = useState<Fase>("instrucao");
  const [amostras, setAmostras] = useState<Ponto[]>([]);
  const inicio = useRef(0);
  const ultimo = useRef(snapshot);
  const botaoPrincipal = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    ultimo.current = snapshot;
  }, [snapshot]);

  useEffect(() => {
    botaoPrincipal.current?.focus();
  }, [fase]);

  // Esc fecha sem alterar nada. Os demais atalhos do app ficam bloqueados
  // enquanto este modal está aberto.
  useEffect(() => {
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onFechar();
      }
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [onFechar]);

  useEffect(() => {
    if (fase !== "coletando") return;

    const coletar = window.setInterval(() => {
      const s = ultimo.current;
      const quadroValido =
        s.rostoOk &&
        s.poseOk &&
        !s.olhosFechados &&
        s.gaze.valido &&
        s.gaze.divergenciaOk !== false;
      if (!quadroValido) return;
      setAmostras((anteriores) => [
        ...anteriores,
        { x: s.gaze.x, y: s.gaze.y },
      ]);
    }, 50);

    const terminar = window.setInterval(() => {
      if (performance.now() - inicio.current >= DURACAO_COLETA_MS) {
        setFase("previa");
      }
    }, 100);

    return () => {
      window.clearInterval(coletar);
      window.clearInterval(terminar);
    };
  }, [fase]);

  const inicioColeta = () => {
    inicio.current = performance.now();
    setAmostras([]);
    setFase("coletando");
  };

  const escolherAlvo = (id: BlocoId) => {
    if (fase === "coletando") return;
    setAlvo(id);
    setAmostras([]);
    setFase("instrucao");
  };

  const referencia = referencias[alvo];
  const medido = amostras.length
    ? {
        x: mediana(amostras.map((p) => p.x)),
        y: mediana(amostras.map((p) => p.y)),
      }
    : null;
  const delta =
    referencia && medido
      ? { dx: medido.x - referencia[0], dy: medido.y - referencia[1] }
      : null;

  const novas = useMemo(() => {
    if (!delta) return null;
    const saida: Record<string, [number, number]> = {};
    for (const [id, ponto] of Object.entries(referencias)) {
      const nx = ponto[0] + delta.dx;
      const ny = ponto[1] + delta.dy;
      if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return null;
      saida[id] = [nx, ny];
    }
    return saida;
  }, [referencias, delta]);

  // Mesma projeção do mapa do olhar, montada com as referências ATUAIS.
  // Assim os cartões salvos caem nos quadrantes e a prévia mostra o quanto
  // eles andam quando o deslocamento for aplicado.
  const projecao = useMemo(
    () => criarProjecaoMapa(referencias),
    [referencias],
  );
  const paraPixel = (valor: number) => MARGEM + limitar(valor) * UTIL;
  const pixel = (ponto: [number, number]) => {
    const projetado = projecao.projetar(ponto[0], ponto[1]);
    return { x: paraPixel(projetado.x), y: paraPixel(projetado.y) };
  };

  const medidoPixel = medido ? pixel([medido.x, medido.y]) : null;

  const amostrasSuficientes = amostras.length >= MIN_AMOSTRAS;
  const podeAplicar = Boolean(novas) && amostrasSuficientes;
  const progresso =
    fase === "coletando"
      ? Math.min(1, (performance.now() - inicio.current) / DURACAO_COLETA_MS)
      : fase === "previa"
        ? 1
        : 0;

  const erro = !temReferencias
    ? "Calibre a prancha antes de recentralizar."
    : fase === "previa" && !amostrasSuficientes
      ? "Poucas amostras válidas. Tente de novo mantendo o olhar no cartão."
      : fase === "previa" && !novas
        ? "O ajuste sairia da área calibrada. Repita a calibração da prancha."
        : null;

  return (
    <div className="absolute inset-0 z-50 grid place-items-center bg-black/45 backdrop-blur-[2px]">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-recentralizar"
        className="w-[900px] rounded-[26px] border border-borda bg-superficie px-[36px] py-[28px] shadow-[0_30px_90px_rgba(0,0,0,0.35)]"
      >
        <div className="flex items-start justify-between gap-6">
          <div>
            <h2
              id="titulo-recentralizar"
              className="text-[32px] font-bold leading-none tracking-tight text-texto"
            >
              Recentralizar o olhar
            </h2>
            <p className="mt-[10px] text-[15px] leading-snug text-apoio">
              Use um cartão conhecido para corrigir o desvio do olhar sem
              refazer a calibração completa.
            </p>
          </div>
          <span className="rounded-full bg-neutro px-3 py-1 text-[12px] font-semibold text-texto">
            1 ponto
          </span>
        </div>

        <div className="mt-[20px] grid grid-cols-[260px_1fr] gap-[26px]">
          <div>
            <svg
              viewBox={`0 0 ${TAM} ${TAM}`}
              className="h-[260px] w-[260px]"
              role="img"
              aria-label="Prévia do deslocamento dos cartões"
            >
              <rect
                x="1"
                y="1"
                width={TAM - 2}
                height={TAM - 2}
                rx="16"
                fill="var(--color-fundo)"
                stroke="var(--color-borda)"
              />
              <line
                x1={MARGEM}
                x2={TAM - MARGEM}
                y1={TAM / 2}
                y2={TAM / 2}
                stroke="var(--color-borda)"
                strokeDasharray="3 5"
              />
              <line
                x1={TAM / 2}
                x2={TAM / 2}
                y1={MARGEM}
                y2={TAM - MARGEM}
                stroke="var(--color-borda)"
                strokeDasharray="3 5"
              />

              {BLOCOS.map((b) => {
                const antigo = referencias[b.id];
                const novo = novas?.[b.id];
                if (!antigo && !novo) return null;
                const origem = pixel(antigo ?? novo!);
                const destino = pixel(novo ?? antigo!);
                return (
                  <g key={b.id}>
                    <line
                      x1={origem.x}
                      y1={origem.y}
                      x2={destino.x}
                      y2={destino.y}
                      stroke="var(--color-texto)"
                      strokeOpacity={0.45}
                      strokeWidth={1.6}
                      strokeDasharray="4 4"
                    />
                    {antigo && (
                      <circle
                        cx={origem.x}
                        cy={origem.y}
                        r={11}
                        fill={b.cor}
                        fillOpacity={0.22}
                        stroke="var(--color-borda)"
                        strokeDasharray="3 3"
                      />
                    )}
                    {novo && (
                      <circle
                        cx={destino.x}
                        cy={destino.y}
                        r={b.id === alvo ? 15 : 12}
                        fill={b.cor}
                        fillOpacity={0.95}
                        stroke={
                          b.id === alvo
                            ? "var(--color-texto)"
                            : "var(--color-borda)"
                        }
                        strokeWidth={b.id === alvo ? 2.5 : 1}
                      />
                    )}
                    <text
                      x={Math.min(TAM - 28, Math.max(28, destino.x))}
                      y={Math.min(TAM - 4, destino.y + 26)}
                      textAnchor="middle"
                      className="fill-apoio text-[10px]"
                    >
                      {b.rotulo}
                    </text>
                  </g>
                );
              })}

              {medidoPixel && (
                <g>
                  <circle
                    cx={medidoPixel.x}
                    cy={medidoPixel.y}
                    r={9}
                    fill="none"
                    stroke="var(--color-atencao)"
                    strokeWidth={2}
                  />
                  <line
                    x1={medidoPixel.x - 12}
                    y1={medidoPixel.y}
                    x2={medidoPixel.x + 12}
                    y2={medidoPixel.y}
                    stroke="var(--color-atencao)"
                    strokeWidth={1.5}
                  />
                  <line
                    x1={medidoPixel.x}
                    y1={medidoPixel.y - 12}
                    x2={medidoPixel.x}
                    y2={medidoPixel.y + 12}
                    stroke="var(--color-atencao)"
                    strokeWidth={1.5}
                  />
                </g>
              )}
            </svg>
            <p className="mt-[8px] text-[12px] leading-snug text-apoio">
              Círculos vazados: posição salva. Círculos cheios: prévia depois
              do ajuste.
            </p>
          </div>

          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-texto">
              1. Cartão de referência
            </p>
            <p className="mt-[4px] text-[12px] leading-snug text-apoio">
              Peça para a pessoa olhar bem para o centro deste cartão.
            </p>
            <div className="mt-[10px] grid grid-cols-2 gap-[8px]">
              {BLOCOS.map((b) => {
                const ativo = b.id === alvo;
                return (
                  <button
                    key={b.id}
                    type="button"
                    disabled={fase === "coletando"}
                    onClick={() => escolherAlvo(b.id)}
                    className={`flex h-[42px] items-center gap-[9px] rounded-[11px] border px-3 text-left text-[15px] font-semibold transition disabled:opacity-50 ${
                      ativo
                        ? "border-texto bg-neutro text-texto"
                        : "border-borda text-apoio hover:bg-neutro/60"
                    }`}
                  >
                    <span
                      className="size-[12px] shrink-0 rounded-full"
                      style={{ backgroundColor: b.cor }}
                    />
                    {b.rotulo}
                    {ativo && (
                      <Check size={16} strokeWidth={2.6} className="ml-auto" />
                    )}
                  </button>
                );
              })}
            </div>

            <div className="mt-[18px] rounded-[14px] border border-borda bg-fundo px-[16px] py-[13px]">
              {fase === "instrucao" && (
                <p className="text-[14px] leading-snug text-apoio">
                  2. Quando o olhar estiver estável em{" "}
                  <strong className="text-texto">{bloco(alvo).rotulo}</strong>,
                  inicie a coleta.
                </p>
              )}

              {fase === "coletando" && (
                <>
                  <p className="text-[14px] font-semibold text-texto">
                    Coletando o olhar em {bloco(alvo).rotulo}…
                  </p>
                  <div className="mt-[10px] h-[8px] overflow-hidden rounded-[4px] bg-neutro">
                    <span
                      className="block h-full rounded-[4px] bg-texto transition-[width] duration-100"
                      style={{ width: `${Math.round(progresso * 100)}%` }}
                    />
                  </div>
                  <p className="mt-[5px] text-[12px] text-apoio">
                    {amostras.length} amostras válidas · mínimo {MIN_AMOSTRAS}
                  </p>
                </>
              )}

              {fase === "previa" && (
                <>
                  <p className="text-[14px] font-semibold text-texto">
                    Prévia do ajuste
                  </p>
                  <p className="mt-[4px] text-[13px] leading-snug text-apoio">
                    {medido
                      ? `Olhar medido em ${porcentagem(medido.x)} / ${porcentagem(medido.y)}.`
                      : "Sem amostras válidas."}
                  </p>
                  {delta && (
                    <p className="mt-[3px] text-[13px] leading-snug text-apoio">
                      Deslocamento:{" "}
                      <strong className="text-texto">
                        {deslocamento(delta.dx, delta.dy)}
                      </strong>
                    </p>
                  )}
                  <p className="mt-[3px] text-[12px] leading-snug text-apoio">
                    Os quatro cartões serão movidos juntos. Dá para desfazer
                    depois.
                  </p>
                </>
              )}

              {erro && (
                <p className="mt-[8px] rounded-[9px] bg-atencao-fundo px-3 py-2 text-[12px] leading-snug text-atencao">
                  {erro}
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="mt-[20px] flex items-center justify-between">
          <p className="max-w-[420px] text-[12px] leading-snug text-apoio">
            Aviso só para o cuidador. A seleção e os tempos da prancha não
            mudam.
          </p>
          <div className="flex items-center gap-[10px]">
            {fase === "instrucao" && (
              <>
                <button
                  type="button"
                  onClick={onFechar}
                  className="inline-flex h-[46px] items-center gap-2 rounded-[11px] border border-borda px-4 text-[15px] font-semibold text-texto transition hover:bg-neutro"
                >
                  <X size={17} strokeWidth={2.3} />
                  Cancelar
                </button>
                <button
                  ref={botaoPrincipal}
                  type="button"
                  disabled={!temReferencias}
                  onClick={inicioColeta}
                  className="h-[46px] rounded-[11px] bg-texto px-5 text-[15px] font-semibold text-fundo transition hover:opacity-90 disabled:opacity-40"
                >
                  Começar coleta
                </button>
              </>
            )}

            {fase === "coletando" && (
              <button
                ref={botaoPrincipal}
                type="button"
                onClick={() => setFase("previa")}
                className="inline-flex h-[46px] items-center gap-2 rounded-[11px] border border-borda px-4 text-[15px] font-semibold text-texto transition hover:bg-neutro"
              >
                Parar e ver prévia
              </button>
            )}

            {fase === "previa" && (
              <>
                <button
                  type="button"
                  onClick={onFechar}
                  className="inline-flex h-[46px] items-center gap-2 rounded-[11px] border border-borda px-4 text-[15px] font-semibold text-texto transition hover:bg-neutro"
                >
                  <X size={17} strokeWidth={2.3} />
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={() => setFase("instrucao")}
                  className="inline-flex h-[46px] items-center gap-2 rounded-[11px] border border-borda px-4 text-[15px] font-semibold text-texto transition hover:bg-neutro"
                >
                  <RotateCcw size={17} strokeWidth={2.3} />
                  Coletar de novo
                </button>
                <button
                  ref={botaoPrincipal}
                  type="button"
                  disabled={!podeAplicar}
                  onClick={() => {
                    if (delta && podeAplicar) onAplicar(delta.dx, delta.dy);
                  }}
                  className="h-[46px] rounded-[11px] bg-texto px-5 text-[15px] font-semibold text-fundo transition hover:opacity-90 disabled:opacity-40"
                >
                  Aplicar ajuste
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
