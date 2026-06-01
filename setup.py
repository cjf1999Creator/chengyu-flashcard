"""
py2app 打包配置
用法:
    python setup.py py2app
"""
from setuptools import setup

APP = ['main.py']
DATA_FILES = [
    'parser.py',
    'storage.py',
    'app_icon.icns',
    'data',
]
OPTIONS = {
    'argv_emulation': False,
    'strip': False,
    'iconfile': 'app_icon.icns',
    'packages': ['tkinter'],
    'includes': ['tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.filedialog',
                 'json', 're', 'os', 'sys', 'random', 'calendar', 'datetime'],
    'excludes': ['numpy', 'pandas', 'matplotlib', 'scipy', 'PIL'],
    'plist': {
        'CFBundleName': '成语积累',
        'CFBundleDisplayName': '成语积累',
        'CFBundleIdentifier': 'com.chengyu.flashcard',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
    },
}

setup(
    name='成语积累',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
