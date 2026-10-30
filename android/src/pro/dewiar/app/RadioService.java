package pro.dewiar.app;

import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.IBinder;
import java.lang.reflect.Constructor;

/** Радио при погасшем экране (30.10, отзыв: «понравилось использовать в машине, но включаю радио — и как только экран
 *  гаснет, всё гаснет»). Поток играет в Radio (MediaPlayer), но без службы переднего плана Android усыпляет или
 *  замораживает приложение, когда экран гаснет, — и звук обрывается. Эта служба — как у музыкальных приложений:
 *  уведомление «Радио · станция» с кнопками «Пауза» / «Дальше играть» и «Стоп»; медиасессия — кнопки машины по Bluetooth,
 *  наушников и экрана блокировки управляют радио, название станции видно на экране машины; Wi-Fi держим, пока играет.
 *  Состояние приходит из Radio.emit() через sync(); играет или подключается — передний план; пауза — уведомление
 *  остаётся (можно смахнуть), стоп или ошибка — служба уходит. */
public class RadioService extends Service {
    static final int NOTE = 7310;
    static final String CH = "radio";
    static final String A_SHOW = "pro.dewiar.RADIO_SHOW", A_PLAY = "pro.dewiar.RADIO_PLAY", A_PAUSE = "pro.dewiar.RADIO_PAUSE",
            A_STOP = "pro.dewiar.RADIO_STOP";
    static volatile String state = "stopped", name = "";
    static volatile boolean byUser;              // пауза человеком (а не звонком или навигатором) — можно уйти с переднего плана
    private MediaSession ms;
    private WifiManager.WifiLock wifi;

    /** Радио сменило состояние (Radio.emit). Запускаем, пока приложение на экране (так требует Android); дальше служба
     *  уже идёт — и обновления доходят и из фона. */
    static void sync(Context c, String st, String nm, String by) {
        state = st == null ? "stopped" : st;
        name = nm == null ? "" : nm;
        byUser = "user".equals(by);
        Intent i = new Intent(c, RadioService.class).setAction(A_SHOW);
        try {
            if ("stopped".equals(state) || "error".equals(state)) { c.stopService(new Intent(c, RadioService.class)); return; }
            try { c.startService(i); return; } catch (IllegalStateException bg) { /* фон — ниже */ }
            if (Build.VERSION.SDK_INT >= 26) Context.class.getMethod("startForegroundService", Intent.class).invoke(c, i);
        } catch (Throwable ignored) { }
    }

