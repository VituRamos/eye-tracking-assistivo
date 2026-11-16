# Eye-Tracking Assistivo V2.2.5

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
│   ├── design.py           # tokens, tipografia, Lona Pillow, SVG e componentes
│   ├── assets/pictogramas/  # SVGs originais de OI, COMER, BEBER e BANHEIRO
│   ├── renderer_cv2.py     # menu, perfis, SIM/NÃO, avisos e telas auxiliares
│   └── board_renderer.py   # prancha: cartões, pictogramas e calibração
├── prototipo_tauri/        # interface React/Tauri + motor empacotado
├── tests/                  # 269 testes (puros, sem câmera/MediaPipe)
├── models/                 # modelo .task versionado (478 pontos, roda offline)
├── perfis/                 # calibrações salvas por usuário (runtime)
├── logs/                   # logs de sessão (runtime)
├── main.py                 # ponto de entrada -- só orquestra os módulos
├── EyeTrackingAssistivo.spec
├── build_exe.ps1
├── requirements.txt
├── requirements-dev.txt
├── requirements-preview.txt # dependências extras do sandbox visual
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
git clone https://github.com/VituRamos/eye-tracking-assistivo.git
cd eye-tracking-assistivo
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
```

O clone já traz o que o aplicativo precisa em tempo de execução: o modelo
`models/face_landmarker.task` (≈3,6 MB, 478 pontos com íris), a configuração
padrão e os pictogramas. Ele roda **sem internet**; se o modelo faltar ou o
checksum divergir, é baixado da URL oficial e verificado pelo SHA-256 (ver
`models/README.md`).

Para preparar tudo de uma vez no Windows (Python + interface):

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

A interface React/Tauri exige Node 20+ (e Rust 1.80+ apenas para o build
desktop):

```powershell
cd prototipo_tauri
npm install
npm run dev        # navegador, com backend de demonstração
npm run tauri dev  # app desktop com o motor Python real
```

Para gerar o instalador Tauri, rode `npm run sidecar` antes de
`npm run tauri build` (detalhes em `prototipo_tauri/README.md`).

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

## Novo design (tema claro)

A interface de produção usa o novo design aprovado no preview:

- fundo claro (`#F4F1EA`), superfícies brancas e tipografia Segoe UI;
- barra lateral com Prancha, Perfis, Calibração, Modo Cuidador e
  Configurações;
- cartões pastel para **OI**, **COMER**, **BEBER** e **BANHEIRO**, com
  pictogramas vetoriais em `ui/assets/pictogramas/`;
- foco em traço escuro e confirmação em verde, com banner de escolha;
- telas novas de **Modo Cuidador** e **Configurações**, abertas com
  `F2`/`G` e `F3`/`O`. No aplicativo Tauri, Configurações é um editor
  completo; a tela `C` abre a escolha entre calibrar a prancha ou o
  SIM / NÃO.

As telas são desenhadas com Pillow em uma `Lona` e copiadas para o frame
do OpenCV (`ui/design.py`). Tempos, seleção, calibração e persistência
permanecem exatamente os mesmos da V2.1.

A interface é renderizada **nativamente em 1920x1080**: textos, cartões e
pictogramas são desenhados já na resolução final, sem upscale do frame. A
captura e a detecção continuam em 1280x720 (`frame_proc`), o que mantém o
custo do MediaPipe baixo; só a composição visual usa o canvas 1080p
(`LARGURA_TELA`/`ALTURA_TELA` em `main.py`). Em monitores menores o
fullscreen reduz a imagem proporcionalmente, sem perder o layout.

## Controles

