"""termux/zrodla.py — zbieranie FotMob po analizie 27 zipow z 03–07.10.2026: osobne limity szczegolow przed/po meczu,
przedwczoraj w oknie „po meczu”, kolejnosc wg listy priorytetu, pobrano_utc, strzaly, Sofascore wylaczony domyslnie.
Syntetyczne odpowiedzi, bez sieci (Sesja.get podmieniony)."""
import datetime as dt
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'termux'))
import zrodla as z  # noqa: E402

TERAZ = dt.datetime(2026, 10, 7, 10, 0)          # 12:00 PL
DZIS = dt.date(2026, 10, 7)
ISO = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')


def _mecz(i, kraj='ENG', liga='Premier League', start=TERAZ + dt.timedelta(hours=1), koniec=False, data=DZIS):
    return {'id': i, 'home': {'name': f'H{i}'}, 'away': {'name': f'A{i}'},
            'status': {'utcTime': start.strftime('%Y-%m-%dT%H:%M:%SZ'), 'finished': koniec, 'started': koniec,
                       'scoreStr': '1 - 0' if koniec else ''}, '_data': str(data), '_kraj': kraj, '_liga': liga}


SZCZEGOLY = {'content': {'stats': {'Periods': {'All': {'stats': [{'title': 'Top stats', 'stats': [
    {'title': 'Expected goals (xG)', 'key': 'expected_goals', 'stats': ['1.84', '0.62']},
    {'title': 'Total shots', 'key': 'total_shots', 'stats': [14, 6]},
    {'title': 'Shots on target', 'key': 'ShotsOnTarget', 'stats': [5, 2]}]}]}}},
    'matchFacts': {'infoBox': {'Stadium': {'name': 'S', 'city': 'C', 'lat': 51.5, 'long': -0.1},
                               'Referee': {'text': 'Michael Oliver'}}}}}


class SesjaFalszywa(z.Sesja):
    """Odpowiada listami meczow wg daty i szczegolami; liczy zapytania matchDetails."""

    def __init__(self, mecze, budzet_s=720):
        super().__init__(budzet_s)
        self.mecze, self.szczegoly, self.daty = mecze, [], []

    def get(self, zrodlo, url, naglowki=None, **kw):
        self.kody.setdefault(zrodlo, {}).setdefault(200, 0)
        m = re.search(r'matches\?date=(\d{8})', url)
        if m:
            d = dt.datetime.strptime(m.group(1), '%Y%m%d').date()
            self.daty.append(d)
            lig = {}
            for x in self.mecze:
                if x['_data'] == str(d):
                    lig.setdefault((x['_kraj'], x['_liga']), []).append({k: v for k, v in x.items() if not k.startswith('_')})
            return 200, json.dumps({'leagues': [{'id': i, 'name': l, 'ccode': k, 'matches': ms}
                                                for i, ((k, l), ms) in enumerate(lig.items())]})
        m = re.search(r'matchDetails\?matchId=(\d+)', url)
        if m:
            self.szczegoly.append(int(m.group(1)))
            return 200, json.dumps(SZCZEGOLY)
        return 404, ''


def test_osobne_limity_przed_i_po(monkeypatch):
    monkeypatch.setattr(z, 'FM_MAKS_PRZED', 3)
    monkeypatch.setattr(z, 'FM_MAKS_PO', 4)
    przed = [_mecz(i) for i in range(1, 11)]
    po = [_mecz(100 + i, start=TERAZ - dt.timedelta(hours=20), koniec=True, data=DZIS - dt.timedelta(days=1)) for i in range(10)]
    s, w, gotowe = SesjaFalszywa(przed + po), {}, set()
    z.z_fotmob(s, w, DZIS, TERAZ, gotowe)
    etapy = [r['etap'] for r in w['fotmob_szczegoly']]
    assert etapy.count('przed') == 3 and etapy.count('po') == 4      # duzo meczow przed nie zjada limitu „po”
    assert len(s.szczegoly) == 7 and len(gotowe) == 4
    assert any('przed meczem 3/3' in d and 'po meczu 4/4' in d and 'czas' in d for d in s.diag)
    # drugie uruchomienie: zakonczone juz pobrane nie wracaja, reszta „po” dociagana
    s2, w2 = SesjaFalszywa(przed + po), {}
    z.z_fotmob(s2, w2, DZIS, TERAZ, gotowe)
    assert [r['etap'] for r in w2['fotmob_szczegoly']].count('po') == 4 and len(gotowe) == 8


def test_przedwczoraj_w_oknie_po_meczu():
    przedwczoraj = DZIS - dt.timedelta(days=2)
    stary = _mecz(7, start=TERAZ - dt.timedelta(days=2), koniec=True, data=przedwczoraj)
    za_stary = _mecz(8, start=TERAZ - dt.timedelta(days=3), koniec=True, data=DZIS - dt.timedelta(days=3))
    s, w = SesjaFalszywa([stary, za_stary]), {}
    z.z_fotmob(s, w, DZIS, TERAZ, set())
    assert przedwczoraj in s.daty and DZIS - dt.timedelta(days=3) not in s.daty
    assert [r['mecz_id'] for r in w['fotmob_szczegoly']] == [7]


