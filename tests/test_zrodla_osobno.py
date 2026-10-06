"""06.10.2026 — rozliczenie nog, gdy ten sam klub ma w puli wynikow kilka nazw z ROZNYCH zrodel (365 / Flashscore)."""
import pandas as pd

import dzienniki

D = '2026-10-05'


def _W(*mecze, zrodla=True):
    w = pd.DataFrame([dict(d=pd.Timestamp(d), h=h, a=a, g=g, ga=ga, hg=None, ha=None, zr=zr) for d, h, a, g, ga, zr in mecze])
    if not zrodla: w = w.drop(columns='zr')
    return dict(pilka=w, inne=pd.DataFrame(columns=['d', 'sport', 'h', 'a', 'pg', 'pa', 'ot']),
                tenis=pd.DataFrame(columns=['d', 'w', 'l', 'score']))


# paczka 06.10 (okno 04–06.10): 365 „Riestra – Central Córdoba SdE”, Flashscore „Dep. Riestra – Central Cordoba”,
# a w oknie jest tez Central Cordoba de Rosario (Primera C, 04.10) — w obu zrodlach
RIESTRA = [('2026-10-05', 'Riestra', 'Central Córdoba SdE', 1, 1, '365'),
           ('2026-10-05', 'Dep. Riestra', 'Central Cordoba', 1, 1, 'fs'),
           ('2026-10-04', 'Central Cordoba de Rosario', 'Yupanqui', 1, 0, '365'),
           ('2026-10-04', 'Central Cordoba', 'Yupanqui', 1, 0, 'fs')]


def test_ten_sam_klub_pod_dwiema_nazwami_z_dwoch_zrodel():
    # ako_log 05.10 AKOP-1800-2: „Deportivo Riestra - CA Central Cordoba” U3.5 — bylo „nie dopasowano: Deportivo Riestra”
    r = dict(sport='pilka', zdarzenie='Deportivo Riestra - CA Central Cordoba', rynek='U3.5', data=D, uwaga='')
    stan, wyn, uw = dzienniki.rozlicz_noge(r, _W(*RIESTRA))
    assert (stan, wyn) == ('TRAFIONY', '1:1')
    assert 'osobno' in uw                                        # w uwadze: dopasowanie do sprawdzenia
    # bez informacji o zrodle (wspolna pula) — jak dotad: nie zgadujemy
    assert dzienniki.rozlicz_noge(r, _W(*RIESTRA, zrodla=False))[0] == 'BRAK WYNIKU'


def test_zrodla_z_roznym_wynikiem_nie_rozstrzygaja():
    # ako_log 20.09: „CD Cuenca - Mushuc Runa” — 365 „Deportivo Cuenca”, Flashscore „Dep. Cuenca”; oba zrodla znajduja mecz
    r = dict(sport='pilka', zdarzenie='CD Cuenca - Mushuc Runa (23:00)', rynek='U3.5', data='2026-09-20', uwaga='')
    zgodne = _W(('2026-09-20', 'Deportivo Cuenca', 'Mushuc Runa', 1, 1, '365'), ('2026-09-20', 'Dep. Cuenca', 'Mushuc Runa', 1, 1, 'fs'))
    stan, wyn, uw = dzienniki.rozlicz_noge(r, zgodne)
    assert (stan, wyn) == ('TRAFIONY', '1:1') and 'zrodle 365/fs osobno' in uw
    rozne = _W(('2026-09-20', 'Deportivo Cuenca', 'Mushuc Runa', 1, 1, '365'), ('2026-09-20', 'Dep. Cuenca', 'Mushuc Runa', 3, 1, 'fs'))
    stan, _, uw = dzienniki.rozlicz_noge(r, rozne)
    assert stan == 'BRAK WYNIKU' and 'rozne wyniki' in uw


def test_wyniki_pilka_zapisuje_zrodlo_z_nazwy_pliku(tmp_path):
    z = tmp_path / 'zewn'
    z.mkdir()
    k = 'data,sport,kraj,liga,runda,gosp,gosc,wg,wa,hg,ha,zw,x\n'
    (z / 'wyniki_365_pilka_2026-10.csv').write_text(k + f'{D},football,Argentina,Liga Profesional,Round,Riestra,Central Córdoba SdE,1,1,,,3,\n')
    (z / 'wyniki_fs_pilka_2026-10.csv').write_text(k + f'{D},football,ARGENTINA,Liga Profesional,,Dep. Riestra,Central Cordoba,1,1,0,0,3,\n')
    w = dzienniki.wyniki_pilka(str(tmp_path))
    assert dict(zip(w.h, w.zr)) == {'Riestra': '365', 'Dep. Riestra': 'fs'}


def test_alias_literowki_365_tatran():
    # ako_log 05.10 AKOP-1500-1: „Tatran Liptovsky Mikulas - STK Samorin” O1.5; 365 pisze „Taran…”, Flashscore „L. Mikulas”
    W = _W(('2026-10-05', 'Taran Liptovsky Mikulas', 'STK Samorin', 2, 0, '365'),
           ('2026-10-05', 'L. Mikulas', 'Samorin', 2, 0, 'fs'))
    r = dict(sport='pilka', zdarzenie='Tatran Liptovsky Mikulas - STK Samorin', rynek='O1.5', data=D, uwaga='')
    assert dzienniki.rozlicz_noge(r, W)[:2] == ('TRAFIONY', '2:0')
