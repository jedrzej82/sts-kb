#!/usr/bin/env python3
"""Nazwy klubow z Wikidata -> wikidata_kluby.csv.gz (qid, sport, kraj, nazwy rozdzielone „|”).  Wersja 2.

Uruchom w Termuxie (tylko biblioteka standardowa Pythona, bez pip):
    pkg install -y python
    termux-setup-storage            # raz, zezwol na dostep do plikow
    python ~/storage/downloads/wikidata_pobierz.py
Wynik: ~/storage/downloads/wikidata_kluby.csv.gz -> wrzuc na Dysk do folderu baza-wiedzy.
Mozna przerwac (Ctrl+C) i uruchomic ponownie — pobrane porcje sa pomijane.

Trzy lekkie kroki zamiast jednego ciezkiego zapytania (wersja 1 dostawala HTTP 504):
 1) klasy „druzyna/klub sportowy” (samo drzewo podklas),
 2) identyfikatory klubow danego sportu tych klas (bez nazw),
 3) nazwy w porcjach po 200 klubow.
"""
import csv, gzip, json, os, sys, time, urllib.error, urllib.parse, urllib.request

URL = 'https://query.wikidata.org/sparql'
# Wikimedia wymaga User-Agenta z adresem kontaktowym — bez niego odpowiada 429/403
UA = 'sts-kb-aliasy/2.0 (https://github.com/jedrzej82/sts-kb; jednorazowe pobranie nazw klubow) Python-urllib'
SPORTY = {'piłka ręczna': 'Q8418', 'koszykówka': 'Q5372', 'siatkówka': 'Q1734', 'hokej': 'Q41466', 'piłka nożna': 'Q2736'}
KORZENIE = ('Q847017', 'Q12973014')   # klub sportowy, druzyna sportowa
JEZYKI = 'en pl de fr es it pt nl cs sk hr sr sl hu ro da sv nb nn fi tr el ru uk bg lt lv et is he ja ko zh'.split()
PORCJA = 200

DOM = os.path.expanduser('~/storage/downloads')
if not os.path.isdir(DOM): DOM = os.getcwd()
WYNIK = os.path.join(DOM, 'wikidata_kluby.csv.gz')
TMP = os.path.join(DOM, 'wikidata_kluby_czesci2')


class Limit(Exception): pass


