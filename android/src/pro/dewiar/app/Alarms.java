package pro.dewiar.app;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;

/** Напоминания, будильники, таймеры: список — JSON в SharedPreferences "alarms" (items), каждое ставится в AlarmManager
 *  (звонит и при выключенном экране; после перезагрузки BootReceiver и запуск MainActivity ставят всё заново).
 *  Срабатывание приходит в AlarmReceiver → fired(): повтор переставляется, разовое убирается, всё пишется в журнал (log).
 *  Ставит и снимает интерфейс: Dewiar.alarmSet / alarmCancel (Bridge.java) по инструменту set_reminder в app.js.
 *  Сигнал опознаётся по id: requestCode = id.hashCode() — тот же id заменяет прежний сигнал, а не добавляет второй. */
public final class Alarms {
    private static final String P = "alarms";
    private Alarms() { }

    private static SharedPreferences sp(Context c) { return c.getSharedPreferences(P, Context.MODE_PRIVATE); }

    public static synchronized JSONArray list(Context c) {
        try { return new JSONArray(sp(c).getString("items", "[]")); } catch (Exception e) { return new JSONArray(); }
    }

    private static void save(Context c, JSONArray a) {
        sp(c).edit().putString("items", a.toString()).apply();
        CaptureWidget.refresh(c);           // на значке «Записать» — ближайшее напоминание
    }

    /** item: {id, at (мс), title, kind: reminder|alarm|timer, repeat: ""|daily|weekdays|weekly|d:0123 (дни, пн = 0)} */
    public static synchronized void put(Context c, JSONObject item) throws Exception {
        JSONArray a = list(c), out = new JSONArray();
        for (int i = 0; i < a.length(); i++) if (!a.getJSONObject(i).getString("id").equals(item.getString("id"))) out.put(a.getJSONObject(i));
        // повторяющееся на уже прошедшее время («по будням в 17:30», поставлено в 17:43) — не звонить сразу, а в следующий раз (№56)
        long now = System.currentTimeMillis();
        while (item.getLong("at") < now - 60000 && !item.optString("repeat").isEmpty()) item.put("at", next(item));
        out.put(item);
        save(c, out);
        schedule(c, item);
        if ("timer".equals(item.optString("kind"))) TimerNote.show(c, item);    // идущий таймер — с отсчётом в шторке
    }

    public static synchronized boolean remove(Context c, String id) {
        JSONArray a = list(c), out = new JSONArray();
        boolean found = false;
        for (int i = 0; i < a.length(); i++) {
            JSONObject x = a.optJSONObject(i);
            if (x == null) continue;
            if (x.optString("id").equals(id)) found = true; else out.put(x);
        }
        save(c, out);
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        am.cancel(pi(c, id, ""));
        TimerNote.hide(c, id);
        return found;
    }

    public static synchronized JSONObject get(Context c, String id) {
        JSONArray a = list(c);
        for (int i = 0; i < a.length(); i++) { JSONObject x = a.optJSONObject(i); if (x != null && x.optString("id").equals(id)) return x; }
        return null;
    }

    static PendingIntent pi(Context c, String id, String title) {
        Intent i = new Intent(c, AlarmReceiver.class).setAction("pro.dewiar.ALARM").putExtra("id", id).putExtra("title", title);
        return PendingIntent.getBroadcast(c, id.hashCode(), i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /** Поставить сигнал в AlarmManager. Точные будильники можно ставить, если система разрешила (Compat.canExact);
     *  «alarm» — через setAlarmClock: его Android не откладывает ради экономии батареи. Нажатие на значок — открыть приложение. */
    static void schedule(Context c, JSONObject x) throws Exception {
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        long at = x.getLong("at");
        PendingIntent p = pi(c, x.getString("id"), x.optString("title"));
        Intent show = new Intent(c, MainActivity.class);
        PendingIntent sp = PendingIntent.getActivity(c, 7, show, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        if (Compat.canExact(am)) {
            if ("alarm".equals(x.optString("kind"))) am.setAlarmClock(new AlarmManager.AlarmClockInfo(at, sp), p);  // значок будильника в шторке
            else am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);
        } else {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);                    // без точных — с погрешностью
        }
    }

    /** Поставить заново весь список (после перезагрузки, обновления, при запуске). Разовое, пропущенное не больше минуты
     *  назад, ещё сработает сразу; более старое — убирается; повторяющееся переносится на ближайший будущий раз. */
    public static synchronized void rescheduleAll(Context c) {
        JSONArray a = list(c), keep = new JSONArray();
        long now = System.currentTimeMillis();
        for (int i = 0; i < a.length(); i++) {
            JSONObject x = a.optJSONObject(i);
            if (x == null) continue;
            try {
                if (x.getLong("at") < now - 60000 && x.optString("repeat").isEmpty()) continue;   // давно прошедшее — убрать
                while (x.getLong("at") < now && !x.optString("repeat").isEmpty()) x.put("at", next(x));
                schedule(c, x);
                keep.put(x);
            } catch (Exception ignored) { }
        }
        save(c, keep);
    }

    /** Следующий раз для повторяющегося: daily — +1 день, weekly — +7, weekdays — ближайший будний, «d:0123» — ближайший
     *  из этих дней (понедельник = 0, как в Python; 30.10: «по будням, кроме пятницы»). Считаем днями календаря, а не по
     *  24 часа: при переходе на летнее время будильник не съедет на час. */
    static long next(JSONObject x) throws Exception {
        java.util.Calendar k = java.util.Calendar.getInstance();
        k.setTimeInMillis(x.getLong("at"));
        String r = x.optString("repeat");
        String set = r.startsWith("d:") ? r.substring(2) : null;
        if (set != null && !set.matches("[0-6]+")) set = null;
        for (int i = 0; i < 8; i++) {
            k.add(java.util.Calendar.DAY_OF_MONTH, "weekly".equals(r) ? 7 : 1);
            int dow = k.get(java.util.Calendar.DAY_OF_WEEK);           // воскресенье = 1 … суббота = 7
            int py = (dow + 5) % 7;                                    // понедельник = 0 … воскресенье = 6
            if ("weekdays".equals(r) && (dow == java.util.Calendar.SATURDAY || dow == java.util.Calendar.SUNDAY)) continue;
            if (set != null && set.indexOf((char) ('0' + py)) < 0) continue;
            break;
        }
        return k.getTimeInMillis();
    }

    /** Сработало: повторяющееся — переставить на следующий раз, разовое — убрать. -> само напоминание. */
    public static synchronized JSONObject fired(Context c, String id) {
        JSONObject x = get(c, id);
        if (x == null) return null;
        try {
            if (!x.optString("repeat").isEmpty()) { x.put("at", next(x)); put(c, x); }
            else remove(c, id);
            log(c, x);
        } catch (Exception ignored) { }
        return x;
    }

    /** Журнал сработавших (последние 300) — для Dewiar.alarmHistory. */
    static void log(Context c, JSONObject x) {
        try {
            JSONArray h = new JSONArray(sp(c).getString("log", "[]"));
            h.put(new JSONObject().put("title", x.optString("title")).put("kind", x.optString("kind")).put("time", System.currentTimeMillis()));
            JSONArray out = new JSONArray();
            for (int i = Math.max(0, h.length() - 300); i < h.length(); i++) out.put(h.get(i));
            sp(c).edit().putString("log", out.toString()).apply();
        } catch (Exception ignored) { }
    }

    public static String history(Context c) { return sp(c).getString("log", "[]"); }
}
