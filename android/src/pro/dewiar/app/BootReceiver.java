package pro.dewiar.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** После перезагрузки телефона и обновления приложения — поставить все напоминания заново (Alarms.rescheduleAll):
 *  AlarmManager перезагрузку не переживает, а список хранится у нас в настройках.
 *  0.87: и при смене времени или часового пояса (перелёт, телефон сам поправил время по сети — будильник «в 7» остаётся
 *  в 7 по новым часам), и когда человек разрешил точные будильники (сигналы, стоявшие «примерно», встают точно).
 *  QUICKBOOT_POWERON — «быстрое включение» части телефонов (HTC, некоторые Xiaomi/Tecno), BOOT_COMPLETED они не шлют. */
public class BootReceiver extends BroadcastReceiver {
    static final String EXACT_CHANGED = "android.app.action.SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED";

    @Override public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (a == null) return;
        boolean boot = Intent.ACTION_BOOT_COMPLETED.equals(a) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)
                || "android.intent.action.QUICKBOOT_POWERON".equals(a) || "com.htc.intent.action.QUICKBOOT_POWERON".equals(a);
        boolean clock = Intent.ACTION_TIME_CHANGED.equals(a) || Intent.ACTION_TIMEZONE_CHANGED.equals(a) || EXACT_CHANGED.equals(a);
        if (!boot && !clock) return;
        // QUICKBOOT система не защищает — его может прислать любое приложение (рецензия 0.87): верим только сразу после
        // включения телефона (первые 10 минут), иначе «перестановка» превращала бы неточный будильник в «пропущенный».
        if (a.endsWith("QUICKBOOT_POWERON") && android.os.SystemClock.elapsedRealtime() > 10 * 60_000L) return;
        Alarms.rescheduleAll(c);
        if (clock) { SeniorGuard.arm(c); return; }
        CloseLive.apply(c);                              // «Близкие» на связи — и после перезагрузки
        SeniorGuard.arm(c);                              // «Для старших»: присмотр при закрытом приложении
    }
}
