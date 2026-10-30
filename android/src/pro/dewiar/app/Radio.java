package pro.dewiar.app;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONObject;

/** Радио внутри ассистента: поток играет здесь же (MediaPlayer), а не в браузере или другом приложении.
 *  Поэтому «стоп», «пауза», «дальше» работают голосом, а пока ассистент слушает и говорит — радио приглушается.
 *  Состояние уходит в интерфейс событием {type:"radio", state: preparing|playing|paused|stopped|error, name, error, by}.
 *  Всё, что трогает MediaPlayer, идёт в главном потоке (ui.post): методы зовутся из моста JavaScript.
 *  Список станций — data/radio.json (сборка кладёт его в radio.js), выбирает станцию app.js. */
final class Radio implements AudioManager.OnAudioFocusChangeListener {
    // многие станции (101.ru, hostingradio…) не отдают звук «непонятным» программам — представляемся браузером
    private static final String UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36";
    private static Radio inst;                       // один проигрыватель на всё приложение: экран пересоздали — радио то же
    private final Context c;
    private Net.Sink sink;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private MediaPlayer mp;
    private String name = "", url = "", state = "stopped", error = "";
    private float duck = 1f, focusDuck = 1f, vol = 1f;   // громкость = vol (своя) × duck (говорит ассистент) × focusDuck (навигатор и т. п.)
    private int gen;                                 // новая станция — старые обратные вызовы не в счёт
    private boolean held;                            // замолчали на время звонка — после него продолжим
    private String by = "";                          // кто поставил паузу: user — человек, focus — другой звук (распознавание, звонок)

    private Radio(Context c, Net.Sink sink) { this.c = c.getApplicationContext(); this.sink = sink; }

    /** Общий проигрыватель: события — в последний открытый экран. Второго MediaPlayer не бывает. */
    static synchronized Radio get(Context c, Net.Sink sink) {
        if (inst == null) inst = new Radio(c, sink);
        else inst.sink = sink;
        return inst;
    }

    /** Проигрыватель, если он уже есть (кнопки уведомления и машины — RadioService). */
    static synchronized Radio current() { return inst; }

    private AudioManager am() { return (AudioManager) c.getSystemService(Context.AUDIO_SERVICE); }

    private void emit() {
        android.util.Log.i("Dewiar", "радио: " + state + " «" + name + "» " + error + " " + url);
        try { sink.event("radio", new JSONObject().put("state", state).put("name", name).put("error", error).put("by", by)); } catch (Exception ignored) { }
        RadioService.sync(c, state, name, by);           // 30.10: играет — служба переднего плана, иначе с погасшим экраном звук обрывается
    }

    private void applyVolume() {
        if (mp == null) return;
        float v = Math.max(0f, Math.min(1f, vol * duck * focusDuck));
        try { mp.setVolume(v, v); } catch (Throwable ignored) { }
    }

    void play(final String u, final String n) {
        ui.post(new Runnable() { @Override public void run() { start(u, n); } });
    }

