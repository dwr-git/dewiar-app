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
 *  (AlarmActivity) — даже на заблокированном экране. Номер уведомления — id.hashCode(): по нему AlarmActivity его убирает. */
public class AlarmReceiver extends BroadcastReceiver {
    static final String DONE = "pro.dewiar.ALARM_DONE", SNOOZE = "pro.dewiar.ALARM_SNOOZE", MADE = "pro.dewiar.ALARM_MADE";

    @Override public void onReceive(Context c, Intent in) {
        String id = in.getStringExtra("id");
        if (id == null) return;
        // кнопки уведомления — на телефоне и на часах (Honor/Huawei, Wear OS и другие повторяют кнопки уведомления)
        if (DONE.equals(in.getAction()) && in.getBooleanExtra("cancel", false)) {    // «Отменить» у идущего таймера (TimerNote)
            Alarms.remove(c, id);
            MainActivity.poke("alarms");
            return;
        }
        if (DONE.equals(in.getAction()) || SNOOZE.equals(in.getAction()) || MADE.equals(in.getAction())) {
            if (MADE.equals(in.getAction())) made(c, id, in.getStringExtra("title"));
            if (SNOOZE.equals(in.getAction())) AlarmActivity.snoozeLater(c, id, in.getStringExtra("title"), in.getStringExtra("kind"), in.getStringExtra("who"));
            ((NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE)).cancel(id.hashCode());
            AlarmActivity.closeIfOpen(id);
            return;
        }
        JSONObject x = Alarms.fired(c, id);           // null — в списке уже нет: показываем по данным самого сигнала
        if (x != null && !x.optString("note", "").isEmpty()) noteSet(c, id, x.optString("note", ""));
        String title = x != null ? x.optString("title", "Напоминание") : in.getStringExtra("title");
        String kind = x != null ? x.optString("kind", "reminder") : "reminder";
        show(c, id, title == null ? "Напоминание" : title, kind, x != null ? x.optString("who", "") : "");
    }

    /** who — персонаж, который ставил напоминание (его лицо и имя — в уведомлении, см. Faces); "" — текущий. */
    static void show(Context c, String id, String title, String kind, String who) { post(c, id, title, kind, who, true); }

    /** Окно будильника открылось и звучит само: то же уведомление — в канал без звука (звук уведомления смолкает, в шторке
     *  оно остаётся, нажатие снова открывает окно). Канал — важный: часы получают только «важные» уведомления. */
    static void quiet(Context c, String id, String title, String kind, String who) { post(c, id, title, kind, who, false); }

    @SuppressWarnings("deprecation")
    private static void post(Context c, String id, String title, String kind, String who, boolean loud) {
        Intent full = new Intent(c, AlarmActivity.class).putExtra("id", id).putExtra("title", title).putExtra("kind", kind).putExtra("who", who)
                .putExtra("fired", loud ? System.currentTimeMillis() : 0L)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_NO_USER_ACTION);
        PendingIntent fp = PendingIntent.getActivity(c, id.hashCode(), full, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String head = "alarm".equals(kind) ? "⏰ Будильник" : "timer".equals(kind) ? "⏱ Таймер" : "🔔 Напоминание";
        boolean soft = Sounds.soft(c, kind);                                // №72: напоминание — громкостью уведомлений
        Notification.Builder b = Compat.builder(c, loud ? Sounds.channel(c, soft) : Sounds.quietChannel(c));
        if (loud && android.os.Build.VERSION.SDK_INT < 26) b.setSound(Sounds.uri(c, Sounds.current(c)), Sounds.attrs(soft));   // до Android 8 звук — у самого уведомления
        String name = Faces.dress(c, b, who);
        // с обликом: заголовок — имя персонажа, вид сигнала — значком в тексте и подписью в шапке (так читается и на часах)
        String text = (name.isEmpty() ? title : head.substring(0, head.indexOf(' ')) + " " + title) + (noteFor(c, id).isEmpty() ? "" : " 📎");
        b.setContentTitle(name.isEmpty() ? head : name)
                .setContentText(text)
                .setStyle(new Notification.BigTextStyle().bigText(text))
                .setCategory(Notification.CATEGORY_ALARM)
                .setPriority(loud ? Notification.PRIORITY_MAX : Notification.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setOnlyAlertOnce(!loud)
                .setContentIntent(fp);
        if (loud) b.setFullScreenIntent(fp, true);
        boolean task = !"alarm".equals(kind) && !"timer".equals(kind);      // напоминание о деле — его можно отметить сделанным
        if (task) b.addAction(action(c, MADE, id, title, kind, who, "Сделано ✓"));
        if (!"timer".equals(kind)) b.addAction(action(c, SNOOZE, id, title, kind, who, "Через 10 минут"));
        b.addAction(action(c, DONE, id, title, kind, who, "Понял"));
        if (!name.isEmpty()) b.setSubText(head.substring(head.indexOf(' ') + 1));
        NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
        // тихое — обновлением того же уведомления, а не снятием: часы (Honor/Huawei Health) видят одно уведомление,
        // а не «появилось и пропало»; звук уведомления к этому времени уже отзвучал (окно ждёт AlarmActivity.SOUND_DELAY_MS)
        nm.notify(id.hashCode(), b.build());
        if (!loud) return;
        // приложение на экране — окно сразу; из фона Android 10+ окно не откроет — тогда остаётся уведомление
        try { c.startActivity(full); } catch (Throwable ignored) { }
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

    @SuppressWarnings("deprecation")
    private static Notification.Action action(Context c, String act, String id, String title, String kind, String who, String label) {
        Intent i = new Intent(c, AlarmReceiver.class).setAction(act).putExtra("id", id).putExtra("title", title).putExtra("kind", kind).putExtra("who", who);
        PendingIntent pi = PendingIntent.getBroadcast(c, (act + id).hashCode(), i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Action.Builder(R.drawable.ic_stat, label, pi).build();
    }
}
