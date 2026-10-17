"""api_football.py — API-Football (API-Sports) w TRYBIE OBSERWACJI (17.10.2026, decyzja użytkownika: „zróbmy wszystkie”).
Nic w przebiegu, typowaniu ani rozliczeniach z tego nie korzysta do backtestu i decyzji użytkownika. Dane zbiera
apps_script/wyniki_live.gs (folder „api-football” na Dysku + wyniki_live.json); tu tylko pomiary.

  python3 api_football.py ligi KURSY.csv.gz wyniki_live.json [--wyjscie api_ligi.json]
      dopasowanie meczów piłki z oferty STS do API (ta sama godzina startu + OBIE drużyny), pokrycie, lista lig STS
      dla skryptu (plik api_ligi.json kładzie się na Dysku — skrypt pobiera statystyki, składy i historię tylko tych lig)
  python3 api_football.py rozliczenia Rozliczenie_DATA.csv api_wyniki_RRRR-MM.csv [...]
      nogi BRAK WYNIKU, które API ma rozliczone, i nogi, gdzie wynik API różni się od wyniku z rozliczenia
  python3 api_football.py historia KATALOG_Z_historia_*.csv --baza kb.sqlite
      ile drużyn i meczów z historii API nie ma w bazie (potencjalne nowe prognozy; Elo z własnych wyników = osobny backtest)
  python3 api_football.py statystyki api_statystyki_RRRR-MM.csv
      pokrycie strzałów, celnych, rożnych, kartek i xG w meczach lig STS
  python3 api_football.py kontuzje api_kontuzje_RRRR-MM.csv
      kontuzje i zawieszenia w ligach STS (co da się dopiąć do meczów z oferty)
"""
import collections
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
import unicodedata
from zoneinfo import ZoneInfo

import pandas as pd

import nazwy

PL = ZoneInfo('Europe/Warsaw')
STOP = {'fc', 'sv', 'sc', 'tsg', 'vfb', 'vfl', 'tsv', 'msv', 'fsv', 'borussia', '1899', 'club', 'afc', 'cf', 'cd', 'ac', 'fk',
        'sk', 'nk', 'ifk', 'bk', 'if', 'fa', 'united', 'city',
        # 17.10.2026 (oferta 17.10 vs API): słowa wspólne wielu klubom — same w sobie nie są dowodem tej samej drużyny
        # („Hednesford Town – Brackley Town” pasowało do kilku meczów „Town – Town” o 16:00)
        'town', 'athletic', 'atletico', 'real', 'deportivo', 'san', 'inter', 'county', 'wanderers', 'rovers', 'sporting',
        'villa', 'rangers', 'union', 'central', 'south', 'north', 'east', 'west', 'nacional', 'olympic', 'sports', 'hapoel',
        'maccabi', 'racing', 'albion', 'women', 'reserves', 'youth', 'academy', 'res'}


def _norm(s):
    s = str(s or '').replace('ı', 'i').replace('ß', 'ss').replace('ł', 'l').replace('Ł', 'L').replace('ø', 'o').replace('æ', 'ae')
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()


def tokeny(s):
    return [w for w in re.split('[^a-z0-9]+', _norm(s)) if len(w) >= 3 and w not in STOP and not re.fullmatch(r'u\d\d|ii|iii', w)]


def ta_sama(x, y):
    """Ta sama drużyna pod inną pisownią (17.10: Tvaakers IF / Tvååker, Kyzylzhar / Kyzyl-Zhar, Aalesunds / Aalesund):
    wspólne słowo, jedna nazwa zawarta w drugiej albo wspólne 5 pierwszych liter słowa. Używane TYLKO razem z tą samą
    godziną startu i drugą drużyną — samo w sobie nie jest dowodem (nie zgadujemy nazw)."""
    if nazwy.znaczniki(x) != nazwy.znaczniki(y):     # kobiety / rezerwy / U21… muszą się zgadzać
        return False
    a, b = tokeny(x), tokeny(y)
    if set(a) & set(b):
        return True
    sx, sy = ''.join(a), ''.join(b)
    if len(sx) >= 5 and len(sy) >= 5 and (sx in sy or sy in sx):
        return True
    return any(len(p) >= 5 and len(q) >= 5 and p[:5] == q[:5] for p in a for q in b)


def start_utc(data, godz):
    """Data i godzina z oferty STS (czas polski, latem UTC+2, zimą UTC+1) -> sekundy UTC."""
    try:
        t = dt.datetime.strptime(f'{data} {godz}', '%Y-%m-%d %H:%M').replace(tzinfo=PL)
    except (TypeError, ValueError):
        return None
    return int(t.timestamp())