| Tecla | Ação |
|---|---|
| `I` | Abrir a prancha de comunicação (modo principal) |
| `C` | Abrir a escolha da calibração (prancha ou SIM / NÃO) |
| `1` / `2` | Escolher a calibração na tela de escolha |
| `S` | Abrir o modo SIM / NÃO (legado) |
| `V` | Calibrar o modo SIM / NÃO (legado) |
| `P` | Selecionar perfil salvo |
| `N` | Criar novo perfil (na tela de perfis) |
| `F2` ou `G` | Abrir o Modo Cuidador |
| `F3` ou `O` | Abrir Configurações (editor completo no app Tauri) |
| `M` | Voltar ao menu / cancelar calibração |
| `ESC` | Voltar ao menu (cuidador/configurações) ou cancelar perfil |
| `ESPAÇO` | Iniciar coleta durante a calibração |
| `ENTER` | Confirmar (novo perfil / telas de calibração concluída) |
| `Q` | Sair |

## Prancha de comunicação

A prancha ocupa a tela inteira em uma grade 2x2:

```
+----------------+----------------+
|       OI       |     COMER      |
+----------------+----------------+
|     BEBER      |    BANHEIRO    |
+----------------+----------------+
```

Cada cartão tem cor pastel própria, pictograma vetorial (SVG em
`ui/assets/pictogramas/`) e rótulo grande. O cartão em foco ganha um anel
escuro e uma barra de progresso; ao confirmar, o anel fica verde, surge o
selo **Confirmado** e o topo mostra a frase **"Você escolheu: ..."**.

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
- frames com a cabeça fora dos limites de yaw, pitch ou roll
  (`calibracao.max_yaw_graus`, `max_pitch_graus`, `max_roll_graus`)
  são descartados;
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
- **Piscada**: 120 ms de olho fechado, com pelo menos 150 ms de foco
  prévio (`deteccao.piscada.*`). O alvo focado é mantido enquanto os
  olhos estão fechados, para a piscada confirmar em vez de cancelar.
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
| `deteccao.piscada.piscada_ms` | 120 | tempo de olho fechado |
| `deteccao.divergencia_max` | 0.25 | diferença máxima entre os olhos; acima disso o quadro é ignorado |
| `deteccao.sem_rosto_ms` | 2000 | tempo contínuo sem rosto antes de pedir para reposicionar |
| `deteccao.confianca_minima` | 0.5 | rigor do detector de rosto (0..1) |
| `deteccao.compensar_yaw` | false | compensação experimental da cabeça (exige recalibrar a prancha) |
| `deteccao.yaw_sensibilidade` | 0.004 | deslocamento do olhar por grau, se a compensação estiver ligada |
| `calibracao.duracao_ms` | 3000 | duração de cada fase |
| `calibracao.min_amostras` | 30 | amostras válidas mínimas |
| `calibracao.max_yaw_graus` | 25 | cabeça virada demais é ignorada |
| `calibracao.max_pitch_graus` | 25 | cabeça muito para cima/baixo é ignorada |
| `calibracao.max_roll_graus` | 30 | inclinação lateral excessiva é ignorada |
| `calibracao.diferenca_minima` | 0.03 | separação mínima SIM/NAO |
| `prancha.distancia_minima_boa` | 0.02 | separação mínima entre cartões |
| `prancha.raio_max` | 0.55 | mantido por compatibilidade; a seleção usa o quadrante calibrado |
| `camera.*` | 0 / 1280x720 / 30 fps | câmera |
| `camera.backend` | `auto` | `auto` (MSMF → DirectShow → padrão), `msmf`, `dshow` ou `any` |
| `camera.timeout_inicial_ms` | 6000 | espera máxima pelo 1º frame ao abrir |
| `feedback.som` | true | bipes de confirmação |
| `janela.fullscreen` | true | inicia em tela cheia (`F11` alterna) |
| `janela.resolucao` | `1920x1080` | resolução da janela: `1280x720` ou `1920x1080` |

Um YAML incompleto é mesclado com os padrões; valores inválidos fazem o
sistema voltar para a configuração padrão e registrar o erro no log.

