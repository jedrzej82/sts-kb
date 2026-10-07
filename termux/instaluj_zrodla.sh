#!/data/data/com.termux/files/usr/bin/bash
# Jednorazowa instalacja dodatkowych zrodel (termux/zrodla.py) na telefonie — 03.10.2026.
#   curl -fsSL https://raw.githubusercontent.com/jedrzej82/sts-kb/main/termux/instaluj_zrodla.sh | bash
# Tworzy ~/zrodla.sh (pobiera najnowszy zrodla.py z main, uruchamia, wysyla wyniki na Dysk tym samym rclone co kursy)
# i dopisuje do crontaba uruchomienie 10 min po kursach (11:40, 14:40, 17:40, 20:40) oraz co godzine 12:20–21:20 sam FotMob
# (sklady przed meczem). Ponowne uruchomienie nic nie dubluje.
set -e
H=/data/data/com.termux/files/home
cat > "$H/zrodla.sh" <<'SKRYPT'
#!/data/data/com.termux/files/usr/bin/bash
export PATH=/data/data/com.termux/files/usr/bin:/system/bin:$PATH
cd /data/data/com.termux/files/home
curl -fsSL https://raw.githubusercontent.com/jedrzej82/sts-kb/main/termux/zrodla.py -o zrodla.py
python zrodla.py "$@"
rclone move /sdcard/Download/ gdrive:zrodla/ --include "zrodla_*.zip"   # zapas, gdy zrodla.py nie wyslal sam
SKRYPT
chmod +x "$H/zrodla.sh"
LINIA="40 11,14,17,20 * * * PATH=/data/data/com.termux/files/usr/bin:/system/bin $H/zrodla.sh >> $H/zrodla.log 2>&1"
# 07.10.2026: sklady — kluby podaja je ok. 60 min przed meczem, a przebiegi o :40 co 3 h trafialy zwykle przed tym
# (wiekszosc to „lastStarting11”, sklad z poprzedniego meczu). Co godzine 12:20–21:20 tylko FotMob (mecze w ciagu 3,5 h).
LINIA2="20 12-21 * * * PATH=/data/data/com.termux/files/usr/bin:/system/bin $H/zrodla.sh --tylko fotmob --budzet-min 6 >> $H/zrodla.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'zrodla.sh' ; echo "$LINIA" ; echo "$LINIA2" ) | crontab -
echo "OK: ~/zrodla.sh gotowy, crontab:"; crontab -l
