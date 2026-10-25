package pro.dewiar.app;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.widget.RemoteViews;
import org.json.JSONObject;

/** Значок «Записать» на рабочем столе (отзыв 16.10: «быстро и надёжно закинуть мысль»). Нажатие открывает приложение
 *  с действием pro.dewiar.CAPTURE: app.js слушает, сказанное — в заметки «Идеи» (или напоминание, если «напомни…»),
 *  и приложение уходит обратно на рабочий стол. Включён по умолчанию; выключить — Настройки → «Значок «Записать»»
 *  (компонент выключается: значок пропадает из списка виджетов). Добавить на экран — requestPinAppWidget (Android 8+). */
public class CaptureWidget extends AppWidgetProvider {
    @Override public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        for (int id : ids) m.updateAppWidget(id, views(c));
    }

    static RemoteViews views(Context c) {
        String look = look(c);
        RemoteViews v = new RemoteViews(c.getPackageName(), "light".equals(look) ? R.layout.widget_capture_light
                : "dark".equals(look) ? R.layout.widget_capture : R.layout.widget_capture_glass);
        v.setTextViewText(R.id.w_sub, nextLine(c));
        Intent i = new Intent(c, MainActivity.class).setAction("pro.dewiar.CAPTURE")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        v.setOnClickPendingIntent(R.id.w_root, PendingIntent.getActivity(c, 7301, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
        return v;
    }

    static ComponentName cn(Context c) { return new ComponentName(c, CaptureWidget.class); }

    /** Вид значка (25.10, владелец: «может стекло матовое… стильно и красиво»): «glass» — матовое стекло (по умолчанию, хорошо
     *  на любых обоях), «light» — светлый неоморфизм, «dark» — матово-чёрный; «theme» — как тема приложения. pref widget_look. */
    static String look(Context c) {
        String w = "";
        try { w = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE).getString("widget_look", ""); } catch (Throwable e) { }
        if ("theme".equals(w)) return light(c) ? "light" : "dark";
        return "light".equals(w) || "dark".equals(w) ? w : "glass";
    }

    /** Светлая тема приложения? (app.js applyLook пишет её в pref look_body: «neusky light neu») — значок светлый
     *  (24.10, владелец: «Лира оформлена красиво в белом — можно ли так же красиво эту кнопку?»). */
    static boolean light(Context c) {
        try {
            return (" " + c.getSharedPreferences("dewiar", Context.MODE_PRIVATE).getString("look_body", "") + " ").contains(" light ");
        } catch (Throwable e) { return false; }
    }

    /** Подпись значка (отзыв 17.10: «может туда вывести что-то полезное»): ближайшее напоминание или будильник в
     *  ближайшие 7 дней — «⏰ 18:00 · Позвонить маме», «⏰ завтра 9:00 · …», «⏰ пт 9:00 · …»; нет — «идея или напоминание».
     *  Обновляется при каждом изменении списка (Alarms.save → refresh) и раз в полчаса (updatePeriodMillis). */
    static String nextLine(Context c) {
        try {
            org.json.JSONArray a = Alarms.list(c);
            long now = System.currentTimeMillis(), best = Long.MAX_VALUE;
            String title = "";
            for (int i = 0; i < a.length(); i++) {
                JSONObject x = a.optJSONObject(i);
                if (x == null || "timer".equals(x.optString("kind"))) continue;
                long at = x.optLong("at");
                if (at > now && at < best) { best = at; title = x.optString("title"); }
            }
            if (best == Long.MAX_VALUE || best - now > 7L * 86400000L) return "идея или напоминание";
            java.util.Calendar k = java.util.Calendar.getInstance(), t = java.util.Calendar.getInstance();
            k.setTimeInMillis(best);
            int days = (int) Math.round((day0(k) - day0(t)) / 86400000.0);
            String hm = String.format(java.util.Locale.ROOT, "%d:%02d", k.get(java.util.Calendar.HOUR_OF_DAY), k.get(java.util.Calendar.MINUTE));
            String[] wd = {"", "вс", "пн", "вт", "ср", "чт", "пт", "сб"};
            String when = days == 0 ? hm : days == 1 ? "завтра " + hm : wd[k.get(java.util.Calendar.DAY_OF_WEEK)] + " " + hm;
            return "⏰ " + (title.isEmpty() ? when : when + " · " + title);
        } catch (Exception e) { return "идея или напоминание"; }
    }

    private static long day0(java.util.Calendar x) {
        java.util.Calendar d = (java.util.Calendar) x.clone();
        d.set(java.util.Calendar.HOUR_OF_DAY, 0); d.set(java.util.Calendar.MINUTE, 0); d.set(java.util.Calendar.SECOND, 0); d.set(java.util.Calendar.MILLISECOND, 0);
        return d.getTimeInMillis();
    }

    /** Перерисовать все значки на экранах (список напоминаний изменился). */
    static void refresh(Context c) {
        try {
            AppWidgetManager m = AppWidgetManager.getInstance(c);
            int[] ids = m.getAppWidgetIds(cn(c));
            if (ids.length > 0) m.updateAppWidget(ids, views(c));
        } catch (Exception ignored) { }
    }

    /** -> {on: значок доступен, placed: сколько на экранах, pin: можно добавить кнопкой из приложения} */
    static JSONObject state(Context c) {
        JSONObject o = new JSONObject();
        try {
            int st = c.getPackageManager().getComponentEnabledSetting(cn(c));
            int placed = AppWidgetManager.getInstance(c).getAppWidgetIds(cn(c)).length;
            o.put("on", st != PackageManager.COMPONENT_ENABLED_STATE_DISABLED).put("placed", placed).put("pin", pinSupported(c)).put("look", look(c));
        } catch (Exception ignored) { }
        return o;
    }

    static void set(Context c, boolean on) {
        c.getPackageManager().setComponentEnabledSetting(cn(c), on ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED
                : PackageManager.COMPONENT_ENABLED_STATE_DISABLED, PackageManager.DONT_KILL_APP);
    }

    // requestPinAppWidget — Android 8 (API 26); собираем против 23, поэтому отражением
    static boolean pinSupported(Context c) {
        if (android.os.Build.VERSION.SDK_INT < 26) return false;
        try { return (Boolean) AppWidgetManager.class.getMethod("isRequestPinAppWidgetSupported").invoke(AppWidgetManager.getInstance(c)); }
        catch (Throwable e) { return false; }
    }

    static boolean pin(Context c) {
        if (!pinSupported(c)) return false;
        try {
            return (Boolean) AppWidgetManager.class.getMethod("requestPinAppWidget", ComponentName.class, android.os.Bundle.class, PendingIntent.class)
                    .invoke(AppWidgetManager.getInstance(c), cn(c), null, null);
        } catch (Throwable e) { return false; }
    }
}
