"""RuStore (владелец 20.11: модерация отклонила APK за REQUEST_INSTALL_PACKAGES; «третья сборка — можно, если не замедлит
сборки»). build_apk.sh собирает и третью: Dewiar-X-store.apk — как основная, но без самообновления (нет разрешения ставить
пакеты и UpdateProvider), с меткой pro.dewiar.store; приложение по ней само обновлений не ищет — обновляет магазин."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


sh = (ROOT / "android/tools/build_apk.sh").read_text(encoding="utf-8")
py = re.search(r"<<'PY'\n(.*?)\nPY\n", sh, re.S).group(1)
tmp = Path(tempfile.mkdtemp())
r = subprocess.run([sys.executable, "-c", py, str(ROOT / "android/AndroidManifest.xml"), str(tmp / "base.xml"), str(tmp / "store.xml")],
                   capture_output=True, text=True)
ok(r.returncode == 0, "манифесты собираются " + r.stderr[-200:])
full = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
base, store = (tmp / "base.xml").read_text(encoding="utf-8"), (tmp / "store.xml").read_text(encoding="utf-8")
ok("REQUEST_INSTALL_PACKAGES" in base and "UpdateProvider" in base, "основная — с самообновлением, как раньше")
ok("REQUEST_INSTALL_PACKAGES" not in store and "UpdateProvider" not in store and ".Hands" not in store, "для магазинов — без самообновления и без «рук»")
ok('<meta-data android:name="pro.dewiar.store" android:value="1"/>' in store and store.count("</application>") == 1, "метка сборки для магазинов")
ok(len(store.splitlines()) >= len(full.splitlines()) - 12, "остальное — то же")
ok('for V in base hands store; do' in sh and 'Dewiar-$VER-store.apk' in sh and '"$B/base-store.apk"' in sh, "три APK одной подписью")
br = (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
ok('.put("store", store())' in br and 'ai.metaData.get("pro.dewiar.store")' in br, "приложение знает, что оно из магазина")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("if (inf.store) {" in app and "Обновления приходят через магазин приложений" in app, "из магазина — само обновлений не ищет")
fb = (ROOT / "tools/files_branch.sh").read_text(encoding="utf-8")
ok('"$DIR"/Dewiar-*.apk' in fb and "store" in fb, "папка выпуска: и сборка для магазинов")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