No aplicativo Tauri, todas essas opções podem ser alteradas em
**Configurações** (`F3`) e são gravadas no `settings.yaml` do usuário
(`%LOCALAPPDATA%\com.eyetracking.prancha`) de forma atômica. Mudanças de
detecção, piscada e som valem na hora; mudanças de câmera pedem reinício.
O aplicativo inicia em **tela cheia** por padrão; ao desligar a tela
cheia, a resolução escolhida é aplicada (reduzida proporcionalmente
quando não cabe na tela).

## Rodando os testes

```bash
pytest
ruff check .
```

Cobertura atual (**228 testes**):

- `design`: Lona, transparência, leitura/rasterização dos 4 SVGs e
  composição de sobreposições;
- `renderer_cv2`: menu, perfis, novo perfil, SIM/NÃO, calibração,
  gráfico, avisos, modo cuidador e configurações (fumaça, sem câmera),
  incluindo as telas-chave em 1920x1080;
- `gaze_engine`: ratio horizontal/vertical, EMA, EAR, yaw, distância do
  rosto normalizada e classificação com histerese;
- `board`: os 4 blocos, geometria da grade 2x2, vizinho mais próximo,
  raio máximo, distância mínima entre pontos e translação de referências;
- `board_calibration`: salvar/carregar, qualidade, validade, path
  traversal, JSON corrompido e coordenadas inválidas;
- `board_renderer`: fumaça das telas de uso, confirmação, calibração e
  conclusão (sem câmera);
- `selection`: dwell por tempo, tolerância a perdas, troca de opção,
  pausa com olhos fechados, piscada, confirmação e reset;
- `calibration`: salvar/carregar, qualidade, validade, path traversal,
  JSON corrompido/chaves faltando/valores fora da faixa;
- `config`: merge parcial, fallback, validação e gravação atômica;
- `ponte_config`: tradução dos ajustes da interface para o YAML;
- `model_loader`: download atômico, checksum e limpeza de `.part`;
- `camera`: seleção de backend, abertura só após o 1º frame, liberação
  antes de reabrir, modo tolerante e diagnóstico;
- `state_machine`: regras de calibração válida/fraca, prancha válida,
  avisos e resets;
- `motor_recentralizacao`: comando de recentralização, persistência,
  desfazer único por sessão e aviso de distância no snapshot.

## Novo na versão 2.2

- **Configurações completas pela interface**: seis categorias (detecção,
  piscada, calibração, prancha, câmera e sistema), com restaurar padrões,
  descartar e salvar de forma atômica.
- **Resolução da tela configurável**: 1280x720 ou 1920x1080; se não
  couber, a janela reduz proporcionalmente e centraliza.
- **Escolha de calibração**: a tecla `C` abre uma tela para escolher entre
  calibrar a prancha (4 cartões) e o SIM / NÃO.
- **Ajustes visuais**: fundo claro sem barras pretas nas laterais, botão
  principal renomeado para "Prancha" e correção do card "O que você pode
  fazer" no Modo Cuidador.
- O selo "LOCAL · OFFLINE · DADOS NO COMPUTADOR" foi removido do menu.

## Novo na versão 2.2.5

- **Status estável**: o indicador de rosto não alterna mais entre "Rosto
  detectado" e "Sem rosto" quando o detector perde um quadro. O motor
  repete o último estado confiável por 700 ms; a seleção continua exigindo
  o rosto no quadro atual.
- **Piscadas não piscam o selo**: "Olhos fechados" só aparece quando os
  olhos ficam fechados de verdade (350 ms ou mais).
- **Cursor do olhar estável**: o ponto mantém a última posição por 500 ms
  com transição suave, sem saltar para o centro nem desaparecer.
- **Cartão mais limpo**: removidos o selo "Confirmado" e a barra de
  progresso do cartão; o anel de foco e o aviso superior continuam.
- **Faixa "Você escolheu" maior**, sem encostar na grade dos cartões.
- **Modo Cuidador revisado**: o painel do olhar perdeu a grade numérica
  que sobrepunha textos e agora mostra o cartão em foco, o estado da
  leitura e uma orientação curta; as ações ganharam título e descrição.

## Novo na versão 2.2.4

