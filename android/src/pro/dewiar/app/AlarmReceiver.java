package pro.dewiar.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import org.json.JSONObject;

/** Время пришло (сигнал от AlarmManager, поставленный в Alarms.schedule): отметить срабатывание в Alarms.fired
 *  (повтор — на следующий раз, разовое — убрать) и показать уведомление поверх всего с полноэкранным окном будильника
 *  (AlarmActivity) — даже на заблокированном экране. Номер уведомления — id.hashCode(): по нему AlarmActivity его убирает.
 *
 *  0.87 (владелец 11.11: «разблокирую экран — не могу найти напоминание, музыка звучит, приходится искать приложение»):
 *  звучащее напоминание всегда можно остановить, не входя в приложение —
 *   • уведомление видно на экране блокировки целиком (VISIBILITY_PUBLIC), кнопки «Стоп» и «Отложить на 10 мин»
 *     (у дела — ещё «Сделано ✓»); смахнули уведомление — звук тоже смолкает (DISMISS);
 *   • пока окно не на экране, звучит само уведомление (FLAG_INSISTENT — повторяется, пока не откроют шторку или не
 *     нажмут кнопку), а не невидимое окно: окно берёт звук на себя, только когда его видно (AlarmActivity.onResume);
 *     окно спрятали (разблокировали, «Домой») — звук возвращается уведомлению (handback);
 *   • через AlarmTime.RING_MS звук смолкает сам (EXPIRE), уведомление остаётся тихим с теми же кнопками;
 *   • открыли приложение, пока звенит, — сразу окно с «Стоп» (reopen из MainActivity.onResume);
 *   • опоздавшее (телефон спал, был выключен) — с припиской «(должно было в 14:00)». */
public class AlarmReceiver extends BroadcastReceiver {
    static final String DONE = "pro.dewiar.ALARM_DONE", SNOOZE = "pro.dewiar.ALARM_SNOOZE", MADE = "pro.dewiar.ALARM_MADE",
            DISMISS = "pro.dewiar.ALARM_DISMISS", EXPIRE = "pro.dewiar.ALARM_EXPIRE";

    @Override public void onReceive(Context c, Intent in) {
        String id = in.getStringExtra("id");
        if (id == null) return;
        String act = in.getAction() == null ? "" : in.getAction();
        // кнопки уведомления — на телефоне и на часах (Honor/Huawei, Wear OS и другие повторяют кнопки уведомления)
        if (DONE.equals(act) && in.getBooleanExtra("cancel", false)) {    // «Отменить» у идущего таймера (TimerNote)
            Alarms.remove(c, id);
            MainActivity.poke("alarms");
            return;
        }
        if (EXPIRE.equals(act)) { expire(c, id); return; }
        if (DISMISS.equals(act)) {                                     // уведомление смахнули — человек его видел: тишина
            stopped(c, id);
            AlarmActivity.closeIfOpen(id);
            return;
        }
        if (DONE.equals(act) || SNOOZE.equals(act) || MADE.equals(act)) {
            if (MADE.equals(act)) made(c, id, in.getStringExtra("title"));
            if (SNOOZE.equals(act)) AlarmActivity.snoozeLater(c, id, in.getStringExtra("title"), in.getStringExtra("kind"), in.getStringExtra("who"));
            stopped(c, id);
            ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(id.hashCode());
            AlarmActivity.closeIfOpen(id);
            return;
        }
        // сигнал уже обработан (пропущенное показали при запуске и переставили на следующий раз) — не звонить второй раз
        JSONObject cur = Alarms.get(c, id);
        if (cur != null && cur.optLong("at") - System.currentTimeMillis() > AlarmTime.DUE_SOON_MS) {
            try { Alarms.schedule(c, cur); } catch (Exception ignored) { }
            return;
        }
        JSONObject x = Alarms.fired(c, id);           // null — в списке уже нет: показываем по данным самого сигнала
        if (x != null && !x.optString("note", "").isEmpty()) noteSet(c, id, x.optString("note", ""));
        String title = x != null ? x.optString("title", "Напоминание") : in.getStringExtra("title");
        String kind = x != null ? x.optString("kind", "reminder") : "reminder";
        long due = x != null ? x.optLong("_due", 0) : in.getLongExtra("due", 0);
        show(c, id, title == null ? "Напоминание" : title, kind, x != null ? x.optString("who", "") : "", due);
    }

