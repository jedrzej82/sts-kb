"""07.10.2026 — Raport 07.10 12:00, usterki 4 i 5 (rozliczenie 06.10, „nie dopasowano”). Reprodukcja na paczce 07.10:
  - EHC Visp – EHC Olten (Swiss League, Zwyciezca 1): Flashscore „Visp – Olten 11:2”; bylo BRAK WYNIKU, oczekiwane TRAFIONY,
  - Club Leandro Niceforo Alem – Centro SR Espanol (Primera C, X2): 365 „Leandro N. Alem – Centro Español 1:5”,
    Flashscore „Leandro N. Alem – CSR Espanol 1:5”; bylo BRAK WYNIKU, oczekiwane TRAFIONY (kupon LVBET 69619908: noga wygrana)."""
import pandas as pd

import dopasuj
import dzienniki
import sporty

D = '2026-10-06'


def _W(pilka=(), inne=()):
    p = pd.DataFrame([dict(d=pd.Timestamp(d), h=h, a=a, g=g, ga=ga, hg=None, ha=None, zr=zr) for d, h, a, g, ga, zr in pilka],
                     columns=['d', 'h', 'a', 'g', 'ga', 'hg', 'ha', 'zr'])
    i = pd.DataFrame([dict(d=pd.Timestamp(d), sport=s, h=h, a=a, pg=pg, pa=pa, ot=ot) for d, s, h, a, pg, pa, ot in inne],
                     columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot'])
    return dict(pilka=p, inne=i, tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


def test_ehc_to_czlon_ogolny_hokej():
    W = _W(inne=[(D, 'hokej', 'Visp', 'Olten', 11, 2, 0), (D, 'hokej', 'Basel', 'GCK Lions', 3, 2, 0)])
    r = dict(sport='hokej', zdarzenie='EHC Visp - EHC Olten', rynek='Zwyciezca 1', data=D, uwaga='mecz 2026-10-06 19:30')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '11:2')
    assert sporty.resolve('EHC Visp', {'Visp', 'Olten'}, 'hokej') == 'Visp'
    # czlon rozrozniajacy dalej chroniony („Independiente Yumbo” -> „Independiente” jak dotad odrzucone)
    assert sporty.resolve('Independiente Yumbo', {'Independiente', 'Visp'}, 'hokej') is None


def test_kotwica_z_inicjalem_i_czlonem_ogolnym(monkeypatch):
    import typuj
    monkeypatch.delitem(typuj.ALIASES, typuj.norm('Club Leandro Niceforo Alem'), raising=False)   # sama kotwica, bez aliasu
    W = _W(pilka=[(D, 'Leandro N. Alem', 'Centro Español', 1, 5, '365'), (D, 'Leandro N. Alem', 'CSR Espanol', 1, 5, 'fs'),
                  (D, 'Claypole', 'Deportivo Espanol', 1, 1, '365')])
    r = dict(sport='pilka', zdarzenie='Club Leandro Niceforo Alem - Centro SR Espanol', rynek='X2', data=D, uwaga='mecz 2026-10-06 19:00')
    stan, wyn, uw = dzienniki.rozlicz_noge(r, W)
    assert (stan, wyn) == ('TRAFIONY', '1:5') and 'po jednej druzynie' in uw


def test_czlony_zawarte_nie_zgaduje():
    cz = dzienniki._czlony_zawarte
    assert cz('Club Leandro Niceforo Alem', 'Leandro N. Alem')
    assert not cz('Club Leandro Niceforo Alem', 'Leandro Alem Norte')   # „Niceforo” bez odpowiednika (ani czlon, ani inicjal)
    assert not cz('FC Club', 'Real Club')                                 # same czlony ogolne — brak wspolnego czlonu w calosci
    assert not cz('Leandro N. Alem', 'Leandro N. Alem (W)')               # rozne znaczniki


def test_aliasy_auto_pamietaja_poprzednie_dni(tmp_path):
    plik = tmp_path / 'aliasy_auto.csv'
    kol = ['modul', 'nazwa', 'cel', 'uzasadnienie', 'data']
    pd.DataFrame([['typuj', 'Club Leandro Niceforo Alem', 'Leandro N. Alem', 'nauka', '2026-10-06'],
                  ['typuj', 'Stary Klub', 'Stary', 'nauka', '2026-09-01'],          # starszy niz DNI_PAMIECI — wypada
                  ['sporty', 'EHC Visp', 'Visp', 'nauka', '2026-10-06']], columns=kol).to_csv(plik, index=False)
    nowe = pd.DataFrame([['sporty', 'EHC Visp', 'EHC Visp', 'nauka', '2026-10-07']], columns=kol)
    s = dopasuj._stare_aliasy(str(plik), nowe, '2026-10-07')
    assert list(s.nazwa) == ['Club Leandro Niceforo Alem']        # dzisiejszy dowod wygrywa przy tej samej nazwie
    assert dopasuj._stare_aliasy(str(tmp_path / 'brak.csv'), nowe, '2026-10-07').empty
