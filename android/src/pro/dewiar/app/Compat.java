package pro.dewiar.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.content.Context;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

/** Новые API Android (26+, 31+) — через отражение: tools/build_apk.sh собирает против android.jar API 23, а работать
 *  надо на любых. Здесь каналы уведомлений, Notification.Builder с каналом и проверка права на точные будильники.
 *  Ошибка отражения не роняет приложение — откатываемся к старому поведению. */
public final class Compat {
    // каналы: будильники и напоминания — alarm_<звук> (важный, звук — выбранный, см. Sounds; прежний общий «alarms»
    // удаляется), info — сообщения ассистента (обычный). Звук и важность канала Android запоминает при создании:
    // поменять их можно только новым id
    // 0.9.12 (владелец 29.10: «у Viber свой звук — сделаем свой»): сообщения ассистента, новости и сообщения близких —
    // канал «dw_note» с фирменным звуком res/raw/dewiar_note.ogg (tools/sounds/notify_sound.py); прежний «info» удаляется
    public static final String CH_ALARM = "alarms", CH_INFO = "dw_note", CH_OLD_INFO = "info";
    private Compat() { }

    public static void channels(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            Class<?> chc = Class.forName("android.app.NotificationChannel");
            Constructor<?> k = chc.getConstructor(String.class, CharSequence.class, int.class);
            Method create = NotificationManager.class.getMethod("createNotificationChannel", chc);
            Sounds.channel(c);                              // будильники — канал под выбранный звук (Sounds)
            Object b = k.newInstance(CH_INFO, "Сообщения, новости и близкие", 3 /* IMPORTANCE_DEFAULT */);
            AudioAttributes aa = new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_NOTIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();
            chc.getMethod("setSound", Uri.class, AudioAttributes.class).invoke(b, note(c), aa);
            create.invoke(nm, b);
            try { NotificationManager.class.getMethod("deleteNotificationChannel", String.class).invoke(nm, CH_OLD_INFO); }
            catch (Throwable ignored) { }
        } catch (Throwable ignored) { }
    }

    @SuppressWarnings("deprecation")
    public static Notification.Builder builder(Context c, String channel) {
        Notification.Builder b = null;
        if (Build.VERSION.SDK_INT >= 26) {
            try {
                b = (Notification.Builder) Notification.Builder.class.getConstructor(Context.class, String.class).newInstance(c, channel);
            } catch (Throwable ignored) { }
        }
        if (b == null) b = new Notification.Builder(c);
        // знак Dewiar в уведомлениях — чёрно-белый, как логотип (без цвета система красила его в синий акцент темы)
        b.setColor(BRAND);
        if (Build.VERSION.SDK_INT < 26 && CH_INFO.equals(channel)) b.setSound(note(c));   // до Android 8 звук — у уведомления
        return b;
    }

    /** Фирменный звук уведомлений (по имени ресурса: канал хранит адрес навсегда, а числа R.raw меняются). */
    public static Uri note(Context c) {
        return Uri.parse("android.resource://" + c.getPackageName() + "/raw/dewiar_note");
    }

    /** Знак Dewiar крупно — справа в уведомлении (новости, сообщения ассистента): маленький значок система красит в свой
     *  цвет (на части телефонов — в синий, что бы мы ни просили), а крупная картинка остаётся как есть. */
    public static android.graphics.Bitmap logo(Context c) {
        try {
            return android.graphics.BitmapFactory.decodeResource(c.getResources(), R.mipmap.ic_launcher);
        } catch (Throwable e) { return null; }
    }

    /** Цвет знака в уведомлениях: почти чёрный (белый знак на нём — как оригинальный логотип). */
    static final int BRAND = 0xFF111111;

    /** Можно ли ставить точные будильники (Android 12+ спрашивает разрешение; USE_EXACT_ALARM из манифеста даёт его
     *  с Android 13 сразу). Не удалось спросить — считаем, что можно. */
    public static boolean canExact(android.app.AlarmManager am) {
        if (Build.VERSION.SDK_INT < 31) return true;
        try { return (Boolean) android.app.AlarmManager.class.getMethod("canScheduleExactAlarms").invoke(am); }
        catch (Throwable e) { return true; }
    }

    /** Можно ли показывать окно напоминания поверх блокировки (полноэкранное уведомление). Android 14+ спрашивает
     *  разрешение USE_FULL_SCREEN_INTENT отдельно (Настройки → Приложения → Dewiar → «Полноэкранные уведомления»);
     *  без него вместо окна — только всплывающее уведомление. До 14 — можно. Не удалось спросить — считаем, что можно. */
    public static boolean canFullScreen(Context c) {
        if (Build.VERSION.SDK_INT < 34) return true;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            return (Boolean) NotificationManager.class.getMethod("canUseFullScreenIntent").invoke(nm);
        } catch (Throwable e) { return true; }
    }

    /** Уведомления приложения включены и канал напоминаний не выключен человеком (важность 0). */
    public static boolean notifyOn(Context c) {
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (Build.VERSION.SDK_INT >= 24 && !(Boolean) NotificationManager.class.getMethod("areNotificationsEnabled").invoke(nm)) return false;
            if (Build.VERSION.SDK_INT >= 26) {
                Object ch = NotificationManager.class.getMethod("getNotificationChannel", String.class).invoke(nm, Sounds.channel(c, Sounds.softOn(c)));
                if (ch != null && (Integer) ch.getClass().getMethod("getImportance").invoke(ch) == 0) return false;
            }
            return true;
        } catch (Throwable e) { return true; }
    }
}
