# Modelo do MediaPipe

`face_landmarker.task` é o modelo oficial **MediaPipe Face Landmarker**
(float16), com **478 pontos** — os 468 do rosto mais os 4 pontos de íris de
cada olho (469–472 e 474–477). A prancha depende desses pontos de íris, por
isso o aplicativo recusa modelos mais antigos e avisa no log.

| Campo | Valor |
|---|---|
| Origem | `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` |
| Tamanho | 3.758.596 bytes (≈3,6 MB) |
| SHA-256 | `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff` |
| Pontos | 478 (com íris) |

## Por que o arquivo está no repositório

Assim o clone já roda **offline**, e o build do instalador (PyInstaller e
Tauri) não depende de download. O `Ponte.spec` e o `EyeTrackingAssistivo.spec`
copiam o arquivo para dentro do executável.

O aplicativo confere o `modelo.sha256_esperado` de `config/settings.yaml`
contra o arquivo local. Se ele faltar ou o checksum divergir, o modelo é
baixado de novo da URL oficial e validado antes de ser usado.

## Como trocar o modelo

1. Substitua `models/face_landmarker.task` pelo novo arquivo.
2. Atualize `modelo.sha256_esperado` em `config/settings.yaml` (e o padrão em
   `config/loader.py`) com o SHA-256 do arquivo novo.
3. Rode `python main.py --check` para validar.

Um modelo com menos de 478 landmarks não é aceito: os índices de íris
ficariam fora do vetor e a detecção do olhar não teria como medir o ratio.

A licença do modelo acompanha o projeto MediaPipe (Apache 2.0).
