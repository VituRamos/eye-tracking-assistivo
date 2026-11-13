# -*- mode: python ; coding: utf-8 -*-
"""
Empacotamento do Eye-Tracking Assistivo em um unico .exe.

Gera dist/EyeTrackingAssistivo.exe contendo:
  * o codigo e as dependencias (OpenCV, NumPy, MediaPipe, PyYAML);
  * config/settings.yaml;
  * models/face_landmarker.task.

Logs e perfis sao gravados ao lado do .exe (ver core/paths.py).

Para gerar uma versao com console (diagnostico):
    $env:ET_CONSOLE=1; python -m PyInstaller --noconfirm --clean EyeTrackingAssistivo.spec
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

raiz = Path(SPECPATH)
modo_console = os.environ.get("ET_CONSOLE", "0") == "1"

mp_datas, mp_binaries, mp_hiddenimports = collect_all("mediapipe")
# Os testes do MediaPipe puxam dependencias que nao usamos (mediapipe.framework,
# google.protobuf, six, ...). Nao vale empacota-los.
mp_hiddenimports = [m for m in mp_hiddenimports if ".test" not in m]

datas = mp_datas + [
    (str(raiz / "config" / "settings.yaml"), "config"),
    (str(raiz / "models" / "face_landmarker.task"), "models"),
    (str(raiz / "ui" / "assets"), "ui/assets"),
]

a = Analysis(
    [str(raiz / "main.py")],
    pathex=[str(raiz)],
    binaries=mp_binaries,
    datas=datas,
    hiddenimports=mp_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Nao usados pelo app; evita inflar o executavel.
        "pytest",
        "ruff",
        "_pytest",
        "jax",
        "jaxlib",
        "scipy",
        "pandas",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "notebook",
        "mediapipe.tasks.python.test",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

nome = "EyeTrackingAssistivoConsole" if modo_console else "EyeTrackingAssistivo"

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=nome,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=modo_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
