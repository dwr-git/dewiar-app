package pro.dewiar.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Vibrator;
import android.webkit.JavascriptInterface;
import android.widget.Toast;
import java.io.File;
import java.io.FileInputStream;
import org.json.JSONArray;
import org.json.JSONObject;

/** Мост WebView → телефон: всё, что интерфейс может попросить, — window.Dewiar.<метод>(…) в app.js (там же заглушка
 *  с теми же именами для проверки в браузере — новый метод добавляй в обе стороны). Методы зовутся из потока JavaBridge,
 *  не из главного: что трогает экран — через runOnUiThread. Короткое отвечает сразу строкой (JSON — строкой, "" — нет),
 *  долгое (сеть, слух, голос, радио) — позже событиями window.N.ev({type, …}) через MainActivity.event. */
public final class Bridge {
    private final MainActivity a;
    private final SharedPreferences prefs;

    Bridge(MainActivity a) {
        this.a = a;
        this.prefs = a.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
    }

    // ---------- общее ----------

    /** Версия, устройство, есть ли распознавание и синтез речи и текст последнего падения (crash.txt пишет App.java). */
    @JavascriptInterface public String info() {
        try {
            String crash = "";
            File f = new File(a.getFilesDir(), "crash.txt");
            if (f.exists()) crash = Net.readAll(new FileInputStream(f));
            return new JSONObject().put("version", BuildInfo.VERSION).put("sdk", Build.VERSION.SDK_INT)
                    .put("android", Build.VERSION.RELEASE).put("device", Build.MANUFACTURER + " " + Build.MODEL)
                    .put("recognizer", Speech.systemAvailable(a)).put("tts", a.tts.ready()).put("crash", crash).toString();
        } catch (Exception e) { return "{}"; }
    }