def mecze_sts(kursy):
    """Kursy z oferta.py -> jeden wiersz na mecz piłki (data, godz, liga, A, B, t)."""
    k = kursy[(kursy.sport == 'PIŁKA NOŻNA') & kursy.gospodarz.notna() & kursy.gosc.notna()]
    m = k.drop_duplicates(['data_meczu', 'godzina_meczu', 'gospodarz', 'gosc'])[['data_meczu', 'godzina_meczu', 'liga', 'gospodarz', 'gosc']]
    m = m.rename(columns={'data_meczu': 'data', 'godzina_meczu': 'godz', 'gospodarz': 'A', 'gosc': 'B'}).reset_index(drop=True)
    m['t'] = [start_utc(d, g) for d, g in zip(m.data, m.godz)]
    return m


def dopasuj(sts, api):
    """sts: mecze_sts; api: lista meczów z wyniki_live.json (s='football'). -> lista (indeks STS, mecz API albo None, powód).
    Jednoznacznie: ta sama godzina startu i OBIE drużyny; kilka kandydatów = brak (nie zgadujemy)."""
    po_t = collections.defaultdict(list)
    for m in api:
        po_t[m.get('t')].append(m)
    wynik = []
    for i, r in sts.iterrows():
        k = [m for m in po_t.get(r.t, []) if ta_sama(r.A, m.get('a')) and ta_sama(r.B, m.get('b'))]
        if len(k) == 1:
            wynik.append((i, k[0], 'ok'))
        elif len(k) > 1:
            wynik.append((i, None, 'kilka kandydatów'))
        else:
            jedna = [m for m in po_t.get(r.t, []) if ta_sama(r.A, m.get('a')) or ta_sama(r.B, m.get('b'))]
            wynik.append((i, None, 'inna nazwa jednej drużyny' if jedna else 'brak w API o tej godzinie'))
    return wynik


