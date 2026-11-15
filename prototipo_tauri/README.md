# Prancha Assistiva

Aplicativo de **comunicação assistiva por rastreamento ocular** para Windows.
A interface é React/Tauri e toda a lógica de câmera, olhar, seleção por dwell,
calibração e perfis roda em um motor Python local (`eye-core`).

**Tudo funciona offline e no próprio computador.** Não há login, nuvem,
telemetria, portas de rede ou envio de imagens para fora da máquina.

## Telas

| Tela | O que faz |
| --- | --- |
| Menu | perfil ativo, status de câmera e calibração, ação Prancha |
| Prancha | 4 cartões (OI, COMER, BEBER, BANHEIRO) escolhidos pelo olhar, com o ponto do olhar e o anel do dwell |
| SIM / NÃO | modo legado com duas metades e confirmação por dwell |
| Perfis | lista, seleção por número e criação de perfil |
| Novo perfil | nome do perfil, seguido da calibração da prancha |
| Escolha de calibração | permite escolher entre prancha e SIM / NÃO |
| Calibração da prancha | coleta o ponto de olhar de cada um dos 4 cartões |
| Calibração SIM / NÃO | calibra os lados esquerdo e direito |
| Modo cuidador | status completo e atalhos de manutenção |
| Configurações | editor completo das opções do aplicativo |
| Sem sinal | orientação ao cuidador quando a câmera para |
| Abertura / erro | progresso da inicialização e diagnóstico de falhas |

## Atalhos

| Tecla | Ação |
| --- | --- |
| `I` | abre a prancha |
| `S` | abre o modo SIM / NÃO |
| `P` | abre os perfis |
| `C` | abre a escolha da calibração (prancha ou SIM / NÃO) |
| `1` / `2` | escolhe a calibração na tela de escolha |
| `V` | calibra SIM / NÃO (legado) |
| `F2` / `G` | modo cuidador |
| `F3` / `O` | configurações |
| `M` / `ESC` | volta ao menu (dependendo da tela) |
| `Q` | sai do aplicativo |
| `F11` | alterna tela cheia |
| `1`–`9` | escolhe um perfil na lista |
| `N` | cria um novo perfil |
| `ESPAÇO` | inicia a coleta na calibração |
| `ENTER` | confirma/volta nas telas concluídas |

Na tela **Novo perfil**, o campo de texto aceita letras, números, `_` e `-`
até 20 caracteres. `ENTER` confirma e inicia a calibração; `ESC` cancela.

Na **Prancha**, uma bolinha indica onde a pessoa está olhando e um anel ao
redor dela se fecha até a confirmação (dwell). Na **calibração da prancha**
o anel acompanha a coleta do cartão; o ponto do olhar usa as referências da
calibração anterior para se posicionar sobre os cartões.

## Como funciona

```
┌─────────────────────────────┐        stdin/stdout (JSON por linha)
│  Interface React + Tauri    │  ────────────────────────────────┐
│  (apresentação e atalhos)   │                                  │
└─────────────────────────────┘                                  ▼
                                              ┌──────────────────────────────┐
                                              │  eye-core.exe (Python)       │
                                              │  câmera, MediaPipe, dwell,   │
                                              │  calibração, perfis, logs    │
                                              └──────────────────────────────┘
```

- O Tauri inicia `eye-core.exe` como processo filho, sem janela de console.
- Comandos da interface vão para o `stdin` do motor, um objeto JSON por linha.
- O motor devolve snapshots a ~30 Hz no `stdout`; o Rust repassa cada linha
  como evento `motor` para o WebView.
- Logs e diagnósticos vão para `stderr` e para a pasta `logs/`, nunca para o
  `stdout` (que é reservado ao protocolo).

## Onde ficam os dados

O aplicativo grava em `%LOCALAPPDATA%\com.eyetracking.prancha`:

```
com.eyetracking.prancha\
├── settings.yaml          # cópia editável da configuração
├── perfis\
│   ├── <nome>.prancha.json
│   └── <nome>.json
└── logs\
    ├── sessao_AAAAMMDD_HHMMSS.log
    └── ponte_stderr.log
```

O `settings.yaml` é criado na primeira execução, mas **não é preciso
editá-lo à mão**: a tela Configurações grava nele de forma atômica.

## Configurações pelo aplicativo

Abra com `F3`. O editor tem sete categorias:

| Categoria | O que ajusta |
| --- | --- |
| Detecção | dwell, tolerância de perda, confirmação, suavização, histórico e aviso sem rosto |
| Distância | aviso informativo de rosto longe/perto, limites e histerese |
| Piscada | ativação, limiar de olho fechado, duração e foco mínimo |
| Calibração | duração, amostras mínimas, ângulo máximo e separação mínima |
| Prancha | distância mínima entre cartões e raio de alcance |
| Câmera | índice, largura, altura, FPS, backend e timeout de abertura |
| Sistema | resolução da janela, validade do perfil e som |