    @SuppressWarnings("deprecation")
    private void start(String u, String n) {
        drop();                                      // прежняя станция смолкает сразу, даже если её поток завис
        final int my = ++gen;
        name = n == null ? "" : n;
        url = u == null ? "" : u;
        error = "";
        by = "";
        state = "preparing";
        emit();
        try {
            mp = new MediaPlayer();
            mp.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build());
            mp.setWakeMode(c, PowerManager.PARTIAL_WAKE_LOCK);
            Map<String, String> h = new HashMap<String, String>();
            h.put("User-Agent", UA);
            h.put("Icy-MetaData", "0");
            mp.setDataSource(c, Uri.parse(url), h);
            mp.setOnPreparedListener(new MediaPlayer.OnPreparedListener() {
                @Override public void onPrepared(MediaPlayer p) {
                    if (my != gen) return;
                    am().requestAudioFocus(Radio.this, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN);
                    applyVolume();
                    p.start();
                    state = "playing";
                    emit();
                    ui.postDelayed(new Runnable() {      // «играет», а звука нет (плейлист вместо потока, пустой эфир) — честно скажем
                        @Override public void run() {
                            boolean on = false;
                            try { on = mp != null && mp.isPlaying(); } catch (Throwable ignored) { }
                            if (my == gen && "playing".equals(state) && !on) fail("станция молчит — поток не идёт");
                        }
                    }, 5000);
                }
            });
            mp.setOnErrorListener(new MediaPlayer.OnErrorListener() {
                @Override public boolean onError(MediaPlayer p, int what, int extra) {
                    if (my != gen) return true;
                    fail(what == MediaPlayer.MEDIA_ERROR_SERVER_DIED ? "станция прервала поток"
                            : extra == -1004 ? "станция не отвечает (сеть)" : extra == -1010 ? "формат потока не поддерживается"
                            : extra == -110 ? "станция не ответила вовремя" : "станция не играет (" + what + "/" + extra + ")");
                    return true;
                }
            });
            mp.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {
                @Override public void onCompletion(MediaPlayer p) { if (my == gen) fail("поток закончился"); }
            });
            mp.prepareAsync();
            ui.postDelayed(new Runnable() {          // поток так и не пошёл — не висим вечно в «подключаюсь»
                @Override public void run() { if (my == gen && "preparing".equals(state)) fail("станция не ответила за 12 секунд"); }
            }, 12000);
        } catch (Throwable e) {
            fail("адрес станции не открылся: " + e.getMessage());
        }
    }

    private void fail(String why) {
        gen++;                                       // поздние обратные вызовы этого проигрывателя — уже не в счёт
        release();
        state = "error";
        error = why;
        emit();
    }

    /** Убрать проигрыватель, не задерживая экран: звук глушим сразу, а reset/release — в фоне. MediaPlayer с сетевым
     *  потоком на reset() может висеть, пока не отпустит сеть, — и всё это время доигрывать старую станцию, а новая
     *  ждёт в очереди: ассистент называет новую станцию, а играет прежняя. */
    private void drop() {
        final MediaPlayer old = mp;
        mp = null;
        if (old == null) return;
        try { old.setVolume(0f, 0f); } catch (Throwable ignored) { }
        try { if (old.isPlaying()) old.pause(); } catch (Throwable ignored) { }
        new Thread(new Runnable() { @Override public void run() {
            try { old.reset(); } catch (Throwable ignored) { }
            try { old.release(); } catch (Throwable ignored) { }
        } }, "radio-release").start();
    }

    @SuppressWarnings("deprecation")
    private void release() {
        boolean had = mp != null;
        drop();
        if (had) am().abandonAudioFocus(this);
    }

    void pause() { pause("user"); }

    // пауза во время подключения — бросаем подключение: resume() подключится заново

    private void pause(final String who) {
        ui.post(new Runnable() { @Override public void run() {
            held = false;
            by = who;
            if (mp != null && "playing".equals(state)) {
                try { mp.pause(); } catch (Throwable ignored) { }
                state = "paused";
                emit();
            } else if ("preparing".equals(state)) {
                gen++;
                release();
                state = "paused";
                emit();
            }
        } });
    }

    void resume() {
        ui.post(new Runnable() { @Override public void run() {
            by = "";
            if (mp != null && "paused".equals(state)) {
                try {
                    am().requestAudioFocus(Radio.this, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN);
                    mp.start(); state = "playing"; applyVolume(); emit(); return;
                } catch (Throwable ignored) { }
            }
            if (!url.isEmpty()) start(url, name);    // проигрывателя нет (ошибка, пауза при подключении) или он не продолжил — подключаемся заново
        } });
    }

    void stop() {
        ui.post(new Runnable() { @Override public void run() {
            gen++;
            release();
            state = "stopped";
            error = "";
            emit();
        } });
    }

    /** Приглушить на время разговора с ассистентом (on) и вернуть громкость (off). */
    void duck(final boolean on) {
        ui.post(new Runnable() { @Override public void run() { duck = on ? 0.15f : 1f; applyVolume(); } });
    }

    void volume(final float v) {
        ui.post(new Runnable() { @Override public void run() { vol = Math.max(0.05f, Math.min(1f, v)); applyVolume(); } });
    }

    String state() {
        try {
            return new JSONObject().put("state", state).put("name", name).put("error", error).put("volume", vol).toString();
        } catch (Exception e) { return "{}"; }
    }

    @Override public void onAudioFocusChange(int f) {
        if (f == AudioManager.AUDIOFOCUS_LOSS) {            // другой звук забрал динамик (распознавание речи, другой плеер) — пауза;
            pause("focus");                                 // если это был наш разговор, интерфейс сам продолжит радио после ответа
        } else if (f == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) {   // звонок — замолкаем, после него продолжим
            if (mp != null && "playing".equals(state)) {
                try { mp.pause(); } catch (Throwable ignored) { }
                state = "paused";
                held = true;
                by = "focus";
                emit();
            }
        } else if (f == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK) {   // навигатор, уведомление — тише
            focusDuck = 0.15f;
            applyVolume();
        } else if (f == AudioManager.AUDIOFOCUS_GAIN) {
            focusDuck = 1f;
            applyVolume();
            if (held && mp != null && "paused".equals(state)) {
                try { mp.start(); state = "playing"; by = ""; emit(); } catch (Throwable ignored) { }
            }
            held = false;
        }
    }
}
