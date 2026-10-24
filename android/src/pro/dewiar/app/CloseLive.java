package pro.dewiar.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import android.os.IBinder;
import java.lang.reflect.Constructor;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

/** «Близкие» на связи, когда приложение свёрнуто или экран погас (отзыв 11.10: сообщения и звонки не доходили, пока
 *  приложение закрыто). Служба переднего плана с тихим значком «Dewiar на связи» держит к облаку длинный запрос
 *  (cloud.php ?p=/close/wait: ответ приходит сразу, как в ящике появилось новое, иначе через ~20 с — и снова):
 *  пришло сообщение — уведомление «💌 Анна: новое сообщение»; звонят (kind «ring» — открытый признак звонка, само
 *  предложение звонка зашифровано) — уведомление звонка на весь экран со звонком телефона и кнопками «Ответить» /
 *  «Отклонить». Сами сообщения служба не читает: ключи и расшифровка — в интерфейсе (app.js). Пока приложение на экране
 *  (visible), уведомлений нет — всё показывает оно. Что спрашивать (адрес, вход, курсор) — тот же close_watch, что у
 *  CloseWatch; включена ли — close_live (Bridge.closeLive). */
public class CloseLive extends Service {
    static final int NOTE = 7301, RING_NOTE = 7302, NEWS_NOTE = 7303;
    static final String CH_LIVE = "close_live", CH_CALL = "close_call", ACT_DECLINE = "pro.dewiar.CLOSE_DECLINE";
    static volatile boolean visible = false;
    private static volatile Thread loop;

    /** Включить или выключить по настройкам (close_live и close_watch). Запускать можно, пока приложение на экране
     *  или сразу после загрузки телефона — так требует Android. */
    static void apply(Context c) {
        SharedPreferences pr = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
        boolean on = pr.getBoolean("close_live", false) && !pr.getString("close_watch", "").isEmpty();
        Intent i = new Intent(c, CloseLive.class);
        try {
            if (!on) { c.stopService(i); return; }
            if (Build.VERSION.SDK_INT >= 26) Context.class.getMethod("startForegroundService", Intent.class).invoke(c, i);
            else c.startService(i);
        } catch (Throwable ignored) { }
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACT_DECLINE.equals(intent.getAction())) {                      // «Отклонить» на уведомлении звонка
            ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(RING_NOTE);
            return START_STICKY;
        }
        channels(this);
        Notification.Builder b = Compat.builder(this, CH_LIVE);
        PendingIntent open = PendingIntent.getActivity(this, 6, new Intent(this, MainActivity.class).setAction("pro.dewiar.CLOSE"),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle("Dewiar на связи").setContentText("Сообщения и звонки близких дойдут, даже когда приложение закрыто")
                .setOngoing(true).setContentIntent(open);
        try { startForeground(NOTE, b.build()); } catch (Throwable e) { stopSelf(); return START_NOT_STICKY; }
        if (loop == null || !loop.isAlive()) {
            loop = new Thread(new Runnable() { @Override public void run() { work(); } }, "close-live");
            loop.start();
        }
        return START_STICKY;
    }

    @Override public void onDestroy() {
        Thread t = loop; loop = null;
        if (t != null) t.interrupt();
        super.onDestroy();
    }

    private void work() {
        long pause = 2000;
        while (loop == Thread.currentThread()) {
            try {
                if (!once()) { stopSelf(); return; }
                pause = 2000;
            } catch (InterruptedException e) {
                return;
            } catch (Throwable e) {                                // нет сети, облако недоступно — подождать и снова
                try { Thread.sleep(pause); } catch (InterruptedException x) { return; }
                pause = Math.min(pause * 2, 60000);
            }
        }
    }

    /** Один длинный запрос. -> false — служба больше не нужна (выключили в настройках). */
    private boolean once() throws Exception {
        SharedPreferences pr = getSharedPreferences("dewiar", Context.MODE_PRIVATE);
        JSONObject w = new JSONObject(pr.getString("close_watch", "{}"));
        String base = w.optString("base"), token = w.optString("token");
        if (!pr.getBoolean("close_live", false) || base.isEmpty() || token.isEmpty()) return false;
        long seen = Math.max(w.optLong("cursor"), pr.getLong("close_notified", 0));
        HttpURLConnection h = (HttpURLConnection) new URL(base + "?p=/close/wait&after=" + seen).openConnection();
        h.setConnectTimeout(15000); h.setReadTimeout(45000);
        h.setRequestProperty("Authorization", "Bearer " + token);
        if (!w.optString("link").isEmpty()) h.setRequestProperty("X-Sync-Link", w.optString("link"));
        int code = h.getResponseCode();
        if (code == 401 || code == 403) { Thread.sleep(60000); return true; }
        if (code != 200) throw new Exception("облако ответило " + code);
        JSONObject d = new JSONObject(Net.readAll(h.getInputStream()));
        JSONArray items = d.optJSONArray("items");
        long last = Math.max(seen, d.optLong("last"));
        for (int i = 0; items != null && i < items.length(); i++) {
            JSONObject it = items.getJSONObject(i);
            if (it.optBoolean("out") || visible) continue;
            String kind = it.optString("kind"), name = it.optString("name", "Близкий");
            if ("msg".equals(kind)) message(name);
            else if ("ring".equals(kind) && System.currentTimeMillis() / 1000 - it.optLong("ts") < 60) {
                JSONObject env = it.optJSONObject("env");
                ring(name, it.optString("peer"), env != null && env.optBoolean("video"));
            }
        }
        pr.edit().putLong("close_notified", last).apply();
        // объявление для всех (кабинет → «Объявления»): уведомление один раз по номеру; на экране — покажет само приложение
        JSONObject nw = d.optJSONObject("news");
        if (nw != null && nw.optLong("id") > pr.getLong("news_notified", 0)) {
            if (!visible) news(nw);
            pr.edit().putLong("news_notified", nw.optLong("id")).apply();
        }
        return true;
    }

