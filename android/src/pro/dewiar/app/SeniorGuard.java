package pro.dewiar.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import org.json.JSONArray;
import org.json.JSONObject;

/** «Для старших», когда приложение закрыто (0.65; было: «проверки идут, пока приложение живо» — Android усыплял
 *  приложение на телефоне мамы, и «не отметила лекарство» не уходило).
 *  Интерфейс (senior.js, srArm) заранее готовит сообщения присматривающим — уже зашифрованные для их устройств — и
 *  отдаёт план (Bridge.srPlan): {base, token, link, items: [{at, med, day, key, rid, kind: late|noon, payloads: [{to, env,
 *  kind}]}]}. Здесь — один сигнал AlarmManager на ближайший пункт. Сработал — проверяем, нужно ли ещё:
 *   • уже отправлено (приложением или нами) — senior_day.sent того же дня;
 *   • «late»: лекарство отмечено «Выпил(а) ✓» в окне напоминания — очередь done_inbox (id = rid, не раньше часа до приёма);
 *   • «noon»: человек сегодня говорил с Лирой (senior_day.talk) или отметил любое лекарство;
 *  и отправляем в облако (?p=/close/send — как clSend). Нет сети — пробуем снова через 10 минут, но не позже 6 часов.
 *  Отправили — пишем ключ в senior_day.sent: приложение, проснувшись, второй раз не пошлёт. Тексты здесь не видны. */
public class SeniorGuard extends BroadcastReceiver {
    static final String ACT = "pro.dewiar.app.SENIOR";
    static final long KEEP = 6 * 3600_000L, RETRY = 10 * 60_000L;

    static SharedPreferences prefs(Context c) { return c.getSharedPreferences("dewiar", Context.MODE_PRIVATE); }

    /** План от интерфейса: пустая строка — выключить. */
    static synchronized void plan(Context c, String json) {
        prefs(c).edit().putString("senior_plan", json == null ? "" : json).commit();
        arm(c);
    }

    private static PendingIntent pi(Context c) {
        Intent i = new Intent(c, SeniorGuard.class).setAction(ACT);
        return PendingIntent.getBroadcast(c, 7377, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /** Поставить сигнал на ближайший пункт плана (и после перезагрузки — BootReceiver). */
    static synchronized void arm(Context c) {
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        am.cancel(pi(c));
        long next = Long.MAX_VALUE, now = System.currentTimeMillis();
        try {
            JSONArray it = new JSONObject(prefs(c).getString("senior_plan", "{}")).optJSONArray("items");
            for (int i = 0; it != null && i < it.length(); i++) {
                long at = it.getJSONObject(i).optLong("next", it.getJSONObject(i).optLong("at"));
                if (at < now - KEEP) continue;
                next = Math.min(next, Math.max(at, now + 5000));
            }
        } catch (Exception e) { return; }
        if (next == Long.MAX_VALUE) return;
        if (Compat.canExact(am)) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next, pi(c));
        else am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, next, pi(c));
    }

    @Override public void onReceive(Context c, Intent i) {
        final PendingResult r = goAsync();
        final Context ac = c.getApplicationContext();
        new Thread(new Runnable() { @Override public void run() {
            try { check(ac); } catch (Throwable ignored) { }
            finally { arm(ac); r.finish(); }
        } }).start();
    }

    static synchronized void check(Context c) throws Exception {
        SharedPreferences p = prefs(c);
        String raw = p.getString("senior_plan", "");
        if (raw.isEmpty()) return;
        JSONObject plan = new JSONObject(raw);
        JSONArray items = plan.optJSONArray("items"), keep = new JSONArray();
        long now = System.currentTimeMillis();
        for (int i = 0; items != null && i < items.length(); i++) {
            JSONObject it = items.getJSONObject(i);
            long at = it.optLong("at"), when = it.optLong("next", at);
            if (when > now) { keep.put(it); continue; }
            if (at < now - KEEP) continue;                       // слишком давно — уже не новость
            if (!needed(p, it)) continue;
            if (send(plan, it)) { markSent(p, it); continue; }
            it.put("next", now + RETRY); keep.put(it);           // нет сети — ещё раз позже
        }
        plan.put("items", keep);
        p.edit().putString("senior_plan", plan.toString()).commit();
    }

