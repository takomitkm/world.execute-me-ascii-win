"""Windows console input. Keys are translated to the escape sequences the player already parses."""
import msvcrt, os, time

PREFIX = {'\x00', '\xe0'}
ARROW = {'H': '\x1b[A', 'P': '\x1b[B', 'K': '\x1b[D', 'M': '\x1b[C'}


def powershell():
    from shutil import which
    root = os.environ.get('SystemRoot', r'C:\Windows')
    fixed = os.path.join(root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    if os.path.exists(fixed):
        return fixed
    return which('powershell.exe') or which('pwsh.exe') or 'powershell.exe'


def _pair(limit=0.03):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if msvcrt.kbhit():
            return msvcrt.getwch()
    return ''


def poll(timeout):
    end = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < end:
        if msvcrt.kbhit():
            return True
        time.sleep(0.002)
    return bool(msvcrt.kbhit())


def read_keys():
    out = ''
    while msvcrt.kbhit():
        ch = msvcrt.getwch()
        if ch in PREFIX:
            nxt = _pair()
            if nxt:
                out += ARROW.get(nxt, '')
        else:
            out += ch
    return out