    private void news(JSONObject nw) {
        PendingIntent pi = PendingIntent.getActivity(this, 11, new Intent(this, MainActivity.class).setAction("pro.dewiar.NEWS"),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        String title = nw.optString("title"), text = nw.optString("text");
        Notification.Builder b = Compat.builder(this, Compat.CH_INFO);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle(("warn".equals(nw.optString("level")) ? "⚠️ " : "📣 ") + (title.isEmpty() ? "Dewiar" : title))
                .setContentText(text).setStyle(new Notification.BigTextStyle().bigText(text)).setAutoCancel(true).setContentIntent(pi);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(NEWS_NOTE, b.build());
    }

    private void message(String name) {
        PendingIntent pi = PendingIntent.getActivity(this, 5, new Intent(this, MainActivity.class).setAction("pro.dewiar.CLOSE"),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = Compat.builder(this, Compat.CH_INFO);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle("💌 " + name).setContentText("новое сообщение").setAutoCancel(true).setContentIntent(pi);
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(("close:" + name).hashCode(), b.build());
    }

    /** Звонок: на весь экран (на заблокированном тоже), звонок телефона, «Ответить» — открыть Dewiar и сразу ответить. */
    private void ring(String name, String pid, boolean video) {
        Intent answer = new Intent(this, MainActivity.class).setAction("pro.dewiar.CLOSE_CALL").putExtra("pid", pid).putExtra("answer", true)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        Intent show = new Intent(this, MainActivity.class).setAction("pro.dewiar.CLOSE_CALL").putExtra("pid", pid).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        int fl = PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT;
        PendingIntent pa = PendingIntent.getActivity(this, 8, answer, fl), ps = PendingIntent.getActivity(this, 9, show, fl);
        PendingIntent pd = PendingIntent.getService(this, 10, new Intent(this, CloseLive.class).setAction(ACT_DECLINE), fl);
        Notification.Builder b = Compat.builder(this, CH_CALL);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle("📞 " + name).setContentText(video ? "видеозвонок через Dewiar" : "звонит через Dewiar")
                .setCategory(Notification.CATEGORY_CALL).setPriority(Notification.PRIORITY_MAX).setAutoCancel(true)
                .setContentIntent(ps).setFullScreenIntent(ps, true)
                .addAction(new Notification.Action.Builder(R.drawable.ic_stat, "Ответить", pa).build())
                .addAction(new Notification.Action.Builder(R.drawable.ic_stat, "Отклонить", pd).build());
        if (Build.VERSION.SDK_INT < 26) b.setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)).setVibrate(new long[] { 0, 800, 600, 800 });
        try { Notification.Builder.class.getMethod("setTimeoutAfter", long.class).invoke(b, 50000L); } catch (Throwable ignored) { }
        Notification n = b.build();
        n.flags |= Notification.FLAG_INSISTENT;                     // звонит, пока не ответят или не отклонят
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(RING_NOTE, n);
    }

    static void cancelRing(Context c) {
        ((NotificationManager) c.getSystemService(NOTIFICATION_SERVICE)).cancel(RING_NOTE);
    }

    /** Каналы: «Dewiar на связи» — тихий, без значка в строке; «Звонки близких» — важный, со звонком телефона. */
    static void channels(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            Class<?> chc = Class.forName("android.app.NotificationChannel");
            Constructor<?> k = chc.getConstructor(String.class, CharSequence.class, int.class);
            java.lang.reflect.Method create = NotificationManager.class.getMethod("createNotificationChannel", chc);
            Object live = k.newInstance(CH_LIVE, "Dewiar на связи", 1 /* IMPORTANCE_MIN */);
            chc.getMethod("setShowBadge", boolean.class).invoke(live, false);
            create.invoke(nm, live);
            if (NotificationManager.class.getMethod("getNotificationChannel", String.class).invoke(nm, CH_CALL) == null) {
                Object call = k.newInstance(CH_CALL, "Звонки близких", 4 /* IMPORTANCE_HIGH */);
                Uri tone = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE);
                AudioAttributes aa = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();
                chc.getMethod("setSound", Uri.class, AudioAttributes.class).invoke(call, tone, aa);
                chc.getMethod("enableVibration", boolean.class).invoke(call, true);
                chc.getMethod("setVibrationPattern", long[].class).invoke(call, (Object) new long[] { 0, 800, 600, 800 });
                create.invoke(nm, call);
            }
        } catch (Throwable ignored) { }
    }
}
