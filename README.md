# Eye-Tracking Assistivo V2.1

Sistema de comunicação assistiva por rastreamento ocular. O modo
principal é uma **prancha de comunicação em grade** (estilo PECS) com
quatro cartões iniciais -- **OI, COMER, BEBER e BANHEIRO** -- escolhidos
com o olhar. O modo **SIM / NÃO** continua disponível como recurso legado.

Usa MediaPipe Face Landmarker. Esta versão corrige os problemas de
robustez e precisão identificados na revisão do projeto e adiciona
empacotamento em executável Windows.

## Estrutura do projeto

```
eye-tracking-assistivo/
├── config/
│   ├── settings.yaml       # todos os parâmetros ajustáveis (sem editar código)
│   └── loader.py           # leitura do YAML com merge de padrões e validação
├── core/
│   ├── state_machine.py    # Enum de estados + AppState
│   ├── gaze_engine.py      # cálculo puro: ratio, EMA, EAR (piscada), pose
│   ├── board.py            # blocos da prancha + grade 2x2 + classificação
│   ├── board_calibration.py# persistência da calibração da prancha
│   ├── selection.py        # decisão de seleção: dwell por tempo + piscada
│   ├── calibration.py      # persistência/validação de calibração SIM/NÃO
│   ├── camera_thread.py    # captura em thread, com reconexão
│   ├── model_loader.py     # download atômico + verificação SHA256
│   ├── paths.py            # caminhos em dev e no executável (PyInstaller)
│   ├── feedback.py         # bipe de confirmação/erro
│   ├── erros.py            # caixa de erro nativa quando não há console
│   └── logging_config.py   # logging estruturado (arquivo + console)
├── ui/
│   ├── renderer_cv2.py     # menu, perfis e modo SIM/NÃO
│   └── board_renderer.py   # prancha: cartões, ícones e calibração
├── preview_novo_design/    # sandbox do novo design (tema claro; não entra no .exe)
├── tests/                  # 143 testes (puros, sem câmera/MediaPipe)
├── models/                 # modelo .task (baixado no 1º uso; ignorado no git)
├── perfis/                 # calibrações salvas por usuário (runtime)
├── logs/                   # logs de sessão (runtime)
├── main.py                 # ponto de entrada -- só orquestra os módulos
├── EyeTrackingAssistivo.spec
├── build_exe.ps1
├── requirements.txt
├── requirements-dev.txt
├── requirements-preview.txt # Pillow, apenas para o sandbox visual
├── requirements-build.txt
└── pyproject.toml          # configuração do Ruff
```

## Requisitos

- Windows 10/11 (o executável é gerado para Windows x64)
- Python **3.11** ou 3.12 para rodar a partir do código-fonte
- Webcam
- Para o executável: nada além do Windows (as dependências vão embutidas)

## Instalação (código-fonte)

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Na primeira execução, o modelo `models/face_landmarker.task` (≈3,6 MB) é
baixado automaticamente.

## Executando

```bash
python main.py
```

Opções úteis:

```bash
python main.py --sem-fullscreen   # abre em janela
python main.py --check            # valida instalação/modelo e encerra
python main.py --check-camera     # testa a webcam em cada backend e encerra
python main.py --config outro.yaml
```

## Executável (.exe)

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

O script cria/atualiza o `.venv`, instala as dependências, garante o
modelo, roda os testes e gera:

```
dist\EyeTrackingAssistivo.exe
```

