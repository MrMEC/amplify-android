#!/bin/bash
# Downloads the animated GIFs used as the default Zen preset artwork and embeds them in the app.
# Any GIF that fails to download is skipped (that preset keeps its painted scene).
cd "$(dirname "$0")/.."
mkdir -p www/zen/art
LIST="storm|https://i.pinimg.com/originals/2a/69/ab/2a69abcd11ecc2fed2f24c9212abfee7.gif
lighthouse|https://cdn.pixabay.com/animation/2024/05/27/21/55/21-55-52-574_512.gif
deep-sleep|https://i.makeagif.com/media/12-27-2023/QZRRMz.gif
cozy-cabin|https://i.makeagif.com/media/9-03-2020/uTRhF8.gif
forest-stream|https://i.pinimg.com/originals/8f/b1/a6/8fb1a65ac9a08636be60455ce87f0ca6.gif
rainy-night|https://i.pinimg.com/originals/e2/89/1a/e2891a60b8c9b60ead0a617eb26411b4.gif
campfire|https://i.pinimg.com/originals/6a/ad/41/6aad4128ff7d3c11406835667101ef82.gif
seaside-dawn|https://giffiles.alphacoders.com/457/4571.gif
misty-morning|https://i.pinimg.com/originals/a4/35/23/a43523b94c546f6a8a06c1a24e66152c.gif
deep-blue|https://i.pinimg.com/originals/cc/d0/db/ccd0dbb7eeb48aa6790ec216c543da89.gif"
OK=""
while IFS='|' read -r id url; do
  f="www/zen/art/$id.gif"
  if [ ! -s "$f" ]; then
    curl -sSL -m 60 --retry 2 -A "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36" -e "https://www.google.com/" -o "$f" "$url" || rm -f "$f"
  fi
  if [ -s "$f" ] && [ "$(head -c 3 "$f")" = "GIF" ]; then OK="$OK'$id',"; echo "ok $id $(stat -c%s "$f")"; else rm -f "$f"; echo "FAILED $id"; fi
done <<< "$LIST"
OK="${OK%,}"
sed -i "s/var ZEN_BUNDLED = \[[^]]*\];/var ZEN_BUNDLED = [$OK];/" www/index.html
grep -n "var ZEN_BUNDLED" www/index.html