    /** who — персонаж, который ставил напоминание (его лицо и имя — в уведомлении, см. Faces); "" — текущий. */
    static void show(Context c, String id, String title, String kind, String who) { show(c, id, title, kind, who, 0); }

    static void show(Context c, String id, String title, String kind, String who, long due) { post(c, id, title, kind, who, due, true, true); }

    /** Окно будильника открылось и звучит само: то же уведомление — в канал без звука (звук уведомления смолкает, в шторке
     *  оно остаётся, нажатие снова открывает окно). Канал — важный: часы получают только «важные» уведомления. */
    static void quiet(Context c, String id, String title, String kind, String who) { quiet(c, id, title, kind, who, 0); }

    static void quiet(Context c, String id, String title, String kind, String who, long due) { post(c, id, title, kind, who, due, false, false); }

    /** Окно спрятали, пока звенит (разблокировали экран, нажали «Домой», открыли другое приложение): звук — снова у
     *  уведомления, которое видно в шторке и на экране блокировки с кнопками «Стоп» и «Отложить». Окно не открываем. */
    static void handback(Context c, String id, String title, String kind, String who, long due) { post(c, id, title, kind, who, due, true, false); }

    /** Пропущенное, пока телефон был выключен или сигнал сняла система (Alarms.rescheduleAll): до получаса — звонит, как
     *  обычно; позже — тихое уведомление, чтобы не звенеть ни с того ни с сего; в тексте — «(должно было в …)». */
    static void missed(Context c, String id, String title, String kind, String who, long due, boolean loud) {
        post(c, id, title, kind, who, due, loud, loud);
    }

    @SuppressWarnings("deprecation")
    private static void post(Context c, String id, String title, String kind, String who, long due, boolean loud, boolean open) {
        long now = System.currentTimeMillis();
        long fired = now;
        if (loud) {                                                      // звенит: запомнить, когда начал (для «смолкнуть сам»)
            JSONObject r = ringing(c, id);
            if (r != null && !open) fired = r.optLong("fired", now);     // вернули звук от окна — отсчёт прежний
            if (now - fired >= AlarmTime.RING_MS) loud = false;          // уже отзвенел — только тихо
            else ringStart(c, id, title, kind, who, due, fired);
        }
        Intent full = new Intent(c, AlarmActivity.class).putExtra("id", id).putExtra("title", title).putExtra("kind", kind).putExtra("who", who)
                .putExtra("fired", loud ? fired : 0L).putExtra("due", due)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_USER_ACTION);
        PendingIntent fp = PendingIntent.getActivity(c, id.hashCode(), full, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String head = "alarm".equals(kind) ? "⏰ Будильник" : "timer".equals(kind) ? "⏱ Таймер" : "🔔 Напоминание";
        boolean soft = Sounds.soft(c, kind);                                // №72: напоминание — громкостью уведомлений
        Notification.Builder b = Compat.builder(c, loud ? Sounds.channel(c, soft) : Sounds.quietChannel(c));
        if (loud && android.os.Build.VERSION.SDK_INT < 26) b.setSound(Sounds.uri(c, Sounds.current(c)), Sounds.attrs(soft));   // до Android 8 звук — у самого уведомления
        String name = Faces.dress(c, b, who);
        String late = AlarmTime.lateNote(due, now, java.util.TimeZone.getDefault());
        // с обликом: заголовок — имя персонажа, вид сигнала — значком в тексте и подписью в шапке (так читается и на часах)
        String text = (name.isEmpty() ? title : head.substring(0, head.indexOf(' ')) + " " + title) + late + (noteFor(c, id).isEmpty() ? "" : " 📎");
        b.setContentTitle(name.isEmpty() ? head : name)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setCategory(Notification.CATEGORY_ALARM)
                .setPriority(loud ? Notification.PRIORITY_MAX : Notification.PRIORITY_HIGH)
                .setVisibility(Notification.VISIBILITY_PUBLIC)               // на экране блокировки — текст и кнопки, не «Скрыто»
                .setAutoCancel(false)                                        // остаётся, пока не нажали «Стоп»/«Отложить» или не смахнули
                .setOnlyAlertOnce(!loud)
                .setShowWhen(true)
                .setWhen(due > 0 ? due : now)
                .setContentIntent(fp)
                .setDeleteIntent(broadcast(c, DISMISS, id, title, kind, who));   // смахнули — звук смолкает
        if (loud) b.setFullScreenIntent(fp, true);
        boolean task = !"alarm".equals(kind) && !"timer".equals(kind);      // напоминание о деле — его можно отметить сделанным
        b.addAction(action(c, DONE, id, title, kind, who, "Стоп"));
        if (!"timer".equals(kind)) b.addAction(action(c, SNOOZE, id, title, kind, who, "Отложить на 10 мин"));
        if (task) b.addAction(action(c, MADE, id, title, kind, who, "Сделано ✓"));
        if (!name.isEmpty()) b.setSubText(head.substring(head.indexOf(' ') + 1));
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        Notification n = b.build();
        // звенит, пока окна не видно: звук уведомления повторяется, пока не нажмут кнопку, не откроют шторку или окно не
        // возьмёт звук (тихое обновление того же уведомления) — и никогда не звучит «из ниоткуда» без видимой кнопки
        if (loud) n.flags |= Notification.FLAG_INSISTENT;
        // тихое — обновлением того же уведомления, а не снятием: часы (Honor/Huawei Health) видят одно уведомление,
        // а не «появилось и пропало»; звук уведомления к этому времени уже отзвучал (окно ждёт AlarmActivity.SOUND_DELAY_MS)
        nm.notify(id.hashCode(), n);
        if (!loud || !open) return;
        // приложение на экране — окно сразу; из фона Android 10+ окно не откроет — тогда остаётся уведомление
        try { c.startActivity(full); } catch (Throwable ignored) { }
    }

