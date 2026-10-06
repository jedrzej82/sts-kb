"""06.10.2026 — termux/kursy_bukmacherow.py --diag-sts: skad strona STS bierze oferte (bez sieci: odpowiedzi podstawione)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'termux'))
import kursy_bukmacherow as kb   # noqa: E402


def test_adresy_bez_plikow_statycznych_i_obcych_hostow():
    js = ('fetch("https://api.sts.pl/offer/v2/events?sport=1");a="/api/live/matches";b="https://cdn.sts.pl/logo.svg";'
          'c="wss://push.sts.pl/socket";d="/graphql";e="https://example.com/api";f="https://static.sts.pl/app.js"')
    assert kb.sts_adresy(js) == ['/api/live/matches', '/graphql', 'https://api.sts.pl/offer/v2/events?sport=1',
                                 'wss://push.sts.pl/socket']
    html = '<script src="/_next/a.js"></script><script defer src="//static.sts.pl/b.js"></script><script src="/_next/a.js">'
    assert kb.sts_skrypty(html, 'https://www.sts.pl') == ['https://www.sts.pl/_next/a.js', 'https://static.sts.pl/b.js']


def test_diag_sts_zapisuje_plik(tmp_path, monkeypatch):
    odp = {'https://www.sts.pl/': (200, 'text/html', '<script src="/app.js"></script><script>window.__NUXT__={}</script>'),
           'https://www.sts.pl/app.js': (200, 'application/javascript', 'x="https://api.sts.pl/offer/events";y="/api/sport"'),
           'https://api.sts.pl/offer/events': (200, 'application/json', '{"events":[{"id":1,"odds":[1.5,4.0,6.0]}]}'),
           'https://www.sts.pl/api/sport': (403, 'text/html', 'Forbidden')}
    monkeypatch.setattr(kb, '_sts_pobierz', lambda u, h=None, limit=0: odp.get(u, (404, 'text/html', 'nie ma')))
    monkeypatch.setattr(kb.time, 'sleep', lambda s: None)
    plik = kb.diag_sts(['--diag-sts', '--katalog', str(tmp_path)])
    t = open(plik, encoding='utf-8').read()
    assert os.path.basename(plik).startswith('diag_sts_')
    assert '__NUXT__' in t and 'https://api.sts.pl/offer/events' in t and '"odds"' in t
    assert '403' in t and '404' in t                                  # bledy tez sa w pliku
