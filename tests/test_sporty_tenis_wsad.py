"""07.10.2026 (Raporty 02.10 12:00 usterka 2, 02.10 18:00 usterka 4): tryb wsadowy sporty.py typuj i tenis.py —
baza / stan Elo raz na proces, wynik kazdego meczu taki jak osobne wywolanie (stan globalny czyszczony miedzy meczami).
Rownowaznosc na prawdziwych danych sprawdzona poza CI (17 meczow innych sportow, 11 tenisa: bloki identyczne)."""
import sys
import types

import sporty
import sporty_wsad
import tenis
import tenis_wsad


def _lista(tmp_path, tekst):
    p = tmp_path / 'lista.tsv'
    p.write_text(tekst, encoding='utf-8')
    return str(p)


def test_parsowanie_listy(tmp_path):
    p = _lista(tmp_path, '# komentarz\n\nhokej\t"Boston Bruins"\tChicago\t--neutral --kurs Z1=1.80\r\n'
                         'dart\tPrice\n'
                         'siatkówka\tPolska\tNiemcy\n')
    L = sporty_wsad.wczytaj_liste(p, 3)
    assert L[0][1:] == (['hokej', 'Boston Bruins', 'Chicago'], ['--neutral', '--kurs', 'Z1=1.80'])
    assert L[1][1] is None                                     # za malo pol -> zly wiersz, nie wyjatek
    assert L[2][1:] == (['siatkówka', 'Polska', 'Niemcy'], [])
    T = sporty_wsad.wczytaj_liste(_lista(tmp_path, '"Ann Li"\t"Belinda Bencic"\t--clay --bo5\n'), 2)
    assert T[0][1:] == (['Ann Li', 'Belinda Bencic'], ['--clay', '--bo5'])


def test_uruchom_lapie_exit_i_przywraca_argv():
    widziane = []

    def main(a):
        widziane.append(list(sys.argv))
        print('linia')
        if a[2] == 'zle': sys.exit('BRAK W BAZIE: ...')
    tekst, kod = sporty_wsad.uruchom(main, ['sporty.py', 'typuj', 'hokej', 'zle', 'B'], ['typuj', 'hokej', 'zle', 'B'])
    assert kod == 1 and tekst == 'linia\nBRAK W BAZIE: ...\n'
    assert widziane[0] == ['sporty.py', 'typuj', 'hokej', 'zle', 'B'] and sys.argv[1:3] != ['typuj', 'hokej']


def test_sporty_wsad_typuje_kazdy_wiersz_i_resetuje_stan(tmp_path, monkeypatch, capsys):
    wolane = []

    def main(a):
        wolane.append((list(a), dict(sporty._KANDYDAT)))
        sporty._KANDYDAT['x'] = 'z poprzedniego meczu'
        print('blok', a[2])
        if a[3] == 'Zly': sys.exit('BRAK W BAZIE')
    monkeypatch.setattr(sporty, 'main', main)
    p = _lista(tmp_path, 'hokej\tA\tB\t--neutral\nkoszykowka\tC\tZly\nzly wiersz\n')
    assert sporty_wsad.main([p]) == 0
    assert wolane == [(['typuj', 'hokej', 'A', 'B', '--neutral'], {}), (['typuj', 'koszykowka', 'C', 'Zly'], {})]
    out = capsys.readouterr().out
    assert out.startswith('##### 1/3 hokej | A | B\nblok A\nKOD: 0\n##### 2/3 koszykowka | C | Zly\nblok C\nBRAK W BAZIE\nKOD: 1\n')
    assert '##### 3/3 zly wiersz\nZLY WIERSZ LISTY' in out and out.endswith('KOD: 2\n')
    assert sporty.load is not None and not isinstance(getattr(sporty.load, '__self__', None), sporty_wsad.Pamiec)


def test_pamiec_liczy_raz_powtarza_wypis_i_oddaje_kopie():
    licz = {'load': 0, 'elo': 0, 'marza': 0}
    d = object()

    def load():
        licz['load'] += 1; print('scalono warianty: 1'); return d

    def elo(d_, sport, pre=None, info=None):
        licz['elo'] += 1
        if info is not None: info.update(last={'A': 1}, seeded={})
        return {'A': 1500.0}, {'A': 3}, 50, True, 0.2

    def marza(d_, sport, k):
        licz['marza'] += 1; return {'A': 1.0}
    m = types.SimpleNamespace(load=load, elo=elo, marza=marza)
    pam = sporty_wsad.Pamiec(m); pam.zaloz()
    for _ in range(3):
        tekst, _kod = sporty_wsad.uruchom(lambda: print(m.load() is d), ['x'])
        assert tekst == 'scalono warianty: 1\nTrue\n'           # wypis load() w kazdym meczu, jak w osobnym procesie
        inf = {}
        R, N, *_ = m.elo(m.load.__self__.d, 'hokej', info=inf)
        R['A'] = 0; inf['last']['A'] = 99                      # zmiana kopii nie psuje nastepnego meczu
        M = m.marza(d, 'koszykowka', {'k': 0.1, 'hfa': 2}); M['A'] = -5
    assert m.elo(d, 'hokej', info={})[0] == {'A': 1500.0} and m.marza(d, 'koszykowka', {'k': 0.1, 'hfa': 2}) == {'A': 1.0}
    assert licz == {'load': 1, 'elo': 1, 'marza': 1}
    m.elo(d, 'hokej', pre=[])                                  # backtest (pre) bez pamieci
    assert licz['elo'] == 2
    pam.zdejmij()
    assert m.load is load and m.elo is elo and m.marza is marza


def test_tenis_wsad_stan_raz_i_reset_slownikow(tmp_path, monkeypatch, capsys):
    stany = []
    st = {'R': {'Ann Li': 1900.0}, 'N': {'Ann Li': 10}, 'last': {}, 'alias': {'Li Ann': 'Ann Li'}}
    monkeypatch.setattr(tenis, 'state', lambda: stany.append(1) or st)
    monkeypatch.setattr(tenis, 'fetch', lambda: None)
    wolane = []

    def main():
        s = tenis.state()
        wolane.append((list(sys.argv), dict(tenis.NCOUNT), dict(tenis.ALIASY)))
        s['R']['Ann Li'] = 0                                   # main dostaje kopie stanu
        tenis.NCOUNT.update(s['N']); tenis.ALIASY.update(s['alias']); tenis.ALIASY['smiec'] = 'z poprzedniego'
        print('Dopasowano:', sys.argv[1], sys.argv[2])
        if sys.argv[2] == 'Nikt': sys.exit('Brak zawodnika w bazie')
    monkeypatch.setattr(tenis, 'main', main)
    p = _lista(tmp_path, '"Ann Li"\t"Belinda Bencic"\t--clay\n"X"\t"Nikt"\n')
    assert tenis_wsad.main([p]) == 0
    assert len(stany) == 1 and st['R']['Ann Li'] == 1900.0
    assert wolane == [(['tenis.py', 'Ann Li', 'Belinda Bencic', '--clay'], {}, {}), (['tenis.py', 'X', 'Nikt'], {}, {})]
    assert capsys.readouterr().out == ('##### 1/2 Ann Li | Belinda Bencic\nDopasowano: Ann Li Belinda Bencic\nKOD: 0\n'
                                       '##### 2/2 X | Nikt\nDopasowano: X Nikt\nBrak zawodnika w bazie\nKOD: 1\n')
    assert not tenis.NCOUNT and not tenis.ALIASY                # po wsadzie modul czysty
