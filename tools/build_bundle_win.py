"""Build a single-file Windows player containing the original music and scenes."""
import hashlib
import json
import zipapp
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('player.py', 'scenes.py', 'winkeys.py', 'audio-clock-win.ps1', 'config.json',
         'lyrics.json', 'spectrum.json', 'media/song.mp3')
BUNDLE = 'world-execute-mv-win.pyz'


def manifest_for(stage_files):
    return {'format': 1, 'platform': 'Windows 10+ / PowerShell 5.1',
            'architectures': ['any (C Python 3.9+)'],
            'files': {name: hashlib.sha256(data).hexdigest() for name, data in stage_files.items()}}


def build(output=None):
    if not (ROOT / 'media/song.mp3').is_file():
        raise SystemExit('请先将本地音频放入 media/song.mp3；音频不会提交到仓库。')
    out = Path(output) if output else ROOT / 'dist'
    out.mkdir(parents=True, exist_ok=True)
    stage = {name: (ROOT / name).read_bytes() for name in FILES}
    stage['__main__.py'] = (ROOT / 'tools/win_bundle_main.py').read_bytes()
    stage['bundle-manifest.json'] = (json.dumps(manifest_for(stage), indent=2) + '\n').encode()
    package = out / BUNDLE
    import tempfile
    with tempfile.TemporaryDirectory(prefix='winbundle-') as folder:
        staging = Path(folder)
        for name, data in stage.items():
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        zipapp.create_archive(staging, package, compressed=True)
    return package


def main():
    package = build()
    with zipfile.ZipFile(package.parent / 'world-execute-mv-windows.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in [(BUNDLE, package), ('README.md', ROOT / 'README.md'),
                           ('运行单文件.bat', ROOT / '运行单文件.bat')]:
            archive.write(path, 'world-execute-mv-windows/' + name)
    paths = [package, package.parent / 'world-execute-mv-windows.zip']
    (package.parent / 'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in paths), encoding='utf-8')
    print(json.dumps({'artifacts': [str(p) for p in paths], 'embedded_audio': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