    // ---------- что звенит сейчас: SharedPreferences "alarms" → ringing {id: {title, kind, who, due, fired}} ----------

    private static android.content.SharedPreferences prefs(Context c) { return c.getSharedPreferences("alarms", Context.MODE_PRIVATE); }

    private static synchronized JSONObject ringAll(Context c) {
        try { return new JSONObject(prefs(c).getString("ringing", "{}")); } catch (Exception e) { return new JSONObject(); }
    }

    static synchronized JSONObject ringing(Context c, String id) { return ringAll(c).optJSONObject(id); }

    /** Начал звенеть: запомнить и поставить «смолкнуть» через RING_MS (AlarmManager — процесс могут и усыпить). */
    private static synchronized void ringStart(Context c, String id, String title, String kind, String who, long due, long fired) {
        try {
            JSONObject all = ringAll(c);
            all.put(id, new JSONObject().put("title", title).put("kind", kind).put("who", who).put("due", due).put("fired", fired));
            prefs(c).edit().putString("ringing", all.toString()).apply();
            android.app.AlarmManager am = (android.app.AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            PendingIntent p = broadcast(c, EXPIRE, id, title, kind, who);
            long at = fired + AlarmTime.RING_MS;
            if (Compat.canExact(am)) am.setExactAndAllowWhileIdle(android.app.AlarmManager.RTC_WAKEUP, at, p);
            else am.setAndAllowWhileIdle(android.app.AlarmManager.RTC_WAKEUP, at, p);
        } catch (Throwable ignored) { }
    }

    /** Больше не звенит (Стоп, Отложить, Сделано, смахнули, окно закрыли): забыть и снять «смолкнуть». */
    static synchronized void stopped(Context c, String id) {
        try {
            JSONObject all = ringAll(c);
            if (all.has(id)) { all.remove(id); prefs(c).edit().putString("ringing", all.toString()).apply(); }
            ((android.app.AlarmManager) c.getSystemService(Context.ALARM_SERVICE)).cancel(broadcast(c, EXPIRE, id, "", "", ""));
        } catch (Throwable ignored) { }
    }

    /** Отзвенело RING_MS, а никто не ответил: звук смолкает (и у окна), уведомление остаётся тихим — с кнопками. */
    private static void expire(Context c, String id) {
        JSONObject r = ringing(c, id);
        if (r == null) return;
        stopped(c, id);
        AlarmActivity.silenceIfOpen(id);
        post(c, id, r.optString("title", "Напоминание"), r.optString("kind", "reminder"), r.optString("who", ""), r.optLong("due", 0), false, false);
    }

    /** Открыли приложение, пока звенит (не нашли окно — «приходится искать приложение»): сразу окно с «Стоп». */
    static void reopen(Context c) {
        try {
            JSONObject all = ringAll(c);
            java.util.Iterator<String> it = all.keys();
            long now = System.currentTimeMillis();
            while (it.hasNext()) {
                String id = it.next();
                JSONObject r = all.optJSONObject(id);
                if (r == null || now - r.optLong("fired") >= AlarmTime.RING_MS) continue;
                c.startActivity(new Intent(c, AlarmActivity.class).putExtra("id", id).putExtra("title", r.optString("title"))
                        .putExtra("kind", r.optString("kind")).putExtra("who", r.optString("who")).putExtra("due", r.optLong("due"))
                        .putExtra("fired", 0L).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                return;
            }
        } catch (Throwable ignored) { }
    }

    /** Напоминание с вложениями (app.js addAlarm(…, note)): id заметки с фото и файлами. Разовое при срабатывании уходит из
     *  списка Alarms, поэтому связь «напоминание → заметка» живёт отдельно (до 40 последних) — для окна (кнопка «Посмотреть
     *  вложения») и для «Отложить» (отложенное — с теми же вложениями). */
    static synchronized void noteSet(Context c, String id, String note) {
        try {
            android.content.SharedPreferences p = c.getSharedPreferences("alarms", Context.MODE_PRIVATE);
            JSONObject m;
            try { m = new JSONObject(p.getString("notes", "{}")); } catch (Exception e) { m = new JSONObject(); }
            m.put(id, note);
            while (m.length() > 40) m.remove(m.keys().next());
            p.edit().putString("notes", m.toString()).apply();
        } catch (Exception ignored) { }
    }

    static String noteFor(Context c, String id) {
        try {
            return new JSONObject(c.getSharedPreferences("alarms", Context.MODE_PRIVATE).getString("notes", "{}")).optString(id, "");
        } catch (Exception e) { return ""; }
    }

    /** «Сделано ✓» — дело в очередь done_inbox (SharedPreferences "dewiar"): приложение заберёт её в журнал дел
     *  (doneInbox в app.js) — сразу, если открыто, иначе при следующем открытии. */
    static synchronized void made(Context c, String id, String title) {
        try {
            android.content.SharedPreferences p = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
            org.json.JSONArray q;
            try { q = new org.json.JSONArray(p.getString("done_inbox", "[]")); } catch (Exception e) { q = new org.json.JSONArray(); }
            String base = id.replaceAll("-s\\d+$", "");                 // отложенное «через 10 минут» — то же дело
            q.put(new JSONObject().put("id", base).put("title", title == null ? "Дело" : title).put("at", System.currentTimeMillis()));
            p.edit().putString("done_inbox", q.toString()).commit();
        } catch (Exception ignored) { }
        MainActivity.poke("done_inbox");
    }

    private static PendingIntent broadcast(Context c, String act, String id, String title, String kind, String who) {
        Intent i = new Intent(c, AlarmReceiver.class).setAction(act).putExtra("id", id).putExtra("title", title).putExtra("kind", kind).putExtra("who", who);
        return PendingIntent.getBroadcast(c, (act + id).hashCode(), i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    @SuppressWarnings("deprecation")
    private static Notification.Action action(Context c, String act, String id, String title, String kind, String who, String label) {
        return new Notification.Action.Builder(R.drawable.ic_stat, label, broadcast(c, act, id, title, kind, who)).build();
    }
}