    private static JSONObject day(SharedPreferences p, String d) {
        try {
            JSONObject x = new JSONObject(p.getString("senior_day", "{}"));
            if (d.equals(x.optString("d"))) return x;
        } catch (Exception ignored) { }
        return null;
    }

    private static boolean has(JSONArray a, String v) {
        for (int i = 0; a != null && i < a.length(); i++) if (v.equals(a.optString(i))) return true;
        return false;
    }

    static boolean needed(SharedPreferences p, JSONObject it) {
        String key = it.optString("key"), kind = it.optString("kind");
        JSONObject d = day(p, it.optString("day"));
        if (d != null && has(d.optJSONArray("sent"), key)) return false;
        JSONArray done;
        try { done = new JSONArray(p.getString("done_inbox", "[]")); } catch (Exception e) { done = new JSONArray(); }
        if ("late".equals(kind)) {
            String rid = it.optString("rid");
            long med = it.optLong("med");
            for (int i = 0; i < done.length(); i++) {
                JSONObject x = done.optJSONObject(i);
                if (x != null && rid.equals(x.optString("id")) && x.optLong("at") >= med - 3600_000L) return false;
            }
            return true;
        }
        if ("noon".equals(kind)) {
            if (d != null) { JSONArray t = d.optJSONArray("talk"); if (t != null && t.length() > 0) return false; }
            long from = it.optLong("at") - 12 * 3600_000L;       // с полуночи этого дня
            for (int i = 0; i < done.length(); i++) {
                JSONObject x = done.optJSONObject(i);
                if (x != null && x.optLong("at") >= from && x.optString("title").startsWith("Выпить")) return false;
            }
            return true;
        }
        return false;
    }

    static boolean send(JSONObject plan, JSONObject it) {
        String base = plan.optString("base"), token = plan.optString("token"), link = plan.optString("link");
        JSONArray ps = it.optJSONArray("payloads");
        if (base.isEmpty() || token.isEmpty() || ps == null) return true;   // некуда — не копим
        int ok = 0;
        for (int i = 0; i < ps.length(); i++) {
            try {
                HttpURLConnection h = (HttpURLConnection) new URL(base + "?p=/close/send").openConnection();
                h.setConnectTimeout(15000); h.setReadTimeout(20000);
                h.setRequestMethod("POST"); h.setDoOutput(true);
                h.setRequestProperty("Authorization", "Bearer " + token);
                h.setRequestProperty("Content-Type", "application/json");
                if (!link.isEmpty() && !link.equals(token)) h.setRequestProperty("X-Sync-Link", link);
                byte[] b = ps.getJSONObject(i).toString().getBytes(StandardCharsets.UTF_8);
                OutputStream o = h.getOutputStream(); o.write(b); o.close();
                int code = h.getResponseCode();
                if (code < 300) ok++;
                else if (code >= 400 && code < 500) ok++;      // отказ облака (близкий удалён) — повтор не поможет
                h.disconnect();
            } catch (Exception ignored) { }
        }
        return ok > 0;
    }

    static void markSent(SharedPreferences p, JSONObject it) {
        try {
            String d = it.optString("day");
            JSONObject x = day(p, d);
            if (x == null) x = new JSONObject().put("d", d).put("talk", new JSONArray()).put("sent", new JSONArray()).put("alerts", new JSONArray());
            JSONArray s = x.optJSONArray("sent");
            if (s == null) { s = new JSONArray(); x.put("sent", s); }
            s.put(it.optString("key"));
            p.edit().putString("senior_day", x.toString()).commit();
        } catch (Exception ignored) { }
    }
}
