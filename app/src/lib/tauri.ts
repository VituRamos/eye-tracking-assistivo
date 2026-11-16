/** Utilidades de janela que só existem quando rodando dentro do Tauri. */

async function janelaTauri() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    return getCurrentWindow();
  } catch {
    return null;
  }
}

export async function fecharJanela(): Promise<boolean> {
  const janela = await janelaTauri();
  if (!janela) return false;
  await janela.close();
  return true;
}

export async function alternarTelaCheia(): Promise<boolean | null> {
  const janela = await janelaTauri();
  if (!janela) return null;
  const atual = await janela.isFullscreen();
  await janela.setFullscreen(!atual);
  return !atual;
}

/**
 * Aplica a tela cheia e a resolução escolhidas nas configurações.
 *
 * Quando a tela cheia está ativa (padrão), a janela ocupa a tela inteira
 * e a resolução não é aplicada. Ao desligar a tela cheia, a janela assume
 * a resolução escolhida; se não couber, reduz proporcionalmente (16:9) e
 * centraliza.
 */
export async function aplicarJanela(
  resolucao: string,
  fullscreen: boolean,
): Promise<boolean | null> {
  const janela = await janelaTauri();
  if (!janela) return null;

  const emTelaCheia = await janela.isFullscreen();
  if (fullscreen) {
    if (!emTelaCheia) await janela.setFullscreen(true);
    return true;
  }
  if (emTelaCheia) {
    await janela.setFullscreen(false);
  }

  const [largura, altura] = resolucao.split("x").map(Number);
  if (!Number.isFinite(largura) || !Number.isFinite(altura)) return false;

  const disponivelLargura = window.screen.availWidth;
  const disponivelAltura = window.screen.availHeight;
  const fator = Math.min(
    1,
    (disponivelLargura - 24) / largura,
    (disponivelAltura - 64) / altura,
  );
  const alvoLargura = Math.max(640, Math.round(largura * fator));
  const alvoAltura = Math.max(360, Math.round(altura * fator));

  if (await janela.isMaximized()) {
    await janela.unmaximize();
  }

  const { LogicalSize } = await import("@tauri-apps/api/dpi");
  await janela.setSize(new LogicalSize(alvoLargura, alvoAltura));
  await janela.center();
  return true;
}