É um executável **onefile** (um único arquivo, ≈97 MB), sem console.
Logs e perfis são gravados **ao lado do .exe**, em `logs\` e `perfis\`.

Para validar o executável sem webcam:

```powershell
.\dist\EyeTrackingAssistivo.exe --check
Get-Content .\dist\diagnostico.txt
```

Para personalizar a configuração sem reconstruir o exe, crie
`dist\config\settings.yaml`; esse arquivo tem prioridade sobre o
empacotado.

## Preview do novo design (tema claro)

A pasta `preview_novo_design/` é um **sandbox visual isolado**: recria as
telas do novo design com Pillow para revisão, sem substituir a interface
de produção e sem entrar no `.exe`. Ela não altera tempos, seleção,
calibração nem persistência.

```bash
pip install -r requirements-preview.txt
python -m preview_novo_design --render-only   # gera os PNGs
python -m preview_novo_design                 # abre a navegação interativa
```

As telas ficam em `preview_novo_design/saidas/` (1280x720, 1920x1080 e
uma folha de contato). Detalhes, tokens e decisões estão em
`preview_novo_design/README.md`.

## Controles

| Tecla | Ação |
|---|---|
| `I` | Abrir a prancha de comunicação (modo principal) |
| `C` | Calibrar a prancha (4 blocos) |
| `S` | Abrir o modo SIM / NÃO (legado) |
| `V` | Calibrar o modo SIM / NÃO (legado) |
| `P` | Selecionar perfil salvo |
| `N` | Criar novo perfil (na tela de perfis) |
| `M` | Voltar ao menu / cancelar calibração |
| `ESPAÇO` | Iniciar coleta durante a calibração |
| `ENTER` | Confirmar (novo perfil / tela de calibração concluída) |
| `ESC` | Voltar / cancelar (no menu, encerra o app) |
| `Q` | Sair |

> **Se o teclado não responder**, clique uma vez na janela do aplicativo e
> pressione a tecla de novo. Em tela cheia o Windows pode abrir a janela sem
> entregar o foco do teclado; o app tenta recuperar o foco sozinho nos
> primeiros 20 segundos, mas um clique garante o funcionamento.

## Prancha de comunicação

A prancha ocupa a tela inteira em uma grade 2x2:

```
+----------------+----------------+
|       OI       |     COMER      |
+----------------+----------------+
|     BEBER      |    BANHEIRO    |
+----------------+----------------+
```

Cada cartão tem cor própria, pictograma desenhado com OpenCV (sem
imagens externas) e rótulo grande. O cartão em foco ganha borda amarela
e uma barra de progresso; ao confirmar, a borda fica verde e o topo
mostra **"VOCÊ ESCOLHEU: ..."**.

### Calibração da prancha

Cada um dos 4 blocos é calibrado em uma fase: o usuário olha fixo para o
cartão destacado por **3 segundos**, com no mínimo **30 amostras
válidas** (`calibracao.duracao_ms` / `calibracao.min_amostras`). Para
cada bloco são guardados a mediana de `(ratio_x, ratio_y)` dos dois
olhos. A calibração fica em:

```
perfis/<nome>.prancha.json
```

- Se dois cartões ficarem a menos de `prancha.distancia_minima_boa`
  (padrão `0.02`) um do outro, a calibração é **fraca**: não é salva e a
  prancha fica bloqueada até recalibrar.
- No uso, o bloco escolhido é o **vizinho mais próximo** do ponto de
  olhar calibrado. Se o olhar estiver a mais de `prancha.raio_max`
  (padrão `0.55`) de todos os cartões, **nenhum** é selecionado -- isso
  evita escolhas quando o usuário olha para o centro da tela ou para
  fora da prancha.

### Seleção na prancha

A mesma lógica de dwell/piscada do modo SIM/NÃO é usada:

- **Dwell**: 700 ms de foco contínuo (`deteccao.dwell_ms`).
- **Tolerância**: perdas de foco de até 180 ms não zeram o progresso.
- **Piscada**: 350 ms de olho fechado, com pelo menos 150 ms de foco
  prévio.
- **Feedback**: bipe curto ao confirmar; bipe grave em erro.
- A seleção confirmada fica na tela por 1,5 s e é registrada no log.

## Calibração SIM / NÃO (legado)

Cada fase (SIM e NÃO) coleta por **3 segundos** e exige no mínimo
**30 amostras válidas**:

- frames com olhos fechados (EAR abaixo do limiar) são descartados;
- frames com a cabeça virada além de `calibracao.max_yaw_graus` são
  descartados;
- a referência final é a **mediana** das amostras (resistente a picos);
- se a separação entre SIM e NÃO ficar abaixo de
  `calibracao.diferenca_minima`, a calibração é considerada **fraca**:
  o perfil **não é salvo** e o modo ativo fica bloqueado até recalibrar.

A classificação no modo ativo usa a **média dos dois olhos**, exatamente
a mesma grandeza calibrada -- isso evita o problema de calibrar com a
média e classificar cada olho isoladamente.

## Seleção no modo SIM / NÃO

- **Dwell**: 700 ms de foco contínuo (`deteccao.dwell_ms`).
- **Tolerância**: perdas de foco de até 180 ms não zeram o progresso
  (`deteccao.tolerancia_perda_ms`) -- um frame de ruído não reinicia tudo.
- **Piscada**: 350 ms de olho fechado, com pelo menos 150 ms de foco
  prévio (`deteccao.piscada.*`).
- **Pausa**: olhos fechados pausam o dwell em vez de acumular tempo.
- **Feedback**: bipe curto ao confirmar; bipe grave em erro.
- A seleção confirmada fica na tela por 1,5 s e é registrada no log.

## Configuração principal (`config/settings.yaml`)

| Chave | Padrão | Efeito |
|---|---|---|
| `deteccao.dwell_ms` | 700 | tempo de foco para confirmar |
| `deteccao.tolerancia_perda_ms` | 180 | perda de foco tolerada |
| `deteccao.alpha_ema` | 0.35 | suavização (0=lento, 1=sem) |
| `deteccao.piscada.habilitada` | true | confirmação por piscada |
| `deteccao.piscada.piscada_ms` | 350 | tempo de olho fechado |
| `calibracao.duracao_ms` | 3000 | duração de cada fase |
| `calibracao.min_amostras` | 30 | amostras válidas mínimas |
| `calibracao.max_yaw_graus` | 25 | cabeça virada demais é ignorada |
| `calibracao.diferenca_minima` | 0.03 | separação mínima SIM/NAO |
| `prancha.distancia_minima_boa` | 0.02 | separação mínima entre cartões |
| `prancha.raio_max` | 0.55 | distância máxima até o cartão mais próximo |
| `camera.*` | 0 / 1280x720 / 30 fps | câmera |
| `camera.backend` | `auto` | `auto` (MSMF → DirectShow → padrão), `msmf`, `dshow` ou `any` |
| `camera.timeout_inicial_ms` | 6000 | espera máxima pelo 1º frame ao abrir |
| `feedback.som` | true | bipes de confirmação |
| `janela.fullscreen` | true | tela cheia |

Um YAML incompleto é mesclado com os padrões; valores inválidos fazem o
sistema voltar para a configuração padrão e registrar o erro no log.

## Rodando os testes

```bash
pytest
ruff check .
```

Cobertura atual (**134 testes**):

- `gaze_engine`: ratio horizontal/vertical, EMA, EAR, yaw;
- `board`: os 4 blocos, geometria da grade 2x2, vizinho mais próximo,
  raio máximo e distância mínima entre pontos;
- `board_calibration`: salvar/carregar, qualidade, validade, path
  traversal, JSON corrompido e coordenadas inválidas;
- `board_renderer`: fumaça das telas de uso, confirmação, calibração e
  conclusão (sem câmera);
- `selection`: dwell por tempo, tolerância a perdas, troca de opção,
  pausa com olhos fechados, piscada, confirmação e reset;
- `calibration`: salvar/carregar, qualidade, validade, path traversal,
  JSON corrompido/chaves faltando/valores fora da faixa;
- `config`: merge parcial, fallback e validação;
- `model_loader`: download atômico, checksum e limpeza de `.part`;
- `camera`: seleção de backend, abertura só após o 1º frame, liberação
  antes de reabrir, modo tolerante e diagnóstico;
- `state_machine`: regras de calibração válida/fraca, prancha válida,
  avisos e resets.

## O que foi corrigido nesta versão

**Bugs / robustez**

- Timestamp do MediaPipe agora é um contador monotônico (o
  `time.time()` do Windows tem granularidade de ~15 ms e podia repetir
  o mesmo milissegundo, derrubando a detecção).
- Classificação usa a média dos olhos, igual à calibração.
- Dwell por tempo com tolerância a perdas, em vez de contagem de frames.
- Olhos fechados pausam o dwell (não acumulam tempo).
- EMA e histórico são reiniciados entre as fases de calibração.
- Amostras de calibração com piscada ou cabeça virada são descartadas;
  a referência usa mediana.
- Calibração fraca não é salva e bloqueia o modo ativo.
- Perfil JSON é validado no carregamento (não gera mais `KeyError`).
- Config YAML parcial é mesclada/validada (não gera `KeyError`).
- Download do modelo é atômico (`.part` → valida → renomeia).
- Caminho do modelo/config funciona no `.exe` (PyInstaller `_MEIPASS`).
- Thread da câmera não gira em 100% de CPU se a câmera cair e tenta
  reconectar.
- Câmera: o dispositivo só é considerado aberto depois de entregar o
  primeiro frame; tenta MSMF/DirectShow/auto; libera a captura antiga
  antes de reabrir; reconexão com espera progressiva (antes, reabrir a
  cada segundo impedia a câmera de aquecer).
- Tela de "SEM SINAL DA CAMERA" com instruções, em vez de janela preta
  que parece travada, e log sem spam (a cada 10 s).
- Novo diagnóstico `--check-camera` para isolar problemas de webcam.
- **Prancha de comunicação** com 4 blocos (OI, COMER, BEBER, BANHEIRO)
  em grade 2x2, calibração em 4 fases por `(ratio_x, ratio_y)` e
  classificação por vizinho mais próximo com raio máximo. O modo
  SIM/NÃO foi preservado como legado.
- Calibração da prancha é gravada em `perfis/<nome>.prancha.json`, sem
  conflitar com a calibração SIM/NÃO (`perfis/<nome>.json`).
- Novo perfil pode ser criado pela interface (antes só existia no menu).
- Avisos e bipes de confirmação/erro; erros fatais aparecem em caixa
  nativa quando não há console.
- O app detecta o fechamento da janela e encerra a sessão.
- **Teclado em tela cheia**: a janela do OpenCV podia abrir sem foco, e
  aí nenhuma tecla era recebida. O app agora solicita o foco ao Windows
  e tenta recuperá-lo até a primeira tecla (20 s), além de orientar um
  clique na janela. Atalhos aceitam maiúsculas e minúsculas, e `ESC`
  volta/cancela em todas as telas (no menu, encerra).

**Higiene**

- `.gitignore` adicionado; `__pycache__`/`.pyc` removidos do índice.
- `perfis/padrao.json` (calibração fraca usada como exemplo) removido.
- Configuração de lint (`pyproject.toml`) e versões com limites.
- Título/versão padronizados em V2.1.

## Limitações e próximos passos

- A navegação de menu ainda usa teclado; o próximo salto é permitir
  seleção por olhar também nas telas de menu/perfis.
- A prancha tem 4 blocos fixos nesta versão. A lista em `core/board.py`
  é um dado: acrescentar itens não exige mudar a lógica de seleção, mas
  a grade 2x2 do renderizador está preparada para 4 cartões.
- Não há síntese de voz (TTS) nem acúmulo de frases; a seleção é
  registrada no log e exibida por 1,5 s.
- O executável onefile extrai as dependências a cada abertura; o
  primeiro start pode demorar alguns segundos e alguns antivírus podem
  pedir confirmação.
- A compensação de pose por yaw é conservadora e deve ser validada com
  usuários reais; `max_yaw_graus` permite ignorar poses extremas.
- O `ratio_y` é usado na prancha, mas a calibração vertical ainda é
  sensível à posição da câmera; reenquadre o rosto antes de recalibrar.

## Solução de problemas

- **"Não foi possível abrir a câmera"**: feche outros apps que usam a
  webcam (Teams, Zoom, OBS, navegador, app Câmera) e confira
  `camera.indice`.
- **A câmera abre mas a tela fica preta / "SEM SINAL DA CAMERA"**: rode
  o diagnóstico dedicado:

  ```bash
  python main.py --check-camera        # grava diagnostico_camera.txt
  ```

  Ele testa MSMF, DirectShow e o backend padrão e diz exatamente onde a
  captura para. Se nenhum entregar frames:

  1. desconecte e reconecte a webcam (ou troque a porta USB);
  2. reinicie o computador — um driver travado só se recupera assim;
  3. confirme em Configurações > Privacidade > Câmera que "Acesso à
     câmera" e "Aplicativos da área de trabalho" estão ativados;
  4. abra o app Câmera do Windows e confirme que a imagem aparece.

  Se funcionar em outros programas mas não no sistema, force o backend
  em `config/settings.yaml`:

  ```yaml
  camera:
    backend: "dshow"   # ou "msmf"
  ```
- **Calibração sempre fraca**: olhe mais para os cantos da tela durante
  a coleta, mantenha a cabeça ereta e o rosto enquadrado; reduza
  `calibracao.diferenca_minima` apenas se necessário.
- **Prancha sempre fraca**: os 4 cartões precisam gerar pontos de olhar
  bem diferentes. Repita olhando firme para cada cartão destacado, sem
  mover a cabeça; se necessário, reduza `prancha.distancia_minima_boa`.
- **Prancha escolhe o cartão errado**: refaça a calibração com o rosto
  na mesma posição em que você usa o sistema (a calibração vertical é
  sensível à altura da câmera). Ajuste `prancha.raio_max` para exigir
  mais precisão.
- **Modo ativo não inicia**: a mensagem na tela indica calibração
  ausente/fraca; pressione `C` (prancha) ou `V` (SIM/NÃO) e refaça.
- **Executável não abre**: rode com `--check` e veja
  `diagnostico.txt`; o log da sessão fica em `logs\`.