    // ---------- обновление внутри приложения (Update.java) ----------
    @JavascriptInterface public void updateGet(String url, String sha256) { Update.download(a, url, sha256); }
    @JavascriptInterface public String updateInstall() { return Update.install(a); }
    @JavascriptInterface public boolean updateCanInstall() { return Update.canInstall(a); }
    @JavascriptInterface public boolean updateReady() { return Update.apk(a).isFile(); }
    /** «Загрузки» системы — убрать старые Dewiar-….apk, скачанные раньше браузером. */
    @JavascriptInterface public boolean openDownloads() {
        try { a.startActivity(new Intent("android.intent.action.VIEW_DOWNLOADS").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return true; }
        catch (Exception e) { return false; }
    }

    // ---------- «освободи место» (18.10): системное «Хранилище», размер Dewiar и свой кэш ----------
    private static long du(File f) {
        if (f == null || !f.exists()) return 0;
        if (f.isFile()) return f.length();
        long n = 0; File[] l = f.listFiles();
        if (l != null) for (File x : l) n += du(x);
        return n;
    }
    /** Сколько занимает Dewiar: {cache, data} в байтах (кэш — голоса, страницы, скачанное обновление; данные — заметки,
     *  настройки, журнал). */
    @JavascriptInterface public String appSize() {
        try {
            long cache = du(a.getCacheDir()) + du(a.getExternalCacheDir());
            long data = du(a.getFilesDir()) + du(new File(a.getApplicationInfo().dataDir, "app_webview")) + du(a.getExternalFilesDir(null));
            return new JSONObject().put("cache", cache).put("data", data).toString();
        } catch (Exception e) { return "{}"; }
    }
    private static void wipe(File d) {
        File[] l = d == null ? null : d.listFiles();
        if (l != null) for (File x : l) { if (x.isDirectory()) wipe(x); //noinspection ResultOfMethodCallIgnored
            x.delete(); }
    }
    /** Почистить свой кэш (голоса заново скачаются при надобности). -> сколько байт освобождено. */
    @JavascriptInterface public long clearOwnCache() {
        long before = du(a.getCacheDir()) + du(a.getExternalCacheDir());
        wipe(a.getCacheDir()); wipe(a.getExternalCacheDir());
        a.runOnUiThread(new Runnable() { @Override public void run() { try { a.clearWebCache(); } catch (Throwable ignored) { } } });
        return Math.max(0, before - du(a.getCacheDir()) - du(a.getExternalCacheDir()));
    }
    /** Системное «Хранилище»: Android сам покажет, что занимает место, и предложит очистку. */
    @JavascriptInterface public boolean openStorage() {
        try { a.startActivity(new Intent("android.settings.INTERNAL_STORAGE_SETTINGS").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return true; }
        catch (Exception e) {
            try { a.startActivity(new Intent(android.provider.Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return true; }
            catch (Exception x) { return false; }
        }
    }

    /** Сила телефона для «лёгкого режима» (app.js liteWhy): память, «маломощный» по мнению Android, ядра, экономия батареи. */
    @JavascriptInterface public String deviceClass() {
        try {
            android.app.ActivityManager am = (android.app.ActivityManager) a.getSystemService(Context.ACTIVITY_SERVICE);
            android.app.ActivityManager.MemoryInfo mi = new android.app.ActivityManager.MemoryInfo();
            am.getMemoryInfo(mi);
            android.os.PowerManager pm = (android.os.PowerManager) a.getSystemService(Context.POWER_SERVICE);
            return new JSONObject().put("ram_mb", mi.totalMem / (1024 * 1024)).put("low_ram", am.isLowRamDevice())
                    .put("cores", Runtime.getRuntime().availableProcessors()).put("power_save", pm != null && pm.isPowerSaveMode()).toString();
        } catch (Exception e) { return "{}"; }
    }

    @JavascriptInterface public void clearCrash() {
        //noinspection ResultOfMethodCallIgnored
        new File(a.getFilesDir(), "crash.txt").delete();
    }

    /** Что пришло до загрузки страницы (кнопка помощника, ярлык, ссылка dewiar://, «Поделиться») — забрать один раз. */
    @JavascriptInterface public String takeIntent() { return a.takePending(); }

    // настройки и состояние интерфейса: ключ → строка в SharedPreferences "dewiar" (в браузерной заглушке app.js — localStorage)
    @JavascriptInterface public String pref(String key) { return prefs.getString(key, ""); }

    @JavascriptInterface public void setPref(String key, String value) {
        prefs.edit().putString(key, value).apply();
        if ("look_body".equals(key) || "widget_look".equals(key)) CaptureWidget.refresh(a);   // сменили тему или вид значка — значок «Записать» на экране тоже
    }

    @JavascriptInterface public void toast(final String t) {
        a.runOnUiThread(new Runnable() { @Override public void run() { Toast.makeText(a, t, Toast.LENGTH_SHORT).show(); } });
    }

    @JavascriptInterface public void vibrate(int ms) {
        try { ((Vibrator) a.getSystemService(Context.VIBRATOR_SERVICE)).vibrate(Math.max(10, Math.min(ms, 1000))); } catch (Throwable ignored) { }
    }

    @JavascriptInterface public void share(String text) {
        Intent i = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text);
        a.startActivity(Intent.createChooser(i, "Отправить").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
    }

    /** Цвет строки состояния и панели жестов под тему оформления (светлые темы — тёмные значки). color — "#rrggbb". */
    @JavascriptInterface public void bars(final String color, final boolean light) {
        a.runOnUiThread(new Runnable() { @Override public void run() {
            try {
                int c = android.graphics.Color.parseColor(color);
                android.view.Window w = a.getWindow();
                w.setStatusBarColor(c);
                w.setNavigationBarColor(c);
                a.web.setBackgroundColor(c);
                android.view.View v = w.getDecorView();
                int f = v.getSystemUiVisibility() & ~(0x2000 | 0x10);   // LIGHT_STATUS_BAR (API 23), LIGHT_NAVIGATION_BAR (API 26)
                if (light) f |= 0x2000 | (Build.VERSION.SDK_INT >= 26 ? 0x10 : 0);
                v.setSystemUiVisibility(f);
            } catch (Throwable e) { }
        } });
    }

    /** «Близкие» в фоне (CloseWatch): что спрашивать у облака — {base, token, link, cursor} строкой JSON; "" — выключить. */
    @JavascriptInterface public void closeWatch(String json) {
        prefs.edit().putString("close_watch", json == null ? "" : json).apply();
        CloseWatch.schedule(a, json != null && !json.isEmpty());
        CloseLive.apply(a);
    }

    /** «Близкие» на связи, когда приложение закрыто (служба CloseLive): включить или выключить. */
    @JavascriptInterface public void closeLive(boolean on) {
        prefs.edit().putBoolean("close_live", on).apply();
        CloseLive.apply(a);
    }

    /** Не усыпляет ли система Dewiar в фоне (экономия батареи). До Android 6 — не усыпляет. */
    @JavascriptInterface public boolean batteryOk() {
        if (Build.VERSION.SDK_INT < 23) return true;
        try {
            android.os.PowerManager pm = (android.os.PowerManager) a.getSystemService(Context.POWER_SERVICE);
            return (Boolean) android.os.PowerManager.class.getMethod("isIgnoringBatteryOptimizations", String.class).invoke(pm, a.getPackageName());
        } catch (Throwable e) { return true; }
    }

    /** Попросить систему не усыплять Dewiar: окно Android «Разрешить работу в фоне?». Не вышло — настройки батареи. */
    @JavascriptInterface public void askBattery() {
        a.runOnUiThread(new Runnable() { @Override public void run() {
            try {
                a.startActivity(new Intent("android.settings.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS", android.net.Uri.parse("package:" + a.getPackageName())));
            } catch (Throwable e) {
                try { a.startActivity(new Intent("android.settings.IGNORE_BATTERY_OPTIMIZATION_SETTINGS")); } catch (Throwable ignored) { }
            }
        } });
    }

    // ---------- звук напоминаний (Sounds) ----------
    private android.media.MediaPlayer trying;
    private String tryingId = "";

    /** Выбранный звук и название своего файла: {"id": "chime", "custom": "моя мелодия.mp3"}. */
    @JavascriptInterface public String alarmSound() {
        try {
            return new JSONObject().put("id", Sounds.current(a)).put("custom", Sounds.customFile(a).isFile() ? prefs.getString("alarm_custom_name", "Свой звук") : "").toString();
        } catch (Exception e) { return "{}"; }
    }

    @JavascriptInterface public boolean alarmSoundSet(String id) {
        if (Sounds.res(id) == 0 && !"system".equals(id) && !("custom".equals(id) && Sounds.customFile(a).isFile())) return false;
        Sounds.set(a, id);
        return true;
    }

    /** Послушать: играет один раз; тот же звук ещё раз — стоп. -> играет ли сейчас. */
    @JavascriptInterface public synchronized boolean alarmSoundTry(String id) {
        boolean same = id.equals(tryingId) && trying != null;
        try { if (trying != null) { trying.stop(); trying.release(); } } catch (Throwable ignored) { }
        trying = null; tryingId = "";
        if (same || id.isEmpty()) return false;
        trying = Sounds.play(a, id, false, 0.8f);
        if (trying == null) return false;
        tryingId = id;
        final android.media.MediaPlayer p = trying;
        p.setOnCompletionListener(new android.media.MediaPlayer.OnCompletionListener() { @Override public void onCompletion(android.media.MediaPlayer m) {
            synchronized (Bridge.this) { if (trying == p) { trying = null; tryingId = ""; } }
            try { m.release(); } catch (Throwable ignored) { }
            a.event("sound_end", new JSONObject());
        } });
        return true;
    }

    /** Свой звук: файл из выбора (base64) → files/alarm_custom, сразу выбран. Не звучит (не аудио) — ошибка текстом, "" — ок. */
    @JavascriptInterface public String alarmSoundCustom(String b64, String name) {
        try {
            byte[] data = android.util.Base64.decode(b64, android.util.Base64.DEFAULT);
            if (data.length > 12 * 1024 * 1024) return "файл больше 12 МБ";
            java.io.File tmp = new java.io.File(a.getFilesDir(), "alarm_custom.new");
            java.io.FileOutputStream o = new java.io.FileOutputStream(tmp);
            o.write(data); o.close();
            android.media.MediaPlayer test = new android.media.MediaPlayer();
            try { test.setDataSource(tmp.getAbsolutePath()); test.prepare(); }
            catch (Throwable e) { //noinspection ResultOfMethodCallIgnored
                tmp.delete(); return "этот файл телефон не может проиграть"; }
            finally { try { test.release(); } catch (Throwable ignored) { } }
            java.io.File dst = Sounds.customFile(a);
            //noinspection ResultOfMethodCallIgnored
            dst.delete();
            if (!tmp.renameTo(dst)) return "не удалось сохранить файл";
            prefs.edit().putString("alarm_custom_name", name == null || name.isEmpty() ? "Свой звук" : name).apply();
            Sounds.set(a, "custom");
            return "";
        } catch (Throwable e) { return "не удалось сохранить файл"; }
    }

    /** Скопировать текст в буфер обмена (кнопка «Копировать» под ответом). -> удалось ли. */
    @JavascriptInterface public boolean copy(final String text) {
        final boolean[] ok = {false};
        final java.util.concurrent.CountDownLatch done = new java.util.concurrent.CountDownLatch(1);
        a.runOnUiThread(new Runnable() { @Override public void run() {
            try {
                android.content.ClipboardManager cm = (android.content.ClipboardManager) a.getSystemService(android.content.Context.CLIPBOARD_SERVICE);
                cm.setPrimaryClip(android.content.ClipData.newPlainText("Dewiar", text));
                ok[0] = true;
            } catch (Throwable e) { ok[0] = false; }
            done.countDown();
        } });
        try { done.await(1, java.util.concurrent.TimeUnit.SECONDS); } catch (InterruptedException e) { }
        return ok[0];
    }

    /** Текст — прямо в нужный мессенджер (MAX, Telegram…): получателя выбирает человек. Нет приложения — false. */
    @JavascriptInterface public boolean shareTo(String pkg, String text) {
        try {
            Intent i = new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
                    .setPackage(pkg).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            a.startActivity(i);
            return true;
        } catch (Throwable e) { return false; }
    }

    @JavascriptInterface public void keepScreen(boolean on) { a.keepScreen(on); }
    @JavascriptInterface public void immersive(boolean on) { a.immersive(on); }

    @JavascriptInterface public boolean has(String perm) { return a.has(perm); }

    /** Открыть экран настроек Android: assistant — помощник по умолчанию, alarms — точные будильники, tts — синтез речи,
     *  voice — голосовой ввод, иначе — страница приложения (там уведомления и разрешения). Пробует по порядку: у разных
     *  производителей нет то одного, то другого экрана. false — не открылся ни один. */
    @JavascriptInterface public boolean openSettings(String what) {
        String[] acts;
        if ("assistant".equals(what)) acts = new String[]{"android.settings.MANAGE_DEFAULT_APPS_SETTINGS", "android.settings.VOICE_INPUT_SETTINGS"};
        else if ("alarms".equals(what)) acts = new String[]{"android.settings.REQUEST_SCHEDULE_EXACT_ALARM"};
        else if ("tts".equals(what)) acts = new String[]{"com.android.settings.TTS_SETTINGS"};
        else if ("voice".equals(what)) acts = new String[]{"android.settings.VOICE_INPUT_SETTINGS"};
        else if ("accessibility".equals(what)) acts = new String[]{"android.settings.ACCESSIBILITY_SETTINGS"};
        // экраны для «включи Bluetooth» и т. п. (отзыв 19.10, Android 13: «попросил включить блютуз, а она на вкладку вайфай»):
        // сам переключить их Android приложениям не даёт — открываем нужный экран сразу, дальше руки или человек жмут переключатель.
        // panel.action.* — шторка с переключателем (Android 10+), на старых — обычный экран настроек
        else if ("bluetooth".equals(what)) acts = new String[]{"android.settings.BLUETOOTH_SETTINGS"};
        else if ("wifi".equals(what)) acts = new String[]{"android.settings.panel.action.WIFI", "android.settings.WIFI_SETTINGS"};
        else if ("internet".equals(what)) acts = new String[]{"android.settings.panel.action.INTERNET_CONNECTIVITY", "android.settings.WIRELESS_SETTINGS"};
        else if ("nfc".equals(what)) acts = new String[]{"android.settings.panel.action.NFC", "android.settings.NFC_SETTINGS"};
        else if ("airplane".equals(what)) acts = new String[]{"android.settings.AIRPLANE_MODE_SETTINGS", "android.settings.WIRELESS_SETTINGS"};
        else if ("display".equals(what)) acts = new String[]{"android.settings.DISPLAY_SETTINGS"};
        else if ("sound".equals(what)) acts = new String[]{"android.settings.panel.action.VOLUME", "android.settings.SOUND_SETTINGS"};
        else if ("data".equals(what)) acts = new String[]{"android.settings.DATA_ROAMING_SETTINGS", "android.settings.WIRELESS_SETTINGS"};
        else if ("hotspot".equals(what)) acts = new String[]{"android.settings.WIRELESS_SETTINGS"};
        else if ("location".equals(what)) acts = new String[]{"android.settings.LOCATION_SOURCE_SETTINGS"};
        else acts = new String[]{"android.settings.APPLICATION_DETAILS_SETTINGS"};
        for (String act : acts) {
            try {
                Intent i = new Intent(act).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                if (act.endsWith("APPLICATION_DETAILS_SETTINGS") || act.endsWith("SCHEDULE_EXACT_ALARM"))
                    i.setData(android.net.Uri.parse("package:" + a.getPackageName()));
                a.startActivity(i);
                return true;
            } catch (Throwable ignored) { }
        }
        return false;
    }

    // ---------- руки в других приложениях (Hands.java — служба специальных возможностей) ----------

    /** "on" — служба подключена; "pending" — включена в настройках, Android её ещё подключает; "" — выключена. */
    /** "on" — руки работают; "pending" — включены в настройках, подключаются; "" — выключены; "none" — в этой сборке их нет
     *  (основной Dewiar.apk без службы специальных возможностей: такие приложения Android при установке не с магазина
     *  блокирует или пугает предупреждением; руки — в Dewiar-hands.apk, см. android/tools/build_apk.sh). */
    @JavascriptInterface public String handsState() {
        try {
            a.getPackageManager().getServiceInfo(new android.content.ComponentName(a, Hands.class), 0);
        } catch (Exception e) { return "none"; }
        return Hands.on() ? "on" : Hands.enabledInSettings(a) ? "pending" : "";
    }

    @JavascriptInterface public String handsScreen() { return Hands.screen(); }

    @JavascriptInterface public String handsTap(int id, boolean longPress) { return Hands.tap(id, longPress); }

    @JavascriptInterface public String handsTapText(String text) { return Hands.tapText(text); }

    @JavascriptInterface public String handsType(int id, String text, boolean submit) { return Hands.type(id, text, submit); }

    @JavascriptInterface public String handsScroll(int id, String dir) { return Hands.scroll(id, dir); }

    @JavascriptInterface public String handsNav(String what) { return Hands.nav(what); }

    /** Вернуть Dewiar на экран (после работы в другом приложении). */
    @JavascriptInterface public void toFront() {
        try {
            a.startActivity(new Intent(a, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
        } catch (Throwable ignored) { }
    }

    /** Где телефон (радар «Рядом», Loc.java): ответ событием loc {lat, lon, acc, ts} или {error}. */
    @JavascriptInterface public void locate(int maxAgeSec) { Loc.once(a, Math.max(0, maxAgeSec) * 1000L, a); }

    /** Настройки местоположения системы — когда оно выключено. */
    @JavascriptInterface public boolean locSettings() {
        try { a.startActivity(new Intent(android.provider.Settings.ACTION_LOCATION_SOURCE_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return true; }
        catch (Exception e) { return false; }
    }

    /** Спросить разрешение; ответ — событием perm {name, granted}. */
    @JavascriptInterface public void perm(final String perm) {
        a.runOnUiThread(new Runnable() { @Override public void run() { a.askPermission(perm); } });
    }

    /** Сообщение ассистента в шторку — от лица текущего персонажа (Faces): заголовок — его имя, текст — «title — text». */
    @JavascriptInterface public void notify(String title, String text) {
        try {
            PendingIntent p = PendingIntent.getActivity(a, 3, new Intent(a, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            Notification.Builder b = Compat.builder(a, Compat.CH_INFO);
            String name = Faces.dress(a, b, "");
            String body = name.isEmpty() ? text : title + (text == null || text.isEmpty() ? "" : " — " + text);
            Notification n = b.setContentTitle(name.isEmpty() ? title : name).setContentText(body)
                    .setStyle(new Notification.BigTextStyle().bigText(body))
                    .setAutoCancel(true).setContentIntent(p).build();
            ((NotificationManager) a.getSystemService(Context.NOTIFICATION_SERVICE)).notify((int) (System.currentTimeMillis() % 100000), n);   // свой номер — уведомления не заменяют друг друга
        } catch (Throwable ignored) { }
    }

    // ---------- сеть ----------

    /** Запрос в обход CORS; ответ — событиями http_chunk / http_done / http_error с этим id (см. Net.java). */
    @JavascriptInterface public void http(String id, String method, String url, String headers, String body, boolean stream, int timeoutMs) {
        Net.request(id, method, url, headers, body, stream, timeoutMs, a);
    }

    @JavascriptInterface public void abort(String id) { Net.abort(id); }

    /** Прокси для серверов Dewiar — на случай, если провайдер блокирует dewiar.pro (NetProxy.java). "" — принят,
     *  иначе текст ошибки для человека. */
    @JavascriptInterface public String setProxy(String spec, String hostsCsv) {
        try { NetProxy.set(spec, hostsCsv); return ""; } catch (Throwable e) { return String.valueOf(e.getMessage()); }
    }

    // ---------- слух и голос ----------

    // события слуха: stt_start, stt_level, stt_partial, stt_end, stt_result, stt_error (Speech.java); голоса: tts_* (Tts.java)
    @JavascriptInterface public boolean recognizer() { return Speech.systemAvailable(a); }

    @JavascriptInterface public void listen(int g) { a.speech.longPause = false; a.speech.listenSystem(g); }

    /** «Удерживайте и говорите»: то же распознавание, но пауза конца фразы — подольше. */
    @JavascriptInterface public void listenHold(int g) { a.speech.longPause = true; a.speech.listenSystem(g); }

    /** Пока держат кнопку — без «тринька» распознавателя на каждом перезапуске (Speech.quiet). */
    @JavascriptInterface public void sttQuiet(boolean on) { a.speech.quiet(on); }

    @JavascriptInterface public void listenServer(int g, String url, String key, String model) { a.speech.holdRec = false; a.speech.listenServer(g, url, key, model); }

    /** «Удерживайте и говорите» через сервер: запись, пока держат, целиком — на распознавание (Speech.holdRec). */
    @JavascriptInterface public void listenServerHold(int g, String url, String key, String model) { a.speech.holdRec = true; a.speech.listenServer(g, url, key, model); }

    @JavascriptInterface public void stopListen() { a.speech.stop(); }

    /** Добавка к паузе конца фразы (0…900 мс) — app.js учит её под манеру речи человека. */
    /** Слушать микрофоном Bluetooth-наушников, когда они подключены (настройка «Микрофон наушников»). */
    @JavascriptInterface public void btMic(boolean on) { a.speech.btMic = on; if (!on) BtMic.offNow(a); }
    @JavascriptInterface public boolean btMicAvailable() { return BtMic.available(a); }
    @JavascriptInterface public void pauseExtra(int ms) { a.speech.extraMs = Math.max(0, Math.min(900, ms)); }

    @JavascriptInterface public void cancelListen() { a.speech.cancel(); }

    @JavascriptInterface public void speak(String id, String text, float rate, float pitch, String voice, boolean add) {
        a.tts.speak(id, text, rate, pitch, voice, add);
    }

    @JavascriptInterface public void speakRemote(String id, String url, String key, String body) { a.tts.speakRemote(id, url, key, body); }
    /** То же, но с запасным голосом телефона внутри очереди (fb — {text, rate, pitch, voice}): без двух голосов разом. */
    @JavascriptInterface public void speakRemoteFb(String id, String url, String key, String body, String fb) { a.tts.speakRemote(id, url, key, body, fb); }

    @JavascriptInterface public void stopSpeak() { a.tts.stop(); }

    @JavascriptInterface public String voices() { return a.tts.voices(); }

    @JavascriptInterface public boolean ttsReady() { return a.tts.ready(); }

    // ---------- напоминания ----------

    /** Поставить или заменить (тот же id) напоминание; формат — в Alarms.put. -> сохранённое с id или "" при ошибке. */
    /** Облик персонажа для уведомлений (см. Faces): png — картинка base64, рисует faceFor в app.js. */
    @JavascriptInterface public void setFace(String pid, String name, String color, String png) {
        Faces.save(a, pid, name, color, png);
    }

    @JavascriptInterface public String alarmSet(String json) {
        try {
            JSONObject x = new JSONObject(json);
            if (!x.has("id")) x.put("id", "a" + System.currentTimeMillis());
            Alarms.put(a, x);
            return x.toString();
        } catch (Exception e) { return ""; }
    }

    @JavascriptInterface public boolean alarmCancel(String id) { return Alarms.remove(a, id); }

    @JavascriptInterface public String alarms() { return Alarms.list(a).toString(); }

    @JavascriptInterface public String alarmHistory() { return Alarms.history(a); }

    // значок «Записать» на рабочем столе (CaptureWidget): состояние, вкл/выкл, добавить на экран; home — свернуть приложение
    @JavascriptInterface public String widgetState() { return CaptureWidget.state(a).toString(); }

    @JavascriptInterface public void widgetSet(boolean on) { CaptureWidget.set(a, on); }

    @JavascriptInterface public boolean widgetPin() { return CaptureWidget.pin(a); }

    @JavascriptInterface public void home() { a.runOnUiThread(new Runnable() { @Override public void run() { a.moveTaskToBack(true); } }); }

    @JavascriptInterface public boolean exactAlarms() {
        return Compat.canExact((android.app.AlarmManager) a.getSystemService(Context.ALARM_SERVICE));
    }

    // ---------- телефон ----------

    /** Контакт по имени (Phone.contact) или "" — не нашли. Без разрешения — {"need": разрешение}: интерфейс спросит его. */
    @JavascriptInterface public String contact(String who) {
        if (!a.has(android.Manifest.permission.READ_CONTACTS)) return "{\"need\":\"android.permission.READ_CONTACTS\"}";
        JSONObject c = Phone.contact(a, who);
        return c == null ? "" : c.toString();
    }

    // ---------- календарь (Cal.java) ----------

    /** Встречи за период: {"from": мс, "to": мс} → {"events": [...]}; без разрешения — {"need": READ_CALENDAR}. */
    @JavascriptInterface public String calEvents(String json) {
        if (!a.has(android.Manifest.permission.READ_CALENDAR)) return "{\"need\":\"android.permission.READ_CALENDAR\"}";
        try {
            JSONObject q = new JSONObject(json);
            return new JSONObject().put("events", Cal.events(a.getContentResolver(), q.getLong("from"), q.getLong("to"))).toString();
        } catch (Throwable e) {
            return "{\"error\":" + JSONObject.quote(String.valueOf(e.getMessage())) + "}";
        }
    }

    /** Записать встречу (app.js уже спросил «записать?»): {title, begin, end, all_day, location} → {id, calendar} | {error} | {need}. */
    @JavascriptInterface public String calAdd(String json) {
        if (!a.has(android.Manifest.permission.WRITE_CALENDAR)) return "{\"need\":\"android.permission.WRITE_CALENDAR\"}";
        try {
            return Cal.add(a.getContentResolver(), new JSONObject(json)).toString();
        } catch (Throwable e) {
            return "{\"error\":" + JSONObject.quote(String.valueOf(e.getMessage())) + "}";
        }
    }

    /** Окно новой встречи в приложении «Календарь» — сохранит человек. */
    @JavascriptInterface public boolean calOpenInsert(String json) {
        try { return Cal.openInsert(a, new JSONObject(json)); } catch (Throwable e) { return false; }
    }

    // есть разрешение CALL_PHONE — звоним сразу, нет — открываем набор номера, нажать «вызов» человек может сам
    @JavascriptInterface public boolean call(String number) {
        return Phone.call(a, number, a.has(android.Manifest.permission.CALL_PHONE));
    }

    @JavascriptInterface public boolean sms(String number, String text) { return Phone.sms(a, number, text); }

    @JavascriptInterface public String openApp(String name) { return Phone.openApp(a, name); }

    @JavascriptInterface public String apps() { return Phone.apps(a).toString(); }

    @JavascriptInterface public boolean openUrl(String url) { return Phone.openUrl(a, url); }

    // радио: состояние приходит событием radio (Radio.java)
    @JavascriptInterface public void radioPlay(String url, String name) { a.radio.play(url, name); }

    @JavascriptInterface public void radioPause() { a.radio.pause(); }

    @JavascriptInterface public void radioResume() { a.radio.resume(); }

    @JavascriptInterface public void radioStop() { a.radio.stop(); }

    @JavascriptInterface public void radioDuck(boolean on) { a.radio.duck(on); }

    @JavascriptInterface public void radioVolume(float v) { a.radio.volume(v); }

    @JavascriptInterface public String radioState() { return a.radio.state(); }

    @JavascriptInterface public boolean torch(boolean on) { return Phone.torch(a, on); }

    @JavascriptInterface public int volume(String op, int value) { return Phone.volume(a, op, value); }

    @JavascriptInterface public String battery() { return Phone.battery(a).toString(); }

    // files/saveFile — данные интерфейса (заметки, деньги…) файлами во внутренней памяти приложения. Имя проходит через
    // safe(): из JavaScript нельзя выйти из папки приложения («../»). Запись — во временный файл и переименование, чтобы
    // сбой посреди записи не оставил половину файла.
    @JavascriptInterface public String files(String name) {
        try {
            File f = new File(a.getFilesDir(), safe(name));
            return f.exists() ? Net.readAll(new FileInputStream(f)) : "";
        } catch (Exception e) { return ""; }
    }

    @JavascriptInterface public boolean saveFile(String name, String text) {
        try {
            File f = new File(a.getFilesDir(), safe(name));
            File tmp = new File(f.getPath() + ".tmp");
            java.io.FileOutputStream o = new java.io.FileOutputStream(tmp);
            o.write(text.getBytes("UTF-8"));
            o.close();
            return tmp.renameTo(f);
        } catch (Exception e) { return false; }
    }

    /** Сохранить сделанное ассистентом (страница, мини-программа) в «Загрузки/Dewiar» — его видно в «Файлах» телефона.
     *  Android 10+: через MediaStore без разрешений; старее — в папку приложения на карте памяти (Android/data/…/Download).
     *  -> путь для показа человеку или "" при ошибке. */
    /** Показать чужой HTML (сделанное моделью, файлы задач) в отдельном окне без моста — см. HtmlView. */
    @JavascriptInterface public boolean viewHtml(String title, String html) {
        try {
            java.io.File f = new java.io.File(a.getCacheDir(), "htmlview.html");
            try (java.io.FileOutputStream o = new java.io.FileOutputStream(f)) { o.write((html == null ? "" : html).getBytes("UTF-8")); }
            final android.content.Intent i = new android.content.Intent(a, HtmlView.class).putExtra("path", f.getAbsolutePath()).putExtra("title", title);
            a.runOnUiThread(new Runnable() { @Override public void run() { a.startActivityForResult(i, HtmlView.REQ); } });
            return true;
        } catch (Exception e) { return false; }
    }

    @JavascriptInterface public String saveDownload(String name, String mime, String text) {
        try {
            return saveBytes(name, mime, text.getBytes("UTF-8"));
        } catch (Exception e) { return ""; }
    }

    /** Снимок экрана приложения для жалобы разработчику (только своё окно — не другие приложения): JPEG в base64,
     *  уменьшенный до ~1080 точек по длинной стороне; не вышло — "". Android 8+ — PixelCopy: то, что правда на экране
     *  (отзыв 11.10: прежний снимок через View.draw не видел облик и слои с ускорением — жалоба приходила с пустым местом
     *  вместо облика и полосой сверху). Старше или не вышло — как раньше, рисованием окна в главном потоке. */
    @JavascriptInterface public String snapshot() {
        String px = pixelCopy();
        return px.isEmpty() ? drawSnapshot() : px;
    }

    private String pixelCopy() {
        if (Build.VERSION.SDK_INT < 26) return "";
        android.os.HandlerThread ht = new android.os.HandlerThread("snap");
        try {
            final android.view.Window win = a.getWindow();
            android.view.View v = win.getDecorView();
            int w = v.getWidth(), h = v.getHeight();
            if (w <= 0 || h <= 0) return "";
            final android.graphics.Bitmap full = android.graphics.Bitmap.createBitmap(w, h, android.graphics.Bitmap.Config.ARGB_8888);
            final int[] res = { -1 };
            final java.util.concurrent.CountDownLatch done = new java.util.concurrent.CountDownLatch(1);
            Class<?> pc = Class.forName("android.view.PixelCopy");
            Class<?> lis = Class.forName("android.view.PixelCopy$OnPixelCopyFinishedListener");
            Object l = java.lang.reflect.Proxy.newProxyInstance(lis.getClassLoader(), new Class<?>[] { lis }, new java.lang.reflect.InvocationHandler() {
                @Override public Object invoke(Object proxy, java.lang.reflect.Method m, Object[] args) {
                    if ("onPixelCopyFinished".equals(m.getName()) && args != null && args.length > 0) { res[0] = (Integer) args[0]; done.countDown(); }
                    return null;
                }
            });
            ht.start();
            pc.getMethod("request", android.view.Window.class, android.graphics.Bitmap.class, lis, android.os.Handler.class)
                    .invoke(null, win, full, l, new android.os.Handler(ht.getLooper()));
            if (!done.await(2, java.util.concurrent.TimeUnit.SECONDS) || res[0] != 0) { full.recycle(); return ""; }   // 0 — PixelCopy.SUCCESS
            return jpeg(full);
        } catch (Throwable e) {
            return "";
        } finally {
            ht.quitSafely();
        }
    }

    /** Картинка -> JPEG base64, не больше 1080 точек по длинной стороне; исходник освобождается. */
    private static String jpeg(android.graphics.Bitmap src) {
        float k = Math.min(1f, 1080f / Math.max(src.getWidth(), src.getHeight()));
        android.graphics.Bitmap bm = k < 1f ? android.graphics.Bitmap.createScaledBitmap(src, Math.max(1, (int) (src.getWidth() * k)), Math.max(1, (int) (src.getHeight() * k)), true) : src;
        java.io.ByteArrayOutputStream o = new java.io.ByteArrayOutputStream();
        bm.compress(android.graphics.Bitmap.CompressFormat.JPEG, 78, o);
        if (bm != src) bm.recycle();
        src.recycle();
        return android.util.Base64.encodeToString(o.toByteArray(), android.util.Base64.NO_WRAP);
    }

    private String drawSnapshot() {
        final String[] out = {""};
        final java.util.concurrent.CountDownLatch done = new java.util.concurrent.CountDownLatch(1);
        a.runOnUiThread(new Runnable() { @Override public void run() {
            try {
                android.view.View v = a.getWindow().getDecorView().getRootView();
                int w = v.getWidth(), h = v.getHeight();
                if (w > 0 && h > 0) {
                    float k = Math.min(1f, 1080f / Math.max(w, h));
                    android.graphics.Bitmap bm = android.graphics.Bitmap.createBitmap(Math.max(1, (int) (w * k)), Math.max(1, (int) (h * k)),
                            android.graphics.Bitmap.Config.RGB_565);
                    android.graphics.Canvas c = new android.graphics.Canvas(bm);
                    c.scale(k, k);
                    v.draw(c);
                    java.io.ByteArrayOutputStream o = new java.io.ByteArrayOutputStream();
                    bm.compress(android.graphics.Bitmap.CompressFormat.JPEG, 78, o);
                    bm.recycle();
                    out[0] = android.util.Base64.encodeToString(o.toByteArray(), android.util.Base64.NO_WRAP);
                }
            } catch (Throwable e) { out[0] = ""; }
            done.countDown();
        } });
        try { done.await(2, java.util.concurrent.TimeUnit.SECONDS); } catch (InterruptedException e) { }
        return out[0];
    }

    /** Двоичный файл (base64) — в «Загрузки/Dewiar»: файлы результатов задач (PDF, PPTX, картинки). -> путь или "". */
    @JavascriptInterface public String saveDownloadB64(String name, String mime, String b64) {
        try {
            return saveBytes(name, mime, android.util.Base64.decode(b64, android.util.Base64.DEFAULT));
        } catch (Exception e) { return ""; }
    }

    private String saveBytes(String name, String mime, byte[] b) {
        String n = name.replaceAll("[\\\\/:*?\"<>|\\x00-\\x1f]", "_");
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                android.content.ContentValues v = new android.content.ContentValues();
                v.put("_display_name", n);
                v.put("mime_type", mime);
                v.put("relative_path", "Download/Dewiar");
                android.net.Uri u = a.getContentResolver().insert(android.net.Uri.parse("content://media/external/downloads"), v);
                if (u == null) return "";
                java.io.OutputStream o = a.getContentResolver().openOutputStream(u);
                o.write(b);
                o.close();
                return "Загрузки/Dewiar/" + n;
            }
            File d = new File(a.getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS), "Dewiar");
            d.mkdirs();
            java.io.FileOutputStream o = new java.io.FileOutputStream(new File(d, n));
            o.write(b);
            o.close();
            return "Android/data/" + a.getPackageName() + "/files/Download/Dewiar/" + n;
        } catch (Exception e) { return ""; }
    }

    private static String safe(String n) { return n.replaceAll("[^\\w.-]", "_"); }

    @SuppressWarnings("unused") private static JSONArray none() { return new JSONArray(); }
}
