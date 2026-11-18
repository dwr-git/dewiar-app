package pro.dewiar.app;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

/** Напоминания с других устройств, пока приложение закрыто (1.0.36; письмо 18.11: «на компьютере сказал — напомни завтра
 *  в час… а если я засяду с телефоном — телефон мне напомнит?»). Раз в ~15 минут (JobScheduler, нужна сеть) спросить облако
 *  ?p=/sync/peek — напоминания после номера since — и поставить их здесь так же, как синхронизация в app.js (syncApply):
 *  тот же id — тот же сигнал, удалённое — снять. Зашифрованные на устройстве не трогаем: их поставит приложение, когда
 *  его откроют (ключ — только там). Что спрашивать ({base, token, link, since}) кладёт интерфейс через Bridge.remWatch. */
public class RemWatch extends JobService {
    static final int JOB = 4714;

    static void schedule(Context c, boolean on) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        if (!on) { js.cancel(JOB); return; }
        for (JobInfo j : js.getAllPendingJobs()) if (j.getId() == JOB) return;
        JobInfo.Builder b = new JobInfo.Builder(JOB, new ComponentName(c, RemWatch.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(15 * 60 * 1000L).setPersisted(true);
        try { js.schedule(b.build()); } catch (Throwable ignored) { }
    }

    @Override public boolean onStartJob(final JobParameters p) {
        new Thread(new Runnable() { @Override public void run() {
            try { check(RemWatch.this); } catch (Throwable ignored) { }
            jobFinished(p, false);
        } }).start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters p) { return false; }

    /** {kind, days, time} компьютера -> "", daily, weekdays, weekly, d:0123 — как repFromDict в app.js */
    static String repeat(JSONObject r) {
        if (r == null) return "";
        String kind = r.optString("kind");
        JSONArray d = r.optJSONArray("days");
        boolean[] on = new boolean[7];
        int n = 0;
        for (int i = 0; d != null && i < d.length(); i++) { int x = d.optInt(i, -1); if (x >= 0 && x <= 6 && !on[x]) { on[x] = true; n++; } }
        if ("daily".equals(kind) && (d == null || n == 7)) return "daily";
        if (!"daily".equals(kind) && !"weekly".equals(kind)) return "";
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < 7; i++) if (on[i]) s.append(i);
        if (n == 7) return "daily";
        if ("01234".contentEquals(s)) return "weekdays";
        if (n == 1) return "weekly";
        return n > 1 ? "d:" + s : "";
    }

    static void check(Context c) throws Exception {
        SharedPreferences pr = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
        JSONObject w = new JSONObject(pr.getString("rem_watch", "{}"));
        String base = w.optString("base"), token = w.optString("token");
        if (base.isEmpty() || token.isEmpty()) return;
        long since = Math.max(w.optLong("since"), pr.getLong("rem_since", 0));
        HttpURLConnection h = (HttpURLConnection) new URL(base + "?p=/sync/peek&since=" + since).openConnection();
        h.setConnectTimeout(15000); h.setReadTimeout(20000);
        h.setRequestProperty("Authorization", "Bearer " + token);
        if (!w.optString("link").isEmpty()) h.setRequestProperty("X-Sync-Link", w.optString("link"));
        if (h.getResponseCode() != 200) return;
        JSONObject d = new JSONObject(Net.readAll(h.getInputStream()));
        if (!w.optString("sid").isEmpty() && !w.optString("sid").equals(d.optString("sid"))) return;   // данные слились с другими — разберётся приложение
        JSONArray items = d.optJSONArray("items");
        long now = System.currentTimeMillis();
        for (int i = 0; items != null && i < items.length(); i++) {
            JSONObject it = items.getJSONObject(i), x = it.optJSONObject("data");
            String id = it.optString("id");
            if (id.isEmpty()) continue;
            JSONObject was = Alarms.get(c, id);
            if (it.optBoolean("deleted") || (x != null && x.optBoolean("paused"))) { if (was != null) Alarms.remove(c, id); continue; }
            if (x == null || x.has("e2e") || x.has("c")) continue;           // зашифровано на устройстве — откроют приложение
            long at = x.optLong("at");
            String rep = repeat(x.optJSONObject("repeat"));
            if (at <= 0 || (rep.isEmpty() && at < now - 300000 && was == null)) continue;
            String k = x.optString("kind");
            JSONObject a = new JSONObject().put("id", id).put("title", x.optString("text", "Напоминание")).put("at", at)
                    .put("kind", "alarm".equals(k) || "timer".equals(k) ? k : "reminder").put("repeat", rep);
            String note = x.has("note") ? x.optString("note") : was != null ? was.optString("note") : "";
            if (!note.isEmpty()) a.put("note", note);
            if (was != null && was.optLong("at") == at && was.optString("title").equals(a.optString("title"))
                    && was.optString("repeat").equals(rep)) continue;      // уже стоит так же
            Alarms.put(c, a);
        }
        pr.edit().putLong("rem_since", d.optLong("rev", since)).apply();
    }
}