def ligi(a):
    kursy = pd.read_csv(a[1], dtype=str)
    feed = json.load(open(a[2], encoding='utf-8'))
    api = [m for m in feed.get('mecze', []) if m.get('s') == 'football']
    sts = mecze_sts(kursy)
    dni = sorted({dt.datetime.fromtimestamp(m['t'], PL).strftime('%Y-%m-%d') for m in api if m.get('t')})
    sts = sts[sts.data.isin(dni)].reset_index(drop=True)      # tylko dni, które plik API obejmuje
    dop = dopasuj(sts, api)
    powody = collections.Counter(p for _, _, p in dop)
    print(f'POKRYCIE {", ".join(dni)}: {len(sts)} meczów piłki STS, w API jednoznacznie {powody["ok"]} '
          f'({100 * powody["ok"] / max(1, len(sts)):.1f}%) | ' + ', '.join(f'{k} {v}' for k, v in powody.items() if k != 'ok'))
    for i, _, p in dop:
        if p != 'ok':
            r = sts.loc[i]
            print(f'  {p}: {r.data} {r.godz} {r.liga} | {r.A} – {r.B}')
    lg = {}
    for i, m, p in dop:
        if m is None or not m.get('lid'):
            continue
        x = lg.setdefault(m['lid'], dict(lid=m['lid'], sezon=m.get('sez'), liga=m.get('lg'), kraj=m.get('kr'), mecze_sts=0,
                                         ligi_sts=set()))
        x['mecze_sts'] += 1
        x['ligi_sts'].add(sts.loc[i].liga)
    bez_lid = sum(1 for _, m, _ in dop if m is not None and not m.get('lid'))
    if bez_lid:
        print(f'UWAGA: {bez_lid} dopasowanych meczów bez identyfikatora ligi (stara wersja wyniki_live.gs) — wklej aktualną')
    lista = sorted(lg.values(), key=lambda x: -x['mecze_sts'])
    for x in lista:
        x['ligi_sts'] = sorted(x['ligi_sts'])
    wyj = a[a.index('--wyjscie') + 1] if '--wyjscie' in a else 'api_ligi.json'
    json.dump({'utworzono': dt.datetime.now(PL).strftime('%Y-%m-%d %H:%M'), 'dni': dni, 'ligi': lista},
              open(wyj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'LIGI STS w API: {len(lista)} -> {wyj}')
    return lista


def _wyniki_api(pliki):
    w = pd.concat([pd.read_csv(p, dtype={'gg': 'Int64', 'ga': 'Int64'}) for p in pliki], ignore_index=True)
    return w[w.status.isin(['FT', 'AET', 'PEN'])]


def rozliczenia(a):
    roz = pd.read_csv(a[1], dtype=str).fillna('')
    data = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(a[1]))
    data = data.group(1) if data else None
    w = _wyniki_api(a[2:])
    if data:
        w = w[w.data.isin([data, (pd.Timestamp(data) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')])]
    nogi = roz[~roz.tag.str.startswith('RAZEM_') & roz.zdarzenie.str.contains(' - ')]
    zysk, rozne, bez = [], [], 0
    for r in nogi.itertuples():
        A, B = [x.strip() for x in r.zdarzenie.split(' - ', 1)]
        k = w[[ta_sama(A, g) and ta_sama(B, h) for g, h in zip(w.gosp, w.gosc)]]
        if len(k) != 1:
            bez += r.TRAFIONY_PRZEGRANY == 'BRAK WYNIKU'
            continue
        m = k.iloc[0]
        wynik_api = f'{m.gg}:{m.ga}'
        if r.TRAFIONY_PRZEGRANY == 'BRAK WYNIKU':
            zysk.append((r.tag, r.zdarzenie, r.rynek, wynik_api, r.kategoria, r.uwaga))
        elif r.wynik and re.match(r'^\d+:\d+', r.wynik) and r.wynik.split()[0].split('(')[0] != wynik_api:
            rozne.append((r.tag, r.zdarzenie, r.rynek, r.wynik, wynik_api))
    brak = (nogi.TRAFIONY_PRZEGRANY == 'BRAK WYNIKU').sum()
    print(f'ROZLICZENIA {data}: {len(nogi)} nóg, BRAK WYNIKU {brak} — API ma wynik dla {len(zysk)}, bez meczu w API {bez}')
    for x in zysk:
        print(f'  API MA WYNIK: {x[0]} | {x[1]} | {x[2]} | API {x[3]} | [{x[4]}] {x[5]}')
    print(f'WYNIK RÓŻNY OD API: {len(rozne)}')
    for x in rozne:
        print(f'  {x[0]} | {x[1]} | {x[2]} | rozliczenie {x[3]} | API {x[4]}')
    return zysk, rozne


def historia(a):
    pliki = sorted(glob.glob(os.path.join(a[1], 'historia_*.csv')))
    if not pliki:
        sys.exit(f'brak plików historia_*.csv w {a[1]}')
    h = pd.concat([pd.read_csv(p) for p in pliki], ignore_index=True)
    h = h[h.status.isin(['FT', 'AET', 'PEN'])]
    druzyny = sorted(set(h.gosp) | set(h.gosc))
    baza = a[a.index('--baza') + 1] if '--baza' in a else 'kb.sqlite'
    con = sqlite3.connect(baza)
    m = pd.read_sql('select HomeTeam, AwayTeam from matches', con)
    w_bazie = set(m.HomeTeam) | set(m.AwayTeam)
    tok = collections.defaultdict(set)
    for n in w_bazie:
        for t in tokeny(n):
            tok[t].add(n)
    nowe = [d for d in druzyny if not any(ta_sama(d, n) for t in tokeny(d) for n in tok.get(t, ()))]
    print(f'HISTORIA: {len(pliki)} plików (liga x sezon), {len(h)} zakończonych meczów, {len(druzyny)} drużyn; '
          f'bez odpowiednika w bazie: {len(nowe)}')
    for d in nowe[:60]:
        print(f'  NOWA: {d}')
    return nowe


def statystyki(a):
    s = pd.read_csv(a[1])
    mecze = s.fid.nunique()
    print(f'STATYSTYKI: {mecze} meczów, {s.lid.nunique()} lig')
    for k in ('strzaly', 'celne', 'rozne', 'zolte', 'xg'):
        ok = s.groupby('fid')[k].apply(lambda x: x.notna().all()).sum()
        print(f'  {k}: {ok}/{mecze} meczów ({100 * ok / max(1, mecze):.0f}%)')
    return s


def kontuzje(a):
    k = pd.read_csv(a[1])
    print(f'KONTUZJE: {len(k)} wpisów, {k.druzyna.nunique()} drużyn, {k.fid.nunique()} meczów')
    for t, n in k.typ.value_counts().items():
        print(f'  {t}: {n}')
    return k


def main(a):
    if not a or a[0] not in ('ligi', 'rozliczenia', 'historia', 'statystyki', 'kontuzje') or len(a) < 2:
        sys.exit(__doc__)
    return {'ligi': ligi, 'rozliczenia': rozliczenia, 'historia': historia, 'statystyki': statystyki, 'kontuzje': kontuzje}[a[0]](a)


if __name__ == '__main__':
    main(sys.argv[1:])
