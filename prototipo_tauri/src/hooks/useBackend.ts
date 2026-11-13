import { useSyncExternalStore } from "react";
import { fakeBackend } from "../backend/fakeBackend";
import { emTauri, realBackend } from "../backend/realBackend";
import type { BlocoId, Comando } from "../types";

/**
 * Liga a interface ao motor real (dentro do Tauri) ou ao backend de
 * demonstração (navegador). O contrato de snapshot + comandos é o mesmo.
 */
const backend = emTauri() ? realBackend : fakeBackend;
const ehDemo = backend === fakeBackend;
const definirPointerDemo = ehDemo ? fakeBackend.definirPointer : undefined;

export function useBackend() {
  const snapshot = useSyncExternalStore(
    backend.subscribe,
    backend.getSnapshot,
    backend.getSnapshot,
  );

  return {
    snapshot,
    enviar: (comando: Comando) => backend.comando(comando),
    /** Só existe no backend de demonstração (mouse como olhar). */
    definirPointer: definirPointerDemo as ((id: BlocoId | null) => void) | undefined,
  };
}
