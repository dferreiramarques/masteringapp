# -*- mode: python ; coding: utf-8 -*-
# Build multiplataforma (Windows + Linux): pyinstaller MasteringApp.spec
# As partes Windows-only (WebView2/.NET, recursos .ico/.version) ficam
# condicionais — em Linux o desktop.py abre o browser em vez do webview.
import sys
from PyInstaller.utils.hooks import collect_all

datas = [('static', 'static')]
binaries = []
hiddenimports = ['multipart']
excludes = []
exe_kwargs = {}
if sys.platform == 'win32':
    # pywebview via WebView2 (janela nativa Windows) precisa do bridge .NET
    hiddenimports += ['webview.platforms.winforms']
    tmp_ret = collect_all('pythonnet')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    tmp_ret = collect_all('clr_loader')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
    exe_kwargs = dict(version='version.txt', icon=['static/app_icon.ico'])
else:
    # Linux: sem janela nativa — nao embutir o webview (GTK e fragil no freeze)
    excludes += ['webview']
tmp_ret = collect_all('pedalboard')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MasteringApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    **exe_kwargs,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MasteringApp',
)
