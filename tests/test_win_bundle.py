"""Windows bundle checks: packaged resources, execution from a clean directory, key dispatch."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import types
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'dist/world-execute-mv-win.pyz'


@unittest.skipUnless(BUNDLE.is_file(), 'run tools/build_bundle_win.py first')
class BundleTests(unittest.TestCase):
    def test_embedded_resources_match_source(self):
        sources = {'__main__.py': 'tools/win_bundle_main.py'}
        with zipfile.ZipFile(BUNDLE) as archive:
            manifest = json.loads(archive.read('bundle-manifest.json'))
            self.assertIn('media/song.mp3', manifest['files'])
            self.assertIn('__main__.py', manifest['files'])
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                self.assertEqual(archive.read(name), (ROOT / sources.get(name, name)).read_bytes())
            config = json.loads(archive.read('config.json'))
            self.assertEqual(config['audio'], 'media/song.mp3')
            self.assertFalse(any(name.lower().endswith(('.mp4', '.png', '.jpg')) for name in archive.namelist()))

    def test_runs_from_an_empty_directory_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            work = base / 'unrelated working directory'; work.mkdir()
            scratch = base / 'scratch'; scratch.mkdir()
            env = dict(os.environ, TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
            for t, expected in [(67.3, 'If I can make you happy'), (124.2, 'Then maybe'),
                                (159.85, 'TROIS'), (183.2, 'Question me')]:
                result = subprocess.run([sys.executable, str(BUNDLE), '--snapshot', str(t),
                                         '--plain', '--width', '125', '--height', '45'],
                                        cwd=work, env=env, capture_output=True, text=True,
                                        encoding='utf-8', errors='replace', check=True)
                self.assertIn(expected, result.stdout)
                self.assertEqual(list(work.iterdir()), [])
                self.assertEqual(list(scratch.iterdir()), [])

    def test_corrupt_resource_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / 'corrupt.pyz'
            with zipfile.ZipFile(BUNDLE) as original, zipfile.ZipFile(bad, 'w') as changed:
                for name in original.namelist():
                    data = original.read(name)
                    changed.writestr(name, b'{}' if name == 'config.json' else data)
            result = subprocess.run([sys.executable, str(bad), '--snapshot', '67.3', '--plain'],
                                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                                    env=dict(os.environ, PYTHONIOENCODING='utf-8'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('资源校验失败', result.stderr)

    def test_timeline_renders_at_every_size(self):
        player = load_player()
        film = player.Film()
        duration = film.config['duration']
        for i in range(0, int(duration * 2)):
            for w, h in ((120, 40), (64, 24)):
                c = film.render(i / 2.0, w, h, False, 0.0, i % 40 == 0, i % 80 == 0)
                c.plain(); c.ansi()

    def test_scenes_use_glyphs_the_system_codepage_cannot_encode(self):
        # The player pins stdout to UTF-8 because these glyphs are not representable in cp936.
        player = load_player()
        film = player.Film()
        drawn = set()
        for i in range(int(film.config['duration'])):
            drawn.update(set(film.render(float(i), 120, 40).plain()))
        blocked = [ch for ch in sorted(drawn) if not ch.isspace() and ch.encode('gbk', 'ignore') == b'']
        self.assertTrue(blocked, 'expected at least one glyph cp936 cannot encode')
        for ch in blocked:
            self.assertTrue(0x2500 <= ord(ch) <= 0x26FF, 'unexpected non-box glyph %s' % hex(ord(ch)))

    def test_keys_reach_the_audio_clock(self):
        player = load_player()
        audio = FakeAudio()
        queue = [' ', 'h', 'H', '1', '3', '5', '\x1b[C', '\x1b[D', '+', '-', 'q']
        player.Audio = lambda path: audio
        player.wait_key = lambda delay: bool(queue)
        player.read_key_chars = lambda: (queue.pop(0) if queue else '')
        stdin = sys.stdin
        stdout = sys.stdout
        import io
        try:
            sys.stdin = types.SimpleNamespace(isatty=lambda: True, fileno=lambda: 0)
            sys.stdout = io.StringIO()
            player.run(types.SimpleNamespace(
                audio=None, start=0., autoplay=False, fps=24, paused=False, offset=None,
                snapshot=None, width=120, height=40, plain=True, report=None, stop_after=None),
                player.Film())
            frames = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = stdin, stdout
        commands = audio.commands
        seeks = [float(c.split()[1]) for c in commands if c.startswith('seek')]
        self.assertEqual(commands[1], 'play')
        self.assertAlmostEqual(seeks[1], 0.0)
        self.assertAlmostEqual(seeks[2], 110.9)
        self.assertAlmostEqual(seeks[3], 177.246)
        self.assertAlmostEqual(seeks[4], 182.246, places=1)
        self.assertAlmostEqual(seeks[5], 177.246, places=1)
        self.assertEqual([c for c in commands if c.startswith('volume')], ['volume 0.8', 'volume 0.75'])
        self.assertEqual(commands[-1], 'quit')
        self.assertTrue(frames.startswith('\x1b[?1049h'))
        self.assertIn('\x1b[?1049l', frames[-200:])
        self.assertIn('05 / LOVE', frames)

    @unittest.skipUnless(os.environ.get('WMV_ACCEPT_AUDIO') == '1',
                         'set WMV_ACCEPT_AUDIO=1 to run the audible audio-clock test')
    def test_audio_clock_tracks_wall_time(self):
        sys.path.insert(0, str(ROOT))
        import player
        audio = player.Audio(ROOT / 'media/song.mp3')
        try:
            audio.command('seek 158.7'); time.sleep(.2)
            self.assertAlmostEqual(audio.state['time'], 158.7, places=2)
            audio.command('play')
            before, wall = audio.state['time'], time.monotonic()
            time.sleep(3.0)
            self.assertAlmostEqual(audio.state['time'] - before, time.monotonic() - wall, delta=.1)
            self.assertTrue(audio.state['playing'])
            audio.command('pause'); held = audio.state['time']; time.sleep(1.0)
            self.assertAlmostEqual(audio.state['time'], held, delta=.1)
            self.assertFalse(audio.state['playing'])
        finally:
            audio.close()


class FakeAudio:
    def __init__(self, path=None):
        self.state = {'time': 0., 'duration': 211.906667, 'playing': False}
        self.last = time.monotonic(); self.error = ''; self.commands = []
        self.wall = time.monotonic()
        self.proc = types.SimpleNamespace(poll=lambda: None)

    def _advance(self):
        now = time.monotonic()
        if self.state['playing']:
            self.state['time'] += now - self.wall
        self.wall = now; self.last = now

    def command(self, s):
        self._advance(); self.commands.append(s)
        verb, _, arg = s.partition(' ')
        if verb == 'play': self.state['playing'] = True
        elif verb == 'pause': self.state['playing'] = False
        elif verb == 'seek': self.state['time'] = float(arg)

    def close(self):
        self.commands.append('quit')


def load_player():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import importlib
    if 'player' in sys.modules:
        return importlib.reload(sys.modules['player'])
    return importlib.import_module('player')


if __name__ == '__main__':
    unittest.main(verbosity=2)
