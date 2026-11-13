# Preview do novo design — tema claro

Esta pasta é um **sandbox visual**. Ela implementa as telas do novo
design em Pillow para revisão e comparação, sem substituir a interface
de produção.

Nada aqui é importado por `main.py`, `ui/board_renderer.py` ou
`ui/renderer_cv2.py`. O executável continua usando o renderizador atual
em OpenCV. A dependência de Pillow fica isolada em
`requirements-preview.txt` e não entra no `.exe`.

## Como rodar

```bash
pip install -r requirements-preview.txt

python -m preview_novo_design --render-only   # gera os PNGs
python -m preview_novo_design                 # gera e abre a janela
```

Na janela interativa:

| Tecla | Ação |
|---|---|
| `←` / `→` ou `A` / `D` | tela anterior / próxima |
| `1`–`9` | ir direto para uma tela |
| `B` | recolher/expandir o menu da tela inicial |
| `S` | salvar a tela atual em `saidas/interativo/` |
| `F` | alternar tela cheia |
| `Q` / `Esc` | sair |

## Saídas

```
preview_novo_design/
├── saidas/
│   ├── contato.png          # folha de contato com todas as telas
│   ├── 1280x720/            # 15 telas na base do projeto
│   └── 1920x1080/           # as mesmas telas em Full HD
├── tema.py                  # cores, tipografia, lona e supersampling
├── svg.py                   # leitor/rasterizador mínimo de SVG
├── icones.py                # aplica a tinta do tema nos pictogramas
├── assets/pictogramas/      # oi.svg, comer.svg, beber.svg, banheiro.svg
├── telas.py                 # composição de cada tela
├── renderizar.py            # CLI, PNGs e navegação interativa
└── __main__.py              # python -m preview_novo_design
```

As telas são desenhadas em unidades de **1280x720** e escaladas para o
tamanho pedido. O desenho interno usa supersampling 2x e é reduzido com
LANCZOS no final, para manter texto e curvas nítidos em 1920x1080.

## Telas incluídas

1. Início com menu lateral: Iniciar, Perfis, Calibração, Modo Cuidador,
   Configurações e Sair, além do resumo do perfil ativo.
2. Início com o menu lateral recolhido, mostrando apenas os ícones.
3. Início com aviso de calibração pendente.
4. Prancha em repouso.
5. Prancha com foco e progresso de dwell.
6. Prancha com confirmação verde (1,5 s).
7. Calibração — introdução.
8. Calibração — coleta de um bloco.
9. Calibração — concluída com qualidade boa.
10. Calibração — repetir por pontos muito próximos.
11. Pausa.
12. Câmera indisponível.
13. Rosto não detectado (a prancha continua).
14. Cabeça muito virada (a prancha continua).
15. Modo cuidador em tela separada.

## Tokens principais

| Uso | Cor |
|---|---|
| Fundo | `#F4F1EA` |
| Superfície | `#FFFFFF` |
| Borda | `#DBD8D0` |
| Texto | `#1B2430` |
| Apoio | `#4D6572` |
| Foco / ação principal | `#1B2430` |
| Cartões neutros na calibração | `#E7E4DC` |
| Confirmação | `#1F7A4A` |
| Atenção | `#9B4A08` |
| OI | `#F4C6D3` |
| COMER | `#F6D58C` |
| BEBER | `#A3DDD2` |
| BANHEIRO | `#B3CDF3` |

Tipografia: Segoe UI (fallback Arial), com escala grande e altura-x
generosa. Rótulos dos cartões em caixa alta curta; instruções em frase
normal.

## O que o preview **não** muda

- dwell de **700 ms** e tolerância de **180 ms**;
- piscada de **350 ms** e foco mínimo de **150 ms**;
- confirmação visível por **1,5 s**;
- calibração de **3 s** por bloco e mínimo de **30 amostras**;
- lógica de classificação por vizinho mais próximo;
- persistência em `perfis/*.prancha.json`;
- fluxo de produção, `main.py`, `ui/` e o `.exe`.

## Decisões de design aplicadas

- tema claro como padrão;
- tela inicial com menu lateral, status de câmera, resumo do perfil e
  ação principal “Iniciar” em destaque;
- menu lateral recolhível: 300 unidades expandido, 88 recolhido, com
  apenas os ícones e um botão de alternância no rodapé;
- modo cuidador em tela separada, acessível pelo item do menu e pela
  tecla F2 (sujeito a PIN);
- linguagem visual única para adultos e crianças;
- pictogramas a partir dos quatro SVGs fornecidos (`assets/pictogramas/`),
  rasterizados sem dependência externa e pintados com a tinta do tema;
- foco com anel duplo (grafite + halo branco) e barra de progresso
  dentro do cartão;
- confirmação com check, texto e cor — nunca só cor;
- avisos de câmera/rosto/cabeça em laranja, sem bloquear a prancha;
- nada de nuvem, login, telemetria ou internet.

O nome do produto continua em aberto. **“Prancha”** é apenas o título de
trabalho usado nas telas.

## Próximos passos sugeridos

1. Revisar as telas em `saidas/contato.png` e nos PNGs individuais.
2. Testar os pictogramas com usuários e cuidadores antes de fechar o
   estilo.
3. Escolher a tecla de acesso ao modo cuidador (F2 é a sugestão atual) e
   decidir se haverá PIN.
4. Só depois portar o visual aprovado para `ui/board_renderer.py` e
   `ui/renderer_cv2.py`, em um branch separado.
