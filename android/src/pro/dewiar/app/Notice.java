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
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

/** «Лира заметила» (0.97, владелец 14.11: «иногда активировалась и находила полезное — предупредила о дожде… а не так,
 *  что каждое утро будет злить»). Раз в ~3 часа (JobScheduler, нужна сеть) телефон сам смотрит, есть ли повод:
 *  дождь, снег, гроза, жара, мороз или сильный ветер сегодня (open-meteo по координатам города), день рождения близкого
 *  сегодня или завтра (из памяти — готовит интерфейс). Есть — одно уведомление, не чаще раза в день и не в тихие часы
 *  (до 8 и после 21). Нет — тишина. Что смотреть, кладёт интерфейс через Bridge.notice: {on, lat, lon, place, who,
 *  days:[{date:"YYYY-MM-DD", text}]}; пусто — выключено. */
public class Notice extends JobService {
    static final int JOB = 4712;

    static void schedule(Context c, boolean on) {
        JobScheduler js = (JobScheduler) c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if (js == null) return;
        if (!on) { js.cancel(JOB); return; }
        for (JobInfo j : js.getAllPendingJobs()) if (j.getId() == JOB) return;
        JobInfo.Builder b = new JobInfo.Builder(JOB, new ComponentName(c, Notice.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(3 * 60 * 60 * 1000L).setPersisted(true);
        try { js.schedule(b.build()); } catch (Throwable ignored) { }
    }

    @Override public boolean onStartJob(final JobParameters p) {
        new Thread(new Runnable() { @Override public void run() {
            try { check(Notice.this, System.currentTimeMillis()); } catch (Throwable ignored) { }
            jobFinished(p, false);
        } }).start();
        return true;
    }

    @Override public boolean onStopJob(JobParameters p) { return false; }

    static String day(long now) { return new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date(now)); }

    /** Проверить и, если есть повод, показать. Возвращает текст уведомления (или "" — промолчали). */
    static String check(Context c, long now) throws Exception {
        SharedPreferences sp = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
        String raw = sp.getString("notice", "");
        if (raw == null || raw.isEmpty()) return "";
        JSONObject cfg = new JSONObject(raw);
        if (!cfg.optBoolean("on")) return "";
        Calendar cal = Calendar.getInstance(); cal.setTimeInMillis(now);
        int h = cal.get(Calendar.HOUR_OF_DAY);
        if (h < 8 || h >= 21) return "";                                   // тихие часы
        String today = day(now);
        if (today.equals(sp.getString("notice_day", ""))) return "";       // сегодня уже говорили
        boolean en = "en".equals(cfg.optString("lang"));
        List<String> why = new ArrayList<>();
        JSONArray days = cfg.optJSONArray("days");
        String tomorrow = day(now + 86400000L);
        if (days != null) for (int i = 0; i < days.length(); i++) {
            JSONObject d = days.optJSONObject(i); if (d == null) continue;
            String dt = d.optString("date"), t = d.optString("text");
            if (t.isEmpty()) continue;
            if (dt.equals(today)) why.add((en ? "today " : "сегодня ") + t);
            else if (dt.equals(tomorrow) && h >= 17) why.add((en ? "tomorrow " : "завтра ") + t);
        }
        if (cfg.has("lat") && cfg.has("lon")) {
            try { String w = weather(cfg.optDouble("lat"), cfg.optDouble("lon"), h, en); if (!w.isEmpty()) why.add(0, w); } catch (Throwable ignored) { }
        }
        if (why.isEmpty()) return "";
        String who = cfg.optString("who", "Лира");
        StringBuilder sb = new StringBuilder();
        for (String s : why) { if (sb.length() > 0) sb.append(". "); sb.append(Character.toUpperCase(s.charAt(0))).append(s.substring(1)); }
        String text = sb.toString() + ".";
        sp.edit().putString("notice_day", today).putInt("notice_n", sp.getInt("notice_n", 0) + 1).apply();
        show(c, who + (en ? " noticed" : " заметила"), text);
        return text;
    }

    /** Повод из прогноза на остаток дня: осадки с вероятностью от 60 %, гроза, жара от 30°, мороз до −15°, ветер от 15 м/с. */
    static String weather(double lat, double lon, int hourNow, boolean en) throws Exception {
        String u = String.format(Locale.US, "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
                + "&hourly=precipitation_probability,weather_code,temperature_2m,wind_gusts_10m&forecast_days=1&timezone=auto&wind_speed_unit=ms", lat, lon);
        JSONObject hr = new JSONObject(get(u)).getJSONObject("hourly");
        return reason(hr, hourNow, en);
    }

    static String reason(JSONObject hr, int hourNow, boolean en) {
        JSONArray pp = hr.optJSONArray("precipitation_probability"), wc = hr.optJSONArray("weather_code"),
                tt = hr.optJSONArray("temperature_2m"), wg = hr.optJSONArray("wind_gusts_10m");
        if (wc == null) return "";
        int rainAt = -1, snowAt = -1, stormAt = -1; double tmax = -99, tmin = 99, gust = 0;
        for (int i = Math.max(0, hourNow); i < Math.min(22, wc.length()); i++) {
            int code = wc.optInt(i); int prob = pp == null ? 100 : pp.optInt(i, 0);
            if (code >= 95 && stormAt < 0) stormAt = i;
            else if (((code >= 71 && code <= 77) || code == 85 || code == 86) && prob >= 60 && snowAt < 0) snowAt = i;
            else if (((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) && prob >= 60 && rainAt < 0) rainAt = i;
            if (tt != null) { tmax = Math.max(tmax, tt.optDouble(i, -99)); tmin = Math.min(tmin, tt.optDouble(i, 99)); }
            if (wg != null) gust = Math.max(gust, wg.optDouble(i, 0));
        }
        if (stormAt >= 0) return en ? "a thunderstorm around " + stormAt + ":00 — better wait it out indoors" : "около " + stormAt + ":00 гроза — лучше переждать под крышей";
        if (snowAt >= 0) return en ? "snow around " + snowAt + ":00 — dress warmly and take care on the road" : "около " + snowAt + ":00 снег — одевайтесь теплее и осторожнее на дороге";
        if (rainAt >= 0) return en ? "rain around " + rainAt + ":00 — take an umbrella" : "около " + rainAt + ":00 дождь — возьмите зонт";
        if (tmax >= 30) return en ? "heat up to " + Math.round(tmax) + "° — take water" : "жара до " + Math.round(tmax) + "° — возьмите воду";
        if (tmin <= -15) return en ? "frost down to " + Math.round(tmin) + "° — dress warmly" : "мороз до " + Math.round(tmin) + "° — одевайтесь теплее";
        if (gust >= 15) return en ? "strong wind, gusts up to " + Math.round(gust) + " m/s" : "сильный ветер, порывы до " + Math.round(gust) + " м/с";
        return "";
    }

    static String get(String u) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(u).openConnection();
        c.setConnectTimeout(10000); c.setReadTimeout(15000);
        try (InputStream in = c.getInputStream()) {
            ByteArrayOutputStream b = new ByteArrayOutputStream(); byte[] buf = new byte[8192]; int n;
            while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
            return b.toString("UTF-8");
        } finally { c.disconnect(); }
    }

    static void show(Context c, String title, String text) {
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm == null) return;
        Intent open = new Intent(c, MainActivity.class).setAction("pro.dewiar.NOTICE");
        PendingIntent pi = PendingIntent.getActivity(c, JOB, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = Compat.builder(c, Compat.CH_INFO);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle(title).setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text)).setAutoCancel(true).setContentIntent(pi);
        nm.notify(JOB, b.build());
    }
}
