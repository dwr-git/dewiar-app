package pro.dewiar.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** После перезагрузки телефона и обновления приложения — поставить все напоминания заново (Alarms.rescheduleAll):
 *  AlarmManager перезагрузку не переживает, а список хранится у нас в настройках. */
public class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (Intent.ACTION_BOOT_COMPLETED.equals(a) || Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)) {
            Alarms.rescheduleAll(c);
            CloseLive.apply(c);                              // «Близкие» на связи — и после перезагрузки
            SeniorGuard.arm(c);                              // «Для старших»: присмотр при закрытом приложении
        }
    }
}
