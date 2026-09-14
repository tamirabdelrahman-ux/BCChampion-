# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('templates','templates'),('static','static')]

a = Analysis(['desktop_launcher.py'], pathex=[], binaries=[], datas=datas, hiddenimports=['openpyxl','xlrd','matplotlib.backends.backend_agg'], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='BCChampion', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False)
