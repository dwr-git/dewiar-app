package pro.dewiar.app;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import java.lang.reflect.Method;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Микрофон Bluetooth-наушников (отчёт №51, 14.10: «Лиру слышу в наушниках, а она меня — нет; отошёл на 4 шага —
 *  совсем перестала слышать»). Android сам отдаёт наушникам только звук (A2DP), а записывает встроенным микрофоном
 *  телефона. Чтобы слушать микрофоном наушников, нужен голосовой канал гарнитуры (SCO) — его и включаем на время
 *  слушания: Android 12+ — setCommunicationDevice (через отражение: собираемся против API 23), раньше — startBluetoothSco
 *  с ожиданием «подключено». После слушания канал выключается не сразу, а через 1,2 с тишины: в разговоре сеансы идут
 *  подряд, и щелчок переключения на каждом был бы хуже; к ответу голосом наушники уже снова в хорошем качестве (A2DP).
 *  Не вышло — слушаем микрофоном телефона, как раньше. */
final class BtMic {
    private static final Handler main = new Handler(Looper.getMainLooper());
    private static volatile boolean on;
    private static final Runnable offR = new Runnable() { @Override public void run() { offNow(app); } };
    private static Context app;

    private BtMic() { }

    /** Подключена гарнитура с микрофоном (Bluetooth SCO)? Разрешений не нужно. */
    static boolean available(Context c) {
        try {
            AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
            if (!am.isBluetoothScoAvailableOffCall()) return false;
            for (AudioDeviceInfo d : am.getDevices(AudioManager.GET_DEVICES_INPUTS))
                if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) return true;
        } catch (Throwable ignored) { }
        return false;
    }

    static boolean isOn() { return on; }

    /** Включить микрофон наушников (ждёт до waitMs — вызывать не из главного потока). -> true, если включён. */
    static boolean start(Context c, int waitMs) {
        app = c.getApplicationContext();
        main.removeCallbacks(offR);
        if (on) return true;
        if (!available(c)) return false;
        AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
        try {
            if (Build.VERSION.SDK_INT >= 31) {
                Method avail = AudioManager.class.getMethod("getAvailableCommunicationDevices");
                Method set = AudioManager.class.getMethod("setCommunicationDevice", AudioDeviceInfo.class);
                @SuppressWarnings("unchecked") List<AudioDeviceInfo> list = (List<AudioDeviceInfo>) avail.invoke(am);
                for (AudioDeviceInfo d : list) {
                    if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) {
                        am.setMode(AudioManager.MODE_IN_COMMUNICATION);
                        on = Boolean.TRUE.equals(set.invoke(am, d));
                        if (!on) am.setMode(AudioManager.MODE_NORMAL);
                        else Thread.sleep(Math.min(waitMs, 400));          // канал поднимается не мгновенно
                        return on;
                    }
                }
                return false;
            }
            final CountDownLatch up = new CountDownLatch(1);
            BroadcastReceiver r = new BroadcastReceiver() {
                @Override public void onReceive(Context x, Intent i) {
                    if (i.getIntExtra(AudioManager.EXTRA_SCO_AUDIO_STATE, -1) == AudioManager.SCO_AUDIO_STATE_CONNECTED) up.countDown();
                }
            };
            c.getApplicationContext().registerReceiver(r, new IntentFilter(AudioManager.ACTION_SCO_AUDIO_STATE_UPDATED));
            try {
                am.setMode(AudioManager.MODE_IN_COMMUNICATION);
                am.startBluetoothSco();
                am.setBluetoothScoOn(true);
                on = up.await(waitMs, TimeUnit.MILLISECONDS);
            } finally {
                try { c.getApplicationContext().unregisterReceiver(r); } catch (Throwable ignored) { }
            }
            if (!on) offNow(c);
            return on;
        } catch (Throwable e) {
            offNow(c);
            return false;
        }
    }

    /** Слушание кончилось: выключить через 1,2 с, если не начнётся новое. */
    static void stopSoon() {
        if (!on) return;
        main.removeCallbacks(offR);
        main.postDelayed(offR, 1200);
    }

    /** Выключить сейчас (перед ответом голосом, при выходе). */
    static void offNow(Context c) {
        main.removeCallbacks(offR);
        if (c == null) return;
        try {
            AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
            if (Build.VERSION.SDK_INT >= 31) {
                try { AudioManager.class.getMethod("clearCommunicationDevice").invoke(am); } catch (Throwable ignored) { }
            } else {
                am.setBluetoothScoOn(false);
                am.stopBluetoothSco();
            }
            // №284 (пакет 27.10): «голосом отвечает один раз, потом только после перезапуска» — если гарнитура так и не
            // подключилась (on = false), режим связи оставался включённым, и голос уходил «в трубку». Возвращаем всегда
            if (on || am.getMode() == AudioManager.MODE_IN_COMMUNICATION) am.setMode(AudioManager.MODE_NORMAL);
        } catch (Throwable ignored) { }
        on = false;
    }
}
