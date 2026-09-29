"""29.09.2026: pyflakes bez zadnych ostrzezen — nowe (np. nieuzywana zmienna po zmianie logiki) sa od razu widoczne."""
import glob
import os

import pytest

pyflakes_api = pytest.importorskip('pyflakes.api')
from pyflakes.reporter import Reporter  # noqa: E402

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _Zbieraj(Reporter):
    def __init__(self):
        self.bledy = []

    def unexpectedError(self, plik, msg): self.bledy.append(f'{plik}: {msg}')
    def syntaxError(self, plik, msg, *a): self.bledy.append(f'{plik}: {msg}')
    def flake(self, m): self.bledy.append(str(m))


def test_pyflakes_czysto():
    r = _Zbieraj()
    for p in sorted(glob.glob(os.path.join(KORZEN, '*.py')) + glob.glob(os.path.join(KORZEN, 'tests', '*.py'))):
        pyflakes_api.checkPath(p, r)
    assert not r.bledy, '\n'.join(r.bledy)
