"""Радио при погасшем экране (30.10, отзыв: «Понравилось использовать в машине, но я включаю радио, и как только экран
гаснет — все гаснет, можно ли это доработать?»). Радио играло в MediaPlayer без службы переднего плана — Android усыплял
приложение вместе с экраном. Теперь RadioService: служба mediaPlayback с уведомлением («Пауза» / «Играть», «Стоп»),
медиасессия (кнопки машины по Bluetooth, наушников, экрана блокировки; название станции — на экране машины), Wi-Fi не
засыпает, пока играет. Java проверяется по исходникам и собранному манифесту (сборка — android/tools/build_apk.sh)."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


A = ROOT / "android/src/pro/dewiar/app"
man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
svc = (A / "RadioService.java").read_text(encoding="utf-8")
radio = (A / "Radio.java").read_text(encoding="utf-8")
ok('<service android:name=".RadioService" android:exported="false" android:foregroundServiceType="mediaPlayback"/>' in man
   and "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" in man, "манифест: служба mediaPlayback и разрешение (Android 14)")
ok(man.count('foregroundServiceType="camera|microphone|location"') == 1, "метка типа службы «Близких» (fgs_type.py) — по-прежнему одна")
ok("RadioService.sync(c, state, name, by);" in radio[radio.index("private void emit()"):radio.index("private void applyVolume")],
   "каждое состояние радио (подключаюсь, играет, пауза, стоп, ошибка) — в службу")
ok("static synchronized Radio current()" in radio, "кнопки уведомления и машины находят тот же проигрыватель")
sync = svc[svc.index("static void sync("):svc.index("@Override public IBinder")]
ok('"stopped".equals(state) || "error".equals(state)' in sync and "stopService" in sync and "startService(i)" in sync and "startForegroundService" in sync,
   "стоп и ошибка — служба уходит; иначе — запуск (из фона — startForegroundService)")
show = svc[svc.index("private void show("):svc.index("/** Медиасессия")]
ok("startForeground(NOTE, n)" in show and "stopForeground(false)" in show and "setOngoing(hold)" in show and "setDeleteIntent(act(A_STOP" in show
   and "(paused && !byUser)" in show and 'byUser = "user".equals(by)' in svc,
   "играет — передний план; пауза человеком — уведомление остаётся (смахнули — стоп); пауза на звонок — передний план держим, после звонка радио продолжит")
ok('"Пауза"' in show and '"Играть"' in show and '"Стоп"' in show and "MediaStyle" in show and "setMediaSession" in show,
   "кнопки «Пауза» / «Играть» и «Стоп», вид медиаплеера")
ses = svc[svc.index("private void session("):svc.index("@SuppressWarnings(\"deprecation\")\n    private static void setFlags")]
ok(all(x in ses for x in ("onPlay()", "onPause()", "onStop()", "METADATA_KEY_TITLE", "STATE_PLAYING", "STATE_BUFFERING", "setActive(")),
   "медиасессия: кнопки машины и наушников, название станции, «играет / подключаюсь / пауза»")
ok("createWifiLock" in svc and "wifi(true)" in show and "wifi(false)" in svc[svc.index("public void onDestroy"):], "Wi-Fi держим, пока играет; отпускаем на паузе и при остановке")
ok("START_NOT_STICKY" in svc and "IMPORTANCE_LOW" in svc, "служба не поднимается сама после гибели процесса; канал «Радио» тихий")
on_start = svc[svc.index("public int onStartCommand"):svc.index("private PendingIntent act")]
ok("A_PLAY.equals(a)" in on_start and "r.resume()" in on_start and "A_PAUSE.equals(a)" in on_start and "r.pause()" in on_start and "r.stop()" in on_start,
   "кнопки уведомления — те же resume / pause / stop, что голосом")
main = (A / "MainActivity.java").read_text(encoding="utf-8")
ok("if (radio != null && isFinishing()) radio.stop();" in main, "закрыли приложение — радио и служба тоже уходят (как было)")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