- **Aviso de distância do rosto**: o aplicativo estima se o rosto está
  longe ou perto demais da câmera. O aviso é apenas informativo -- não
  bloqueia seleção, tempo de olhar nem calibração -- e usa histerese para
  não piscar. As faixas e os tempos ficam em Configurações > Distância.
- **Recentralização de 1 ponto**: no Modo Cuidador, a tecla `R` abre um
  assistente para corrigir o desvio do olhar usando um único cartão
  conhecido. Há prévia do deslocamento, aplicação e a opção `U` para
  desfazer uma vez por sessão.
- **Mapa do olhar ampliado**: o painel do Modo Cuidador agora também
  mostra o estado da distância do rosto.
- **Ponto do olhar na prancha**: uma bolinha mostra onde a pessoa está
  olhando e um anel se fecha até a confirmação por tempo. Na calibração
  o anel acompanha a coleta; agora o ponto também aparece na tela de
  preparação, quando a detecção passou a rodar antes do início da coleta.
- **Detecção mais estável**: aviso de rosto por tempo real
  (`deteccao.sem_rosto_ms`), limites de pitch e roll além do yaw,
  timestamp real no MediaPipe, confiança do detector configurável e
  proteção contra modelo sem pontos de íris.
- **Compensação de cabeça opcional**: `deteccao.compensar_yaw` vem
  desligado por padrão; quem ativar deve recalibrar a prancha com a opção
  ligada.

## Novo na versão 2.2.3

- **Mapa do olhar no Modo Cuidador**: painel ao vivo com os cartões
  calibrados, a trilha recente e a posição atual do olhar, além do cartão
  mais próximo, da distância e da divergência entre os olhos.
- **Divergência entre os olhos como filtro**: quando os dois olhos apontam
  para lugares muito diferentes, o quadro é tratado como inválido e não
  move o dwell nem entra na calibração. O limite fica em
  `deteccao.divergencia_max` (padrão 0.25) e pode ser aumentado em
  Configurações > Detecção para quem tem estrabismo.
- A detecção continua ativa no Modo Cuidador para o mapa funcionar ao
  vivo, sem habilitar seleção nessa tela.

## Novo na versão 2.2.2

- **Pictograma acima da palavra**: os cartões da prancha e das telas de
  calibração agora mostram o ícone centralizado sobre o rótulo, no mesmo
  arranjo dos cartões OI / COMER / BEBER / BANHEIRO aprovados.
- **Tela "Sair do app?"**: o botão "Sair" e a tecla `Q` abrem uma
  confirmação com "Continuar usando" e "Sair". O perfil e a calibração
  continuam salvos neste computador. `Esc` ou `N` cancelam; o olhar
  nunca aciona essa tela.
- **Aviso "Olhe para a tela" estável**: o aviso de cabeça fora de posição
  só aparece após 450 ms contínuos e some após 350 ms contínuos de pose
  boa, eliminando o pisca-pisca quando o ângulo oscila perto do limite.
- **Modo escuro**: novo tema escuro em Configurações > Sistema, com
  prévia imediata e preferência salva em `aparencia.tema` no
  `settings.yaml`. A escolha é lembrada na próxima abertura.

## Novo na versão 2.2.1

- **Novos ícones no menu**: a prancha usa o quadrado dividido em quatro
  partes e o SIM / NÃO usa o quadrado com linha vertical central.
- **Tela cheia por padrão**: o aplicativo abre ocupando a tela inteira;
  o comportamento pode ser alterado em Configurações > Sistema e `F11`
  continua alternando a qualquer momento.
- **Menu sem folga lateral**: os itens do menu encostam na borda esquerda
  da tela, alinhados com o palco do aplicativo.

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
- A compensação de pose por yaw é experimental e fica **desligada por
  padrão** (`deteccao.compensar_yaw: false`). Se ativada, recalibre a
  prancha com a opção ligada; `max_yaw_graus`, `max_pitch_graus` e
  `max_roll_graus` descartam poses extremas.
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
