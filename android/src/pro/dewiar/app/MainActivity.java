package pro.dewiar.app;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.InputStream;
import org.json.JSONObject;

/** Главный и единственный экран: WebView с интерфейсом assets/www (index.html, app.js) и мостом window.Dewiar (Bridge.java).
 *  Здесь же: события в интерфейс (event → window.N.ev), разрешения, выбор файла и камера для страницы, входящие
 *  намерения (кнопка помощника, ярлыки, ссылки dewiar://, «Поделиться») и кнопка «Назад».
 *  Слух, голос и радио живут в Speech, Tts, Radio; радио одно на приложение и переживает пересоздание экрана. */
public class MainActivity extends Activity implements Net.Sink {
    WebView web;
    Speech speech;
    Tts tts;
    Radio radio;
    private volatile boolean pageReady;
    private JSONObject pending;                     // пришедшее намерение, пока страница его не забрала (Dewiar.takeIntent)
    private ValueCallback<Uri[]> fileCb;            // <input type=file> в интерфейсе: снимок оплаты для пополнения
    private static final int PICK_FILE = 7;

    @SuppressWarnings("deprecation")
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        live = new java.lang.ref.WeakReference<>(this);
        final Context app = getApplicationContext();
        new Thread(new Runnable() { @Override public void run() { Update.cleanup(app); } }).start();   // обновление уже стоит — файл не нужен
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#0B0B10"));
        w.setNavigationBarColor(Color.parseColor("#0B0B10"));
        w.addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#0B0B10"));
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setTextZoom(100);                                     // крупный шрифт системы не ломает вёрстку — размеры задаёт app.css
        // отладка WebView (chrome://inspect) — только в отладочной сборке: в обычной через USB достали бы ключи и токены
        WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0);
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage m) {     // console.log интерфейса — в logcat (тег Dewiar)
                android.util.Log.i("Dewiar", m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
            // «сфотографируй меня»: камера в интерфейсе (getUserMedia) — только если разрешение камеры уже дано;
            // само разрешение Android интерфейс спрашивает заранее через Dewiar.perm, здесь не спрашиваем
            @Override public void onPermissionRequest(final android.webkit.PermissionRequest r) {
                runOnUiThread(new Runnable() { @Override public void run() {
                    // камера — для «сфотографируй» и видеозвонков, микрофон — для звонков «Близким»; даём то, на что разрешение уже есть
                    java.util.ArrayList<String> ok = new java.util.ArrayList<>();
                    for (String x : r.getResources()) {
                        if (android.webkit.PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(x) && has(Manifest.permission.CAMERA)) ok.add(x);
                        if (android.webkit.PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(x) && has(Manifest.permission.RECORD_AUDIO)) ok.add(x);
                    }
                    if (ok.isEmpty()) r.deny(); else r.grant(ok.toArray(new String[0]));
                } });
            }
            @Override public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCb != null) fileCb.onReceiveValue(null);       // прежний выбор не закрыт: без ответа WebView больше не откроет выбор
                fileCb = cb;
                try {
                    // что просит страница (accept): снимок оплаты — только картинки, вложение для Лиры — фото и текстовые файлы
                    java.util.ArrayList<String> types = new java.util.ArrayList<>();
                    for (String t : p.getAcceptTypes()) for (String x : (t == null ? "" : t).split(","))
                        if (x.trim().contains("/")) types.add(x.trim());
                    Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                    i.addCategory(Intent.CATEGORY_OPENABLE);
                    boolean onlyImages = types.isEmpty() || (types.size() == 1 && types.get(0).startsWith("image/"));
                    i.setType(types.size() == 1 ? types.get(0) : types.isEmpty() ? "image/*" : "*/*");
                    if (types.size() > 1) i.putExtra(Intent.EXTRA_MIME_TYPES, types.toArray(new String[0]));
                    if (p.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) i.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
                    startActivityForResult(Intent.createChooser(i, onlyImages ? "Выберите фото" : "Фото или файл"), PICK_FILE);
                    return true;
                } catch (Throwable e) {
                    fileCb = null;
                    return false;
                }
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) {
                Uri u = Uri.parse(url);
                if ("file".equals(u.getScheme())) return false;
                Phone.openUrl(MainActivity.this, u.toString());       // ссылки — во внешнем браузере
                return true;
            }
            @Override public void onPageFinished(WebView v, String url) { pageReady = true; }
        });
        // намерение, с которым запустили, ждёт в pending, пока app.js не заберёт его (Dewiar.takeIntent);
        // будильники ставим заново при каждом запуске — на случай, если система их сбросила
        Speech.restoreBeeps(this);                   // закрылись посреди «удерживайте и говорите» — звук вернуть
        speech = new Speech(this, this);
        tts = new Tts(this, this);
        radio = Radio.get(this, this);
        web.addJavascriptInterface(new Bridge(this), "Dewiar");
        setContentView(web);
        handle(getIntent());
        web.loadUrl("file:///android_asset/www/index.html");
        Alarms.rescheduleAll(this);
    }

    @Override protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req == PICK_FILE && fileCb != null) {
            Uri[] out = null;
            if (res == RESULT_OK && data != null) {
                if (data.getClipData() != null && data.getClipData().getItemCount() > 0) {     // выбрали несколько
                    int n = Math.min(4, data.getClipData().getItemCount());
                    out = new Uri[n];
                    for (int k = 0; k < n; k++) out[k] = data.getClipData().getItemAt(k).getUri();
                } else if (data.getData() != null) out = new Uri[]{data.getData()};
            }
            fileCb.onReceiveValue(out);
            fileCb = null;
        }
        if (req == HtmlView.REQ) {                              // окно чужого HTML закрыли: «В «Загрузки»» — сохраняет интерфейс
            try { event("htmlview", new JSONObject().put("save", res == RESULT_OK && data != null && data.getBooleanExtra("save", false))); }
            catch (Exception ignored) { }
        }
    }

    @Override protected void onNewIntent(Intent i) {
        super.onNewIntent(i);
        setIntent(i);
        handle(i);
        if (pageReady && pending != null) { JSONObject p = pending; pending = null; event("intent", p); }   // страница уже открыта — сразу событием
    }

    /** Намерение → pending {action: type | listen | link | import | say | images | note}: images — фото из «Поделиться»,
     *  note — «Посмотреть вложения» в окне напоминания; TYPE — ярлык «написать»; ASSIST/VOICE_COMMAND/LISTEN —
     *  кнопка помощника и ярлык «слушать»; dewiar:// — ссылка (QR из студии на компьютере); открытый файл или текст,
     *  похожий на JSON, — импорт настроек с компьютера;
     *  прочий текст из «Поделиться» — сказать ассистенту. */
    private void handle(Intent i) {
        if (i == null) return;
        try {
            String a = i.getAction();
            if ("pro.dewiar.TYPE".equals(a)) {
                pending = new JSONObject().put("action", "type");
            } else if ("pro.dewiar.CAPTURE".equals(a)) {            // значок «Записать» на рабочем столе (CaptureWidget)
                pending = new JSONObject().put("action", "capture");
            } else if ("pro.dewiar.NOTE".equals(a)) {               // «Посмотреть вложения» в окне напоминания (AlarmActivity)
                pending = new JSONObject().put("action", "note").put("id", i.getStringExtra("note"));
            } else if ("pro.dewiar.CLOSE".equals(a)) {              // уведомление «Близких» (CloseWatch) — открыть переписку
                pending = new JSONObject().put("action", "close");
            } else if ("pro.dewiar.NEWS".equals(a)) {               // уведомление объявления для всех (CloseLive)
                pending = new JSONObject().put("action", "news");
            } else if ("pro.dewiar.CLOSE_CALL".equals(a)) {         // звонок близкого из уведомления (CloseLive): открыть, ответить
                CloseLive.cancelRing(this);
                pending = new JSONObject().put("action", "close_call").put("pid", i.getStringExtra("pid")).put("answer", i.getBooleanExtra("answer", false));
            } else if (Intent.ACTION_ASSIST.equals(a) || "android.intent.action.VOICE_COMMAND".equals(a) || "pro.dewiar.LISTEN".equals(a)) {
                pending = new JSONObject().put("action", "listen");
            } else if (Intent.ACTION_VIEW.equals(a) && i.getData() != null) {
                Uri u = i.getData();
                if ("dewiar".equals(u.getScheme())) pending = new JSONObject().put("action", "link").put("url", u.toString());
                else if ("content".equals(u.getScheme())) pending = new JSONObject().put("action", "import").put("text", read(u));   // файл настроек, выбранный человеком
            } else if ((Intent.ACTION_SEND.equals(a) || Intent.ACTION_SEND_MULTIPLE.equals(a)) && String.valueOf(i.getType()).startsWith("image/")) {
                // снимки и фото из «Поделиться»: уменьшенные (до 1600 px, JPEG) — во вложения поля ввода
                java.util.ArrayList<Uri> us = new java.util.ArrayList<>();
                if (Intent.ACTION_SEND_MULTIPLE.equals(a)) {
                    java.util.ArrayList<Uri> l = i.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
                    if (l != null) us.addAll(l);
                } else { Uri st = i.getParcelableExtra(Intent.EXTRA_STREAM); if (st != null) us.add(st); }
                org.json.JSONArray imgs = new org.json.JSONArray();
                for (Uri u : us) { if (imgs.length() >= 4) break; String d = image(u); if (!d.isEmpty()) imgs.put(d); }
                String t = i.getStringExtra(Intent.EXTRA_TEXT);
                if (imgs.length() > 0) pending = new JSONObject().put("action", "images").put("images", imgs).put("text", t == null ? "" : t);
            } else if (Intent.ACTION_SEND.equals(a)) {
                Uri st = i.getParcelableExtra(Intent.EXTRA_STREAM);
                String t = i.getStringExtra(Intent.EXTRA_TEXT);
                if (st != null) { String f = read(st); if (f.trim().startsWith("{")) t = f; }
                if (t != null && t.trim().startsWith("{")) pending = new JSONObject().put("action", "import").put("text", t);
                else if (t != null) pending = new JSONObject().put("action", "say").put("text", t);
            }
        } catch (Throwable ignored) { }
    }

    /** Картинка по адресу «Поделиться» -> data:image/jpeg;base64 (длинная сторона до 1600 px) или "" — не открылась. */
    private String image(Uri u) {
        try {
            android.graphics.BitmapFactory.Options o = new android.graphics.BitmapFactory.Options();
            o.inJustDecodeBounds = true;
            try (InputStream in = getContentResolver().openInputStream(u)) { android.graphics.BitmapFactory.decodeStream(in, null, o); }
            int side = Math.max(o.outWidth, o.outHeight), k = 1;
            while (side / (k * 2) >= 1600) k *= 2;
            o = new android.graphics.BitmapFactory.Options();
            o.inSampleSize = k;
            android.graphics.Bitmap bm;
            try (InputStream in = getContentResolver().openInputStream(u)) { bm = android.graphics.BitmapFactory.decodeStream(in, null, o); }
            if (bm == null) return "";
            int m = Math.max(bm.getWidth(), bm.getHeight());
            if (m > 1600) {
                float f = 1600f / m;
                bm = android.graphics.Bitmap.createScaledBitmap(bm, Math.round(bm.getWidth() * f), Math.round(bm.getHeight() * f), true);
            }
            java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
            bm.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, out);
            return "data:image/jpeg;base64," + android.util.Base64.encodeToString(out.toByteArray(), android.util.Base64.NO_WRAP);
        } catch (Throwable e) { return ""; }
    }

    private String read(Uri u) {
        try {
            InputStream in = getContentResolver().openInputStream(u);
            return in == null ? "" : Net.readAll(in);
        } catch (Throwable e) { return ""; }
    }

    synchronized String takePending() {
        JSONObject p = pending;
        pending = null;
        return p == null ? "" : p.toString();
    }

    /** Кэш страниц WebView («освободи место», Bridge.clearOwnCache) — только в главном потоке. */
    void clearWebCache() { if (web != null) web.clearCache(true); }

    /** Событие в интерфейс: window.N.ev("{type, ...}") — JSON строкой, разбирает app.js. Зовётся из любого потока
     *  (сеть, слух, голос) — evaluateJavascript только в главном. */
    @Override public void event(String type, JSONObject data) {
        try { data.put("type", type); } catch (Exception ignored) { }
        final String js = "window.N&&N.ev(" + JSONObject.quote(data.toString()) + ")";
        runOnUiThread(new Runnable() { @Override public void run() { if (web != null) web.evaluateJavascript(js, null); } });
    }

    /** Ответ всегда событием perm {name, granted} — и когда разрешение уже есть. */
    void askPermission(String name) {
        if (has(name)) {
            try { event("perm", new JSONObject().put("name", name).put("granted", true)); } catch (Exception ignored) { }
            return;
        }
        // точное место Android 12+ спрашивает только вместе с приблизительным (человек выберет, какое дать)
        if ("android.permission.ACCESS_FINE_LOCATION".equals(name)) requestPermissions(new String[]{name, "android.permission.ACCESS_COARSE_LOCATION"}, 1);
        else requestPermissions(new String[]{name}, 1);
    }

    @Override public void onRequestPermissionsResult(int code, String[] perms, int[] res) {
        for (int i = 0; i < perms.length; i++) {
            try { event("perm", new JSONObject().put("name", perms[i]).put("granted", res.length > i && res[i] == PackageManager.PERMISSION_GRANTED)); }
            catch (Exception ignored) { }
        }
    }

    boolean has(String perm) {
        if ("android.permission.POST_NOTIFICATIONS".equals(perm) && Build.VERSION.SDK_INT < 33) return true;   // до Android 13 не спрашивают
        return checkSelfPermission(perm) == PackageManager.PERMISSION_GRANTED;
    }

    // «Назад»: сначала интерфейсу — N.back() закрывает панель или прерывает разговор и тогда вернёт true;
    // иначе приложение сворачивается, а не закрывается (радио играет дальше)
    @Override public void onBackPressed() {
        web.evaluateJavascript("window.N&&N.back&&N.back()", new ValueCallback<String>() {
            @Override public void onReceiveValue(String v) {
                if (!"true".equals(v)) moveTaskToBack(true);
            }
        });
    }

    @Override protected void onResume() {
        super.onResume();
        CloseLive.visible = true;                            // на экране — сообщения и звонки показывает само приложение
        if (pageReady) event("resume", new JSONObject());
    }

    @Override protected void onPause() {
        super.onPause();
        CloseLive.visible = false;
        if (pageReady) event("pause", new JSONObject());
    }

    /** Открытое окно приложения — чтобы уведомление («Сделано ✓» у напоминания) могло сразу сказать интерфейсу. */
    static java.lang.ref.WeakReference<MainActivity> live = new java.lang.ref.WeakReference<>(null);

    static void poke(String type) {
        MainActivity m = live.get();
        if (m != null) m.event(type, new JSONObject());
    }

    @Override protected void onDestroy() {
        if (live.get() == this) live.clear();
        if (speech != null) { speech.cancel(); speech.release(); }
        if (tts != null) tts.shutdown();
        if (radio != null && isFinishing()) radio.stop();          // закрыли приложение — радио тоже; при пересоздании экрана играет дальше
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }

    /** Игра «во весь экран» (24.10, владелец: «в каждой игре на телефоне не хватает кнопки „во весь экран“»): панели
     *  системы прячутся (появляются смахиванием от края и прячутся снова), выключили или закрыли игру — возвращаются. */
    @SuppressWarnings("deprecation")
    void immersive(final boolean on) {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                View d = getWindow().getDecorView();
                d.setSystemUiVisibility(on ? (View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN) : 0);
            }
        });
    }

    void keepScreen(final boolean on) {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                if (on) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            }
        });
    }

    static final String MIC = Manifest.permission.RECORD_AUDIO;
    static boolean atLeast(int sdk) { return Build.VERSION.SDK_INT >= sdk; }
    @SuppressWarnings("unused") static void hide(View v) { v.setVisibility(View.GONE); }
}
