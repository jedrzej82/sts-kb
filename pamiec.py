"""Cache na dysku (pickle) bezpieczny dla kilku procesow naraz (07.10.2026).

Raport 07.10 12:00, usterka 3: przy 4 rownoleglych tenis.py jeden proces otwieral plik stanu do zapisu
(open(p, 'wb') — plik juz istnieje, ma swiezy czas modyfikacji, ale jest PUSTY), a drugi w tej chwili go czytal:
„EOFError: Ran out of input”. Zapis idzie teraz do pliku tymczasowego i jest podmieniany jednym os.replace
(atomowo — czytelnik widzi stary albo nowy plik, nigdy polowe), a nieczytelny plik oznacza „brak cache”."""
import os
import pickle
import tempfile


def wczytaj(p):
    """Zawartosc cache albo None, gdy pliku nie ma lub jest nieczytelny (uciety, pusty, inna wersja)."""
    try:
        with open(p, 'rb') as f:
            return pickle.load(f)
    except (OSError, EOFError, pickle.UnpicklingError, AttributeError, ImportError, IndexError, ValueError):
        return None


def zapisz(p, v):
    """Atomowy zapis: plik tymczasowy w tym samym katalogu + os.replace."""
    d = os.path.dirname(os.path.abspath(p))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.' + os.path.basename(p) + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            pickle.dump(v, f)
        os.replace(tmp, p)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return v