- Detecção, piscada, calibração e som são aplicados na hora.
- Mudanças de câmera exigem reiniciar o aplicativo (a interface avisa).
- `Restaurar padrões` devolve os valores de fábrica ao rascunho;
  `Salvar alterações` valida e grava o `settings.yaml`.
- A tela cheia é o padrão do aplicativo. O `settings.yaml` guarda essa
  escolha e pode ser alterada em Configurações > Sistema; `F11` alterna
  a tela cheia manualmente.
- A resolução aceita **1280x720** ou **1920x1080** e é aplicada quando a
  tela cheia está desligada. Se não couber na tela disponível, a janela
  reduz proporcionalmente e é centralizada.

## Requisitos

| Ferramenta | Versão usada |
| --- | --- |
| Windows | 10 ou 11 (x64) |
| WebView2 | já presente no Windows 10/11 atualizado |
| Câmera | webcam comum, índice 0 por padrão |
| Node.js | 20+ (usado só no build) |
| Rust / Cargo | 1.80+ (usado só no build) |
| Python | 3.11 (usado só no build do motor) |

O aplicativo instalado **não exige Python, Node ou internet**.

## Desenvolvimento

```powershell
cd prototipo_tauri
npm install
npm run dev          # interface no navegador (backend de demonstração)
npm run tauri dev    # app desktop com o motor Python real
```

No navegador, o `fakeBackend` simula olhar/dwell e todas as telas. No
`tauri dev`, o Rust tenta usar o `eye-core.exe` empacotado e, se não existir,
cai para o `.venv\Scripts\python.exe` + `ponte.py` do projeto.

### Gerar o motor

```powershell
cd prototipo_tauri
npm run sidecar
```

O script compila `Ponte.spec` com PyInstaller (modo *onedir*) e copia
`dist/eye-core` para `src-tauri/resources/eye-core`. O `tauri.conf.json`
mapeia o executável e a pasta `_internal` separadamente para preservar a
estrutura que o PyInstaller espera. O pacote inclui `matplotlib` (importado
pelo MediaPipe) com backend `Agg`, sem abrir janelas gráficas.

### Gerar o aplicativo

```powershell
npm run tauri build
```

Saídas:

- `src-tauri\target\release\prancha-assistiva.exe` (portátil)
- `src-tauri\target\release\bundle\nsis\Prancha Assistiva_2.2.4_x64-setup.exe`

O instalador é NSIS, em português (Brasil), e permite instalação por usuário
ou para todos os usuários. Não é assinado digitalmente; o SmartScreen pode
pedir “Mais informações → Executar assim mesmo”.

## Privacidade

- Nenhuma imagem, vídeo ou métrica sai do computador.
- Não há servidor HTTP nem WebSocket; a comunicação é por pipes do processo.
- O modelo do MediaPipe é embutido no pacote, então não há download em uso.
- Perfis e logs ficam na pasta local do usuário.

## Diagnóstico

- Se a câmera não abrir, a tela **Sem sinal** mostra o backend e instruções.
- `logs\ponte_stderr.log` guarda a saída de erro do motor (inclusive falhas
  antes do logging entrar em ação).
- `logs\sessao_*.log` registra calibrações, seleções e erros de cada sessão.
- Para testar sem câmera: `python ponte.py --simular --dados <pasta>`.

## Estrutura

```
prototipo_tauri/
├── src/
│   ├── App.tsx                      # orquestração das 14 telas e atalhos
│   ├── types.ts                     # contrato SnapshotApp + Comando
│   ├── backend/realBackend.ts       # cliente do motor via eventos Tauri
│   ├── backend/fakeBackend.ts       # demonstração no navegador
│   ├── hooks/useBackend.ts          # escolhe real ou demonstração
│   └── components/                  # Menu, Prancha, Perfis, Calibrações...
├── src-tauri/
│   ├── src/lib.rs                   # sidecar: spawn, stdout, comandos
│   ├── tauri.conf.json              # janela, NSIS, recursos
│   └── resources/eye-core/          # motor empacotado (gerado)
├── scripts/build-sidecar.ps1
└── README.md
```

## Limitações

- Calibração e seleção continuam dependendo de iluminação e posição da cabeça;
  o app avisa quando o rosto sai do enquadramento.
- O modo SIM/NÃO permanece como recurso legado.
- A qualidade da calibração é medida pela separação entre os pontos; quando é
  fraca, o app pede para repetir em vez de salvar um perfil ambíguo.
