# -*- mode: python ; coding: utf-8 -*-
"""
Empacotamento do motor Python usado pelo aplicativo Tauri.

Gera ``dist/eye-core/`` (modo onedir) com ``eye-core.exe``, as
dependências (OpenCV, NumPy, MediaPipe, PyYAML), o settings.yaml e o
modelo do Face Landmarker. O Tauri copia essa pasta para os recursos do
instalador e inicia o executável como processo local.

O modo onedir é usado em vez de onefile porque:
  * o MediaPipe carrega bibliotecas nativas grandes;
  * o aplicativo inicia mais rápido (sem descompactar tudo a cada vez);
  * o antivírus costuma tratar melhor um executável sem autoextração.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

raiz = Path(SPECPATH)

mp_datas, mp_binaries, mp_hiddenimports = collect_all("mediapipe")
mp_hiddenimports = [m for m in mp_hiddenimports if ".test" not in m]

datas = mp_datas + [
    (str(raiz / "config" / "settings.yaml"), "config"),
    (str(raiz / "models" / "face_landmarker.task"), "models"),
]

a = Analysis(
    [str(raiz / "ponte.py")],
    pathex=[str(raiz)],
    binaries=mp_binaries,
    datas=datas,
    hiddenimports=mp_hiddenimports
    + [
        "cv2",
        "yaml",
        # O MediaPipe importa matplotlib ao carregar o módulo de visão,
        # mesmo que o motor não desenhe nada.
        "matplotlib",
        "matplotlib.pyplot",
        "matplotlib.backends.backend_agg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Não usados pelo motor; evita inflar a pasta de recursos.
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
        "tkinter",
        "matplotlib.backends._backend_tk",
        "matplotlib.backends.backend_tkagg",
        "matplotlib.tests",
        "matplotlib.testing",
        "mediapipe.tasks.python.test",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="eye-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="eye-core",
)
