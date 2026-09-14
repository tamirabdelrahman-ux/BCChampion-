# -*- mode: python ; coding: utf-8 -*-
a = Analysis(['stop_launcher.py'], pathex=[], binaries=[], datas=[], hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='BCChampion_Stop', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False)