def zapytaj(q, proby=4):
    dane = urllib.parse.urlencode({'query': q, 'format': 'json'}).encode()
    limity = 0
    for i in range(proby):
        req = urllib.request.Request(URL, data=dane, headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json'})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)['results']['bindings']
        except urllib.error.HTTPError as e:
            if e.code in (429, 403):
                limity += 1
                if limity >= 2: raise Limit(f'HTTP {e.code} dwa razy z rzedu: {e.read()[:300]!r}')
                czekaj = min(int(e.headers.get('Retry-After', 60) or 60), 180)
                print(f'   HTTP {e.code} (limit), czekam {czekaj}s'); time.sleep(czekaj); continue
            print(f'   HTTP {e.code}, ponawiam za {15 * (i + 1)}s'); time.sleep(15 * (i + 1))
        except Exception as e:
            print(f'   blad polaczenia: {e}; ponawiam'); time.sleep(10 * (i + 1))
    return None


def qid(x): return x['value'].rsplit('/', 1)[1]


def pamiec(nazwa, fn):
    """Wynik kroku zapisany w pliku — ponowne uruchomienie go nie pobiera."""
    p = os.path.join(TMP, nazwa + '.json')
    if os.path.exists(p): return json.load(open(p, encoding='utf-8'))
    w = fn()
    if w is None: return None
    json.dump(w, open(p, 'w', encoding='utf-8'), ensure_ascii=False)
    return w


def klasy():
    wsz = set(KORZENIE)
    for k in KORZENIE:
        b = zapytaj(f'SELECT ?t WHERE {{ ?t wdt:P279+ wd:{k} . }}')
        if b is None: return None
        wsz |= {qid(x['t']) for x in b}
    return sorted(wsz)


def kluby(sport_q, typy):
    """Identyfikatory klubow: sport + klasa z drzewa druzyn (klasy w porcjach, zeby zapytanie bylo lekkie)."""
    out = set()
    for i in range(0, len(typy), 300):
        vals = ' '.join('wd:' + t for t in typy[i:i + 300])
        b = zapytaj(f'SELECT DISTINCT ?k WHERE {{ VALUES ?t {{ {vals} }} ?k wdt:P31 ?t ; wdt:P641 wd:{sport_q} . }}')
        if b is None: return None
        out |= {qid(x['k']) for x in b}
        time.sleep(1)
    return sorted(out)


def nazwy(ids):
    vals = ' '.join('wd:' + q for q in ids)
    langs = ', '.join(f'"{x}"' for x in JEZYKI)
    b = zapytaj(f"""SELECT ?k (SAMPLE(?kn) AS ?kraj) (GROUP_CONCAT(DISTINCT ?n; separator="|") AS ?nazwy) WHERE {{
  VALUES ?k {{ {vals} }}
  OPTIONAL {{ ?k wdt:P17 ?c . ?c rdfs:label ?kn . FILTER(LANG(?kn) = "en") }}
  {{ ?k rdfs:label ?n . }} UNION {{ ?k skos:altLabel ?n . }}
  FILTER(LANG(?n) IN ({langs}))
}} GROUP BY ?k""")
    if b is None: return None
    return [[qid(x['k']), x.get('kraj', {}).get('value', ''), x['nazwy']['value']] for x in b]


def main():
    os.makedirs(TMP, exist_ok=True)
    print('1/3 klasy druzyn sportowych...')
    typy = pamiec('klasy', klasy)
    if not typy: sys.exit('Nie udalo sie pobrac klas — uruchom ponownie za kilka minut.')
    print(f'    {len(typy)} klas')
    brak = []
    for sport, sq in SPORTY.items():
        ids = pamiec(f'kluby_{sq}', lambda: kluby(sq, typy))
        if ids is None: print(f'{sport}: NIE pobrano listy klubow'); brak.append(sport); continue
        porcje = [ids[i:i + PORCJA] for i in range(0, len(ids), PORCJA)]
        print(f'2/3 {sport}: {len(ids)} klubow, 3/3 nazwy w {len(porcje)} porcjach')
        for j, p in enumerate(porcje):
            w = pamiec(f'nazwy_{sq}_{j:04d}', lambda: nazwy(p))
            if w is None: print(f'    porcja {j}: blad — uruchom ponownie pozniej'); brak.append(sport); break
            if (j + 1) % 10 == 0 or j + 1 == len(porcje): print(f'    {j + 1}/{len(porcje)}')
            time.sleep(0.5)
    wsz = []
    for sport, sq in SPORTY.items():
        for f in sorted(os.listdir(TMP)):
            if f.startswith(f'nazwy_{sq}_'):
                wsz += [[q, sport, k, n] for q, k, n in json.load(open(os.path.join(TMP, f), encoding='utf-8'))]
    with gzip.open(WYNIK, 'wt', encoding='utf-8', newline='') as f:
        c = csv.writer(f); c.writerow(['qid', 'sport', 'kraj', 'nazwy']); c.writerows(wsz)
    print(f'\nZAPISANO {WYNIK}: {len(wsz)} klubow' + (f'; NIEPELNE: {", ".join(sorted(set(brak)))} — uruchom ponownie' if brak else ''))
    print('Wrzuc ten plik na Dysk do folderu baza-wiedzy.')


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: sys.exit('\nprzerwano — uruchom ponownie, pobrane porcje zostana pominiete')
    except Limit as e: sys.exit(f'\nWikidata odmawia (limit): {e}\nPrzeslij zrzut ekranu — odczekaj ok. 15 min przed ponowieniem.')