    @Override public IBinder onBind(Intent i) { return null; }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String a = intent == null ? A_SHOW : String.valueOf(intent.getAction());
        Radio r = Radio.current();
        if (A_PLAY.equals(a)) { if (r != null) r.resume(); else { stopSelf(); return START_NOT_STICKY; } }
        else if (A_PAUSE.equals(a)) { if (r != null) r.pause(); }
        else if (A_STOP.equals(a)) { if (r != null) r.stop(); stopSelf(); return START_NOT_STICKY; }
        show(state);
        return START_NOT_STICKY;                 // процесс убили — радио всё равно нет, поднимать службу незачем
    }

    private PendingIntent act(String action, int code) {
        return PendingIntent.getService(this, code, new Intent(this, RadioService.class).setAction(action),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    @SuppressWarnings("deprecation")
    private void show(String st) {
        boolean playing = "playing".equals(st), connecting = "preparing".equals(st), paused = "paused".equals(st);
        // пауза на время звонка или ответа ассистента — держим передний план: иначе Android усыпит приложение, и после
        // звонка радио само не продолжит
        boolean hold = playing || connecting || (paused && !byUser);
        session(st);
        channel(this);
        Notification.Builder b = Compat.builder(this, CH);
        android.graphics.Bitmap lg = Compat.logo(this);
        if (lg != null) b.setLargeIcon(lg);
        PendingIntent open = PendingIntent.getActivity(this, 31, new Intent(this, MainActivity.class).setAction("pro.dewiar.RADIO"),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        b.setSmallIcon(R.drawable.ic_stat).setContentTitle(name.isEmpty() ? "Радио" : name)
                .setContentText(connecting ? "Радио · подключаюсь…" : paused ? "Радио · пауза" : "Радио · играет")
                .setContentIntent(open).setShowWhen(false).setOngoing(hold).setDeleteIntent(act(A_STOP, 34));
        if (paused) b.addAction(new Notification.Action.Builder(android.R.drawable.ic_media_play, "Играть", act(A_PLAY, 32)).build());
        else b.addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause, "Пауза", act(A_PAUSE, 33)).build());
        b.addAction(new Notification.Action.Builder(android.R.drawable.ic_menu_close_clear_cancel, "Стоп", act(A_STOP, 34)).build());
        try {
            Notification.MediaStyle style = new Notification.MediaStyle().setShowActionsInCompactView(0, 1);
            if (ms != null) style.setMediaSession(ms.getSessionToken());
            b.setStyle(style);
        } catch (Throwable ignored) { }
        Notification n = b.build();
        try {
            if (hold) {
                startForeground(NOTE, n);
                wifi(true);
            } else {
                // пауза: с переднего плана уходим, уведомление оставляем — «Играть» из него продолжит радио
                startForeground(NOTE, n);
                stopForeground(false);
                wifi(false);
                ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).notify(NOTE, n);
            }
        } catch (Throwable e) {
            stopSelf();
        }
    }

    /** Медиасессия: кнопки машины, наушников и экрана блокировки, название станции на экране машины. */
    private void session(String st) {
        try {
            if (ms == null) {
                ms = new MediaSession(this, "DewiarRadio");
                ms.setCallback(new MediaSession.Callback() {
                    @Override public void onPlay() { Radio r = Radio.current(); if (r != null) r.resume(); }
                    @Override public void onPause() { Radio r = Radio.current(); if (r != null) r.pause(); }
                    @Override public void onStop() { Radio r = Radio.current(); if (r != null) r.stop(); }
                });
                setFlags(ms);
            }
            ms.setMetadata(new MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE, name.isEmpty() ? "Радио" : name)
                    .putString(MediaMetadata.METADATA_KEY_ARTIST, "Радио · Dewiar").build());
            int s = "playing".equals(st) ? PlaybackState.STATE_PLAYING : "preparing".equals(st) ? PlaybackState.STATE_BUFFERING
                    : "paused".equals(st) ? PlaybackState.STATE_PAUSED : PlaybackState.STATE_STOPPED;
            ms.setPlaybackState(new PlaybackState.Builder().setActions(PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE
                    | PlaybackState.ACTION_PLAY_PAUSE | PlaybackState.ACTION_STOP).setState(s, PlaybackState.PLAYBACK_POSITION_UNKNOWN, 1f).build());
            ms.setActive(s != PlaybackState.STATE_STOPPED);
        } catch (Throwable ignored) { }
    }

    @SuppressWarnings("deprecation")
    private static void setFlags(MediaSession m) {
        try { m.setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS | MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS); } catch (Throwable ignored) { }
    }

    /** Wi-Fi не засыпает, пока играет (иначе на некоторых телефонах поток рвётся через минуту после того, как погас экран). */
    @SuppressWarnings("deprecation")
    private void wifi(boolean on) {
        try {
            if (on) {
                if (wifi == null) {
                    WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                    wifi = wm.createWifiLock(3 /* WIFI_MODE_FULL_HIGH_PERF */, "dewiar:radio");
                    wifi.setReferenceCounted(false);
                }
                if (!wifi.isHeld()) wifi.acquire();
            } else if (wifi != null && wifi.isHeld()) wifi.release();
        } catch (Throwable ignored) { }
    }

    @Override public void onDestroy() {
        wifi(false);
        try { stopForeground(true); } catch (Throwable ignored) { }
        try { ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(NOTE); } catch (Throwable ignored) { }
        if (ms != null) { try { ms.setActive(false); ms.release(); } catch (Throwable ignored) { } ms = null; }
        super.onDestroy();
    }

    /** Канал «Радио» — тихий (без звука уведомления), видно в шторке и на экране блокировки. */
    static void channel(Context c) {
        if (Build.VERSION.SDK_INT < 26) return;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            Class<?> chc = Class.forName("android.app.NotificationChannel");
            Constructor<?> k = chc.getConstructor(String.class, CharSequence.class, int.class);
            Object ch = k.newInstance(CH, "Радио", 2 /* IMPORTANCE_LOW */);
            chc.getMethod("setShowBadge", boolean.class).invoke(ch, false);
            NotificationManager.class.getMethod("createNotificationChannel", chc).invoke(nm, ch);
        } catch (Throwable ignored) { }
    }
}