def test_kolejnosc_wg_priorytetu(monkeypatch):
    monkeypatch.setattr(z, 'FM_MAKS_PRZED', 3)
    mecze = [_mecz(1, kraj='IDN', liga='Liga 1', start=TERAZ + dt.timedelta(minutes=10)),
             _mecz(2, kraj='ENG', liga="Women's Super League", start=TERAZ + dt.timedelta(minutes=20)),
             _mecz(3, kraj='NED', liga='Eredivisie', start=TERAZ + dt.timedelta(minutes=30)),
             _mecz(4, kraj='INT', liga='World Cup Qualification UEFA', start=TERAZ + dt.timedelta(hours=3)),
             _mecz(5, kraj='POL', liga='Ekstraklasa', start=TERAZ + dt.timedelta(hours=2))]
    s, w = SesjaFalszywa(mecze), {}
    z.z_fotmob(s, w, DZIS, TERAZ, set())
    # grupa 1 (INT/POL, potem kobiece ENG na koncu grupy) przed NED; Indonezja poza lista odpada przy limicie 3
    assert s.szczegoly == [5, 4, 2]
    assert z.fm_priorytet({'kraj': 'NED', 'liga': 'Eredivisie'}) < z.fm_priorytet({'kraj': 'IDN', 'liga': 'Liga 1'})
    assert z.fm_priorytet({'kraj': 'ENG', 'liga': 'Premier League'}) < z.fm_priorytet({'kraj': 'ENG', 'liga': 'U21 Premier League 2'})


def test_przerwa_gdy_konczy_sie_budzet():
    mecze = [_mecz(i) for i in range(1, 6)]
    s, w = SesjaFalszywa(mecze, budzet_s=z.REZERWA_S - 1), {}
    z.z_fotmob(s, w, DZIS, TERAZ, set())
    assert s.szczegoly == [] and w['fotmob_szczegoly'] == []
    assert any('PRZERWANE' in d for d in s.diag)


def test_pobrano_utc_i_strzaly():
    przed = _mecz(1)
    po = _mecz(2, start=TERAZ - dt.timedelta(hours=5), koniec=True)
    s, w = SesjaFalszywa([przed, po]), {}
    z.z_fotmob(s, w, DZIS, TERAZ, set())
    assert all(ISO.match(r['pobrano_utc']) for r in w['fotmob_mecze'] + w['fotmob_szczegoly'])
    r = next(r for r in w['fotmob_szczegoly'] if r['etap'] == 'po')
    assert (r['xg_gosp'], r['strzaly_gosp'], r['strzaly_gosc'], r['celne_gosp'], r['celne_gosc']) == ('1.84', 14, 6, 5, 2)
    assert len(s.szczegoly) == 2                                     # strzaly bez dodatkowych zapytan
    sedz = z.sedziowie(w)
    assert sedz and all(ISO.match(x['pobrano_utc']) for x in sedz)
    # pogoda: wspolrzedne z FotMob (mecz przed), odpowiedz Open-Meteo syntetyczna
    t = z.utc_z(przed['status']['utcTime'])
    s.get_json = lambda zr, url, *a, **k: [{'hourly': {'time': [t.strftime('%Y-%m-%dT%H:00')], 'temperature_2m': [12],
                                                       'precipitation': [0], 'wind_speed_10m': [9]}}]
    z.z_pogoda(s, w)
    assert len(w['pogoda']) == 1 and ISO.match(w['pogoda'][0]['pobrano_utc'])
    assert z.fotmob_szczegoly({'x': {'title': 'Total shots', 'stats': [3, 4]}})['strzaly_gosc'] == 4


def test_sofascore_wylaczony_domyslnie(tmp_path, monkeypatch):
    monkeypatch.setattr(z, 'STAN', str(tmp_path / 'stan.json'))
    adresy = []
    monkeypatch.setattr(z.Sesja, 'get', lambda self, zr, url, *a, **k: (adresy.append(url), (0, ''))[1])
    assert z.main(['--katalog', str(tmp_path), '--budzet-min', '1', '--tylko', 'fotmob,sofascore,nhl']) == 0
    assert any('sofascore' in u for u in adresy)                     # --tylko sofascore = wyraznie wlaczony
    adresy.clear()
    for p in tmp_path.glob('zrodla_*.zip'): p.unlink()
    assert z.main(['--katalog', str(tmp_path), '--budzet-min', '1']) == 0
    assert not any('sofascore' in u for u in adresy) and any('fotmob' in u for u in adresy)
    with zipfile.ZipFile(next(tmp_path.glob('zrodla_*.zip'))) as zf:
        diag = zf.read(next(n for n in zf.namelist() if n.startswith('zrodla_diag_'))).decode()
    linie = [x for x in diag.splitlines() if 'sofascore' in x]
    assert len(linie) == 1 and 'WYLACZONE' in linie[0] and '--sofascore' in linie[0]
    assert 'fotmob szczegoly: przed meczem 0/0' in diag
    assert z.sofa_wlaczony(['--sofascore']) and not z.sofa_wlaczony(['--tylko', 'fotmob'])
