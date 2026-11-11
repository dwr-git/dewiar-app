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
        stamp(item);
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

    static PendingIntent pi(Context c, String id, String title) { return pi(c, id, title, 0); }

    /** due — на какое время поставлен сигнал: приёмник сравнит с текущим временем и напишет «(должно было в …)». */
    static PendingIntent pi(Context c, String id, String title, long due) {
        Intent i = new Intent(c, AlarmReceiver.class).setAction("pro.dewiar.ALARM").putExtra("id", id).putExtra("title", title).putExtra("due", due);
        return PendingIntent.getBroadcast(c, id.hashCode(), i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /** Поставить сигнал в AlarmManager. 0.87 (владелец 11.11: «напоминание приходит на час позже, как будто телефон спал»):
     *  каждое напоминание звонит и открывает окно — значит, это будильник для человека, и ставится через setAlarmClock
     *  (раньше так — только «alarm», напоминания и таймеры шли через setExactAndAllowWhileIdle: в глубоком сне Android и
     *  оболочки Xiaomi/Samsung/Tecno его придерживают, а setAlarmClock выводят из сна точно в срок и не откладывают).
     *  Точные запрещены (Android 12+ без «Будильников и напоминаний») — setAndAllowWhileIdle: система может задержать
     *  его на десятки минут; поэтому приложение показывает карточку «Напоминания вовремя» (app.js remHealthCard).
     *  Как поставили — в "mode" (clock | inexact): видно в отчёте и в проверке. Нажатие на значок будильника — приложение. */
    static void schedule(Context c, JSONObject x) throws Exception {
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        long at = x.getLong("at");
        PendingIntent p = pi(c, x.getString("id"), x.optString("title"), at);
        Intent show = new Intent(c, MainActivity.class);
        PendingIntent sp = PendingIntent.getActivity(c, 7, show, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String mode = "inexact";
        if (Compat.canExact(am)) {
            try {
                am.setAlarmClock(new AlarmManager.AlarmClockInfo(at, sp), p);         // точно в срок, и из глубокого сна
                mode = "clock";
            } catch (SecurityException e) {                                       // право отозвали между проверкой и вызовом
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);
            }
        } else {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, p);                    // без точных — с погрешностью
        }
        if (!mode.equals(sp(c).getString("mode", ""))) sp(c).edit().putString("mode", mode).apply();
    }

    /** Часовой пояс и «время на стене» в момент постановки: сменится пояс — будильник и повторяющееся встанут на те же
     *  часы (AlarmTime.moved), а не уедут на разницу поясов. */
    static void stamp(JSONObject x) throws Exception {
        java.util.TimeZone tz = java.util.TimeZone.getDefault();
        x.put("tz", tz.getID()).put("wall", AlarmTime.wall(x.getLong("at"), tz));
    }

    /** Поставить заново весь список: после перезагрузки, обновления приложения, смены времени или пояса (BootReceiver),
     *  когда разрешили точные будильники и при каждом запуске (система или оболочка телефона могла сбросить сигналы —
     *  Xiaomi и Tecno при «очистке» снимают их вместе с приложением). Пояс сменился — будильник и повторяющееся встают на
     *  те же часы на стене. Пропущенное (телефон был выключен, сигнал сняли) не пропадает молча, как раньше: до получаса —
     *  звонит сейчас, до суток — тихое уведомление «пропущено», в обоих — «(должно было в …)»; старше суток — в журнал. */
    public static synchronized void rescheduleAll(Context c) {
        JSONArray a = list(c), keep = new JSONArray();
        long now = System.currentTimeMillis();
        java.util.TimeZone tz = java.util.TimeZone.getDefault();
        java.util.List<JSONObject> late = new java.util.ArrayList<>();
        AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
        for (int i = 0; i < a.length(); i++) {
            JSONObject x = a.optJSONObject(i);
            if (x == null) continue;
            try {
                x.put("at", AlarmTime.moved(x.getLong("at"), x.optString("kind"), x.optString("repeat"), x.optString("tz"), x.optString("wall"), tz));
                long at = x.getLong("at");
                int m = AlarmTime.missed(at, now);
                if (m != AlarmTime.NOT_MISSED) {
                    JSONObject was = new JSONObject(x.toString()).put("_due", at).put("_loud", m == AlarmTime.MISSED_LOUD).put("_drop", m == AlarmTime.MISSED_DROP);
                    late.add(was);
                    if (x.optString("repeat").isEmpty()) { am.cancel(pi(c, x.getString("id"), "")); continue; }   // разовое — показали, из списка
                    while (x.getLong("at") < now) x.put("at", next(x));
                }
                stamp(x);
                schedule(c, x);
                keep.put(x);
            } catch (Exception ignored) { }
        }
        save(c, keep);
        for (JSONObject x : late) {
            long due = x.optLong("_due");
            log(c, x, due, x.optBoolean("_drop") ? "dropped" : "missed");
            if (x.optBoolean("_drop")) continue;
            if (!x.optString("note", "").isEmpty()) AlarmReceiver.noteSet(c, x.optString("id"), x.optString("note", ""));
            AlarmReceiver.missed(c, x.optString("id"), x.optString("title", "Напоминание"), x.optString("kind", "reminder"), x.optString("who", ""), due, x.optBoolean("_loud"));
        }
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

    /** Сработало: повторяющееся — переставить на следующий раз, разовое — убрать. -> само напоминание; в "_due" — на
     *  какое время оно было поставлено (по нему — «должно было в …» и опоздание в журнале). */
    public static synchronized JSONObject fired(Context c, String id) {
        JSONObject x = get(c, id);
        if (x == null) return null;
        try {
            long due = x.getLong("at");
            if (!x.optString("repeat").isEmpty()) { x.put("at", next(x)); put(c, x); }
            else remove(c, id);
            log(c, x, due, "");
            x.put("_due", due);
        } catch (Exception ignored) { }
        return x;
    }

    /** Журнал сработавших (последние 300) — для Dewiar.alarmHistory и подсказки «Напоминания вовремя»: due — на когда было
     *  поставлено, late — опоздание в мс (сон телефона, оболочка придержала сигнал), mode — как стоял сигнал (clock |
     *  inexact), how — "" сработало само, missed — показали после перезагрузки/запуска, dropped — пропущено больше суток. */
    static void log(Context c, JSONObject x, long due, String how) {
        try {
            JSONArray h = new JSONArray(sp(c).getString("log", "[]"));
            long now = System.currentTimeMillis();
            JSONObject e = new JSONObject().put("title", x.optString("title")).put("kind", x.optString("kind")).put("time", now);
            if (due > 0) e.put("due", due).put("late", Math.max(0, now - due));
            e.put("mode", sp(c).getString("mode", ""));
            if (!how.isEmpty()) e.put("how", how);
            h.put(e);
            JSONArray out = new JSONArray();
            for (int i = Math.max(0, h.length() - 300); i < h.length(); i++) out.put(h.get(i));
            sp(c).edit().putString("log", out.toString()).apply();
        } catch (Exception ignored) { }
    }

    public static String history(Context c) { return sp(c).getString("log", "[]"); }
}
