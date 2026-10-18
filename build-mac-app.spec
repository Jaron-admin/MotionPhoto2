# -*- mode: python ; coding: utf-8 -*-
# macOS 中文版「动态照片转换.app」的打包配置（PyInstaller）
# 用法：pyinstaller --noconfirm build-mac-app.spec
import os

datas = []
if os.path.isdir('exiftool_bundle'):
    # 内置 ExifTool（Perl 版），用户没装 Homebrew exiftool 时也能用
    datas.append(('exiftool_bundle', 'exiftool_bundle'))

a = Analysis(
    ['mac_gui.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=['motionphoto2', 'Muxer', 'utils', 'constants', 'SamsungTags', 'exiftool', 'lxml.etree'],
    excludes=['gooey', 'wx'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MotionPhoto2zh',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MotionPhoto2zh')
app = BUNDLE(
    coll,
    name='动态照片转换.app',
    icon=None,
    bundle_identifier='io.github.jaron-admin.motionphoto2-zh',
    info_plist={
        'CFBundleName': '动态照片转换',
        'CFBundleDisplayName': '动态照片转换',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,  # 跟随系统深色模式
        'LSMinimumSystemVersion': '11.0',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Folder',
                'CFBundleTypeRole': 'Viewer',
                'LSItemContentTypes': ['public.folder'],
                'LSHandlerRank': 'Alternate',
            }
        ],
    },
)
