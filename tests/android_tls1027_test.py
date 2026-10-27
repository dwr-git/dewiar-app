"""YouTube 27.10: своё подключение на телефоне — «Trust anchor for certification path not found», когда у своего сервера
сертификат собственного выпуска. Приложение доверяет и сертификатам, которые человек сам поставил в телефон
(res/xml/network_security.xml), а ошибка объясняет словами, где их поставить."""
import os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


x = (ROOT / "android/res/xml/network_security.xml").read_text(encoding="utf-8")
ok('<certificates src="system"/>' in x and '<certificates src="user"/>' in x and 'cleartextTrafficPermitted="true"' in x,
   "доверие: системные и поставленные человеком центры; http в своей сети — как было")
man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
ok('android:networkSecurityConfig="@xml/network_security"' in man, "манифест подключает настройку")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
i = app.index("function netErr"); j = app.index("\n}\n", i) + 2
js = "const HOME_URL = /192\\.168\\./;\n" + app[i:j] + "\nconsole.log(netErr('javax.net.ssl.SSLHandshakeException: java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.', 'https://my.server/v1'));"
r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
ok("Сертификат ЦС" in r.stdout and "Шифрование и учётные данные" in r.stdout, f"ошибка — словами, где поставить сертификат: {r.stdout.strip()[:120]!r} {r.stderr[-200:]}")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
