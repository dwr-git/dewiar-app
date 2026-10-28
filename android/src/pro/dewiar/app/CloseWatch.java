package pro.dewiar.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.LinkedHashMap;
import java.util.Map;
import org.json.JSONArray;
import org.json.JSONObject;

/** «Близкие», когда приложение закрыто: раз в ~15 минут (JobScheduler, нужна сеть) спросить облако, есть ли новые
 *  сообщения, и показать уведомление «Анна: новое сообщение». Сами сообщения не открывает — ключи и расшифровка в
 *  интерфейсе (app.js, closecrypto.js): открыли приложение — оно заберёт и прочитает. Что спрашивать (адрес облака,
 *  вход, номер последнего прочитанного) кладёт интерфейс через Bridge.closeWatch; пусто — проверка выключена. */
public class CloseWatch extends JobService {
    static final int JOB = 4711;

    static void schedule(Context c, boolean on) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        if (!on) { js.cancel(JOB); return; }
        for (JobInfo j : js.getAllPendingJobs()) if (j.getId() == JOB) return;     // уже стоит
        JobInfo.Builder b = new JobInfo.Builder(JOB, new ComponentName(c, CloseWatch.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(15 * 60 * 1000L).setPersisted(true);
        try { js.schedule(b.build()); } catch (Throwable ignored) { }
    }

    @Override public boolean onStartJob(final JobParameters p) {
        new Thread(new Runnable() { @Override public void run() {
            try { check(CloseWatch.this); } catch (Throwable ignored) { }
            jobFinished(p, false);
        } }).start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters p) { return false; }

    static void check(Context c) throws Exception {
        SharedPreferences pr = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
        JSONObject w = new JSONObject(pr.getString("close_watch", "{}"));
        String base = w.optString("base"), token = w.optString("token");
        if (base.isEmpty() || token.isEmpty()) return;
        long seen = Math.max(w.optLong("cursor"), pr.getLong("close_notified", 0));
        HttpURLConnection h = (HttpURLConnection) new URL(base + "?p=/close/inbox&after=" + seen).openConnection();
        h.setConnectTimeout(15000); h.setReadTimeout(20000);
        h.setRequestProperty("Authorization", "Bearer " + token);
        if (!w.optString("link").isEmpty()) h.setRequestProperty("X-Sync-Link", w.optString("link"));
        if (h.getResponseCode() != 200) return;
        JSONObject d = new JSONObject(Net.readAll(h.getInputStream()));
        JSONArray items = d.optJSONArray("items");
        Map<String, Integer> who = new LinkedHashMap<>(), work = new LinkedHashMap<>();
        long last = seen;
        for (int i = 0; items != null && i < items.length(); i++) {
            JSONObject it = items.getJSONObject(i);
            last = Math.max(last, it.optLong("id"));
            if (it.optBoolean("out")) continue;
            String k = it.optString("kind");
            if ("work".equals(k)) {                     // «Работа» (0.55): от руководителя — поручение, ответ или напоминание
                String n = it.optString("name", "Руководитель");
                work.put(n, (work.containsKey(n) ? work.get(n) : 0) + 1);
                continue;
            }
            if (!"msg".equals(k)) continue;
            String n = it.optString("name", "Близкий");
            who.put(n, (who.containsKey(n) ? who.get(n) : 0) + 1);
        }
        pr.edit().putLong("close_notified", last).apply();
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (!work.isEmpty()) {
            PendingIntent wi = PendingIntent.getActivity(c, 7, new Intent(c, MainActivity.class).setAction("pro.dewiar.WORK"),
                    PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            for (Map.Entry<String, Integer> e : work.entrySet()) {
                Notification.Builder b = Compat.builder(c, Compat.CH_INFO);
                b.setSmallIcon(R.drawable.ic_stat).setContentTitle("💼 Работа · " + e.getKey()).setContentText("новое по поручениям — откройте «Работу»")
                        .setAutoCancel(true).setContentIntent(wi);
                nm.notify(("work:" + e.getKey()).hashCode(), b.build());
            }
        }
        if (who.isEmpty()) return;
        PendingIntent pi = PendingIntent.getActivity(c, 5, new Intent(c, MainActivity.class).setAction("pro.dewiar.CLOSE"),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        for (Map.Entry<String, Integer> e : who.entrySet()) {
            String text = e.getValue() == 1 ? "новое сообщение" : "новых сообщений: " + e.getValue();
            Notification.Builder b = Compat.builder(c, Compat.CH_INFO);
            b.setSmallIcon(R.drawable.ic_stat).setContentTitle("💌 " + e.getKey()).setContentText(text).setAutoCancel(true).setContentIntent(pi);
            nm.notify(("close:" + e.getKey()).hashCode(), b.build());
        }
    }
}
