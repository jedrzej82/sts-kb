"""30.09.2026 (audyt oferty 01.10): klub z innego kraju / nieznana nazwa — ponowne dopasowanie w kraju meczu z terminarza."""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import typuj, terminarz


def _m():
    r = [('2026-09-20', 'Colombia | Primera A', 'Atletico Nacional', 'Junior FC'),
         ('2026-09-21', 'Nicaragua | Liga de Ascenso', 'CD Junior', 'Real Esteli B'),
         ('2026-09-22', 'El Salvador | Primera Division', 'Alianza FC [elsalvador]', 'Platense Municipal'),
         ('2026-09-23', 'Honduras | Liga Nacional', 'CD Platense', 'Olimpia'),
         ('2026-09-24', 'Paraguay | Primera', 'Cerro Porteño', 'Rubio Ñu'),
         ('2026-09-25', 'Paraguay | Primera', 'Cerro Porteño B', 'Olimpia Asuncion')]
    return pd.DataFrame(r, columns=['MatchDate', 'Division', 'HomeTeam', 'AwayTeam']).assign(MatchDate=lambda x: pd.to_datetime(x.MatchDate))


def _mt(kraj, g, a):
    return dict(kraj=kraj, turniej='Liga', gosp=g, gosc=a, data='2026-10-01', godzina_utc='01:00')


def test_klub_z_innego_kraju_zamieniony():
    m = _m(); pool = set(m.HomeTeam) | set(m.AwayTeam)
    r = typuj._kraj_z_terminarza('Atletico Nacional', 'CD Junior Barranquilla', 'Atletico Nacional', 'CD Junior',
                                 'colombia', 'nicaragua', pool, m, _mt('Colombia', 'Atletico Nacional', 'Junior FC'))
    assert r == ('Atletico Nacional', 'Junior FC')


def test_nieznana_nazwa_w_kraju_meczu():
    m = _m(); pool = set(m.HomeTeam) | set(m.AwayTeam)
    r = typuj._kraj_z_terminarza('Cerro Porteno Asuncion', 'Rubio Nu', None, 'Rubio Ñu', None, None, pool, m,
                                 _mt('Paraguay', 'Cerro Porteno', 'Rubio Nu'))
    assert r == ('Cerro Porteño', 'Rubio Ñu')


def test_bez_meczu_albo_kraj_ogolny_bez_zmian(monkeypatch):
    m = _m(); pool = set(m.HomeTeam) | set(m.AwayTeam)
    monkeypatch.setattr(terminarz, 'znajdz', lambda *a, **k: None)              # meczu nie ma w terminarzu
    assert typuj._kraj_z_terminarza('Cerro Porteno Asuncion', 'Rubio Nu', None, 'Rubio Ñu', None, None, pool, m) is None
    assert typuj._kraj_z_terminarza('Cerro Porteno Asuncion', 'Rubio Nu', None, 'Rubio Ñu', None, None, pool, m,
                                    _mt('World', 'Cerro Porteno', 'Rubio Nu')) is None
    # nazwa bez jednoznacznego klubu w kraju meczu — nic nie zgadujemy
    assert typuj._kraj_z_terminarza('Nieznany Klub', 'Rubio Nu', None, 'Rubio Ñu', None, None, pool, m,
                                    _mt('Paraguay', 'Nieznany Klub', 'Rubio Nu')) is None


def test_znajdz_luzno():
    t = pd.DataFrame([('2026-10-01', '00:00', 'football', 'El Salvador', 'Primera Division', '', 'Alianza FC', 'Platense Municipal', '2'),
                      ('2026-10-01', '01:00', 'football', 'Colombia', 'Liga BetPlay', '', 'Atletico Nacional', 'Junior FC', '2')],
                     columns=['data', 'godzina_utc', 'sport', 'kraj', 'turniej', 'runda', 'gosp', 'gosc', 'status'])
    assert terminarz.znajdz('Alianza FC San Salvador', 'CD Platense Zacatecoluca', t) is None       # scisle: nic
    assert terminarz.znajdz('Alianza FC San Salvador', 'CD Platense Zacatecoluca', t, luzno=True)['gosc'] == 'Platense Municipal'
    assert terminarz.znajdz('Atletico Nacional', 'CD Junior Barranquilla', t, luzno=True)['gosc'] == 'Junior FC'
    assert terminarz.znajdz('Deportivo Cali', 'Junior U19', t, luzno=True) is None                 # obie luzno / znaczniki


def test_stary_zapis_klubu_nie_jest_kandydatem():
    """Raport 30.09 21:00: „San Luis Quillota” -> „San Luis” (ostatni mecz 2018) zamiast „San Luis de Quillota”."""
    r = [('2018-11-28', 'CHI', 'San Luis', 'Colo Colo'),
         ('2026-09-15', 'Chile | First Division B', 'San Luis de Quillota', 'Cobreloa'),
         ('2026-09-26', 'Chile | First Division B', 'Union San Felipe', 'Deportes Copiapo')]
    m = pd.DataFrame(r, columns=['MatchDate', 'Division', 'HomeTeam', 'AwayTeam']).assign(MatchDate=lambda x: pd.to_datetime(x.MatchDate))
    pool = set(m.HomeTeam) | set(m.AwayTeam)
    assert typuj._w_kraju(['San Luis', 'San Luis Quillota'], 'chile', pool, m) == 'San Luis de Quillota'


def test_sporty_stary_zapis_pominiety():
    import sporty
    d = pd.DataFrame([('2018-03-01', 'koszykówka', 'Chile | LNB', 'San Luis', 'X'),
                      ('2026-09-20', 'koszykówka', 'Chile | LNB', 'San Luis de Quillota', 'Y')],
                     columns=['data', 'sport', 'liga', 'gosp', 'gosc']).assign(data=lambda x: pd.to_datetime(x.data))
    r = sporty.kraj_z_terminarza(d, 'koszykówka', ('San Luis Quillota', 'Y'), (None, 'Y'),
                                 mt=dict(kraj='Chile', turniej='LNB', gosp='San Luis', gosc='Y'))
    assert r == ('San Luis de Quillota', 'Y')
