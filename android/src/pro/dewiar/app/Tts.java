package pro.dewiar.app;

import android.content.Context;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

/** Голос: синтез речи телефона (Google, Яндекс, RHVoice…) или голос вашего сервера (OpenAI-совместимый /v1/audio/speech).
 *  События в интерфейс: tts_ready {ok} — движок готов (или нет русского), tts_start / tts_done {id} на каждую фразу,
 *  tts_error {id, error} — звук с сервера голоса не получен. tts_done приходит всегда — и при ошибке, и при остановке:
 *  по нему app.js ведёт очередь фраз и понимает, что ассистент договорил. */
public final class Tts {
    private final Context ctx;
    private final Net.Sink sink;
    private TextToSpeech tts;
    private volatile boolean ready;
    private MediaPlayer player;
    private final Object playLock = new Object();    // ожидание конца фразы в play(); stop() будит его, иначе очередь стоит до таймаута
    private java.util.concurrent.ExecutorService queue = java.util.concurrent.Executors.newSingleThreadExecutor();   // фразы сервера — строго по одной
    private volatile int gen;                        // поколение: stop() его меняет, и фразы прежнего поколения не звучат

    public Tts(Context c, Net.Sink sink) {
        this.ctx = c;
        this.sink = sink;
        tts = new TextToSpeech(c, new TextToSpeech.OnInitListener() {
            @Override public void onInit(int status) {
                if (status == TextToSpeech.SUCCESS) {
                    int r = tts.setLanguage(new Locale("ru", "RU"));
                    ready = r != TextToSpeech.LANG_MISSING_DATA && r != TextToSpeech.LANG_NOT_SUPPORTED;
                    tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                        @Override public void onStart(String id) { ev("tts_start", id); }
                        @Override public void onDone(String id) { ev("tts_done", id); release(id); }
                        @Override public void onError(String id) { ev("tts_done", id); release(id); }
                        @Override public void onError(String id, int code) {      // в пульс: у кого голос устройства не говорит
                            try { sink.event("tts_fail", new JSONObject().put("id", id).put("code", code)); } catch (Exception ignored) { }
                            ev("tts_done", id); release(id);
                        }
                        @Override public void onStop(String id, boolean interrupted) { ev("tts_done", id); release(id); }
                    });
                }
                try { sink.event("tts_ready", new JSONObject().put("ok", ready)); } catch (Exception ignored) { }
            }
        });
    }

    private void ev(String type, String id) {
        try { sink.event(type, new JSONObject().put("id", id)); } catch (Exception ignored) { }
    }

    public boolean ready() { return ready; }

    /** Русские голоса движка: [{name, offline}]. */
    public String voices() {
        JSONArray a = new JSONArray();
        try {
            if (tts != null && tts.getVoices() != null) {
                for (Voice v : tts.getVoices()) {
                    if (v.getLocale() != null && "ru".equals(v.getLocale().getLanguage())) {
                        JSONArray f = new JSONArray();                // у части движков в признаках есть пол голоса
                        if (v.getFeatures() != null) for (String x : v.getFeatures()) f.put(x);
                        a.put(new JSONObject().put("name", v.getName()).put("offline", !v.isNetworkConnectionRequired()).put("features", f));
                    }
                }
            }
        } catch (Throwable ignored) { }
        return a.toString();
    }

    /** Очередь фраз: add=true — дописать к уже звучащему (ответ модели идёт предложениями). */
    public void speak(String id, String text, float rate, float pitch, String voice, boolean add) {
        if (!ready) { ev("tts_done", id); return; }
        if (BtMic.isOn()) BtMic.offNow(ctx);          // слушали микрофоном наушников — ответ звучит в обычном качестве
        try {
            tts.setSpeechRate(rate <= 0 ? 1f : rate);
            tts.setPitch(pitch <= 0 ? 1f : pitch);
            if (voice != null && !voice.isEmpty() && tts.getVoices() != null) {
                for (Voice v : tts.getVoices()) if (v.getName().equals(voice)) { tts.setVoice(v); break; }
            }
            Bundle p = new Bundle();
            p.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, id);
            tts.speak(text, add ? TextToSpeech.QUEUE_ADD : TextToSpeech.QUEUE_FLUSH, p, id);
        } catch (Throwable e) { ev("tts_done", id); }
    }

    /** Фраза на другом языке (lang — «en-US»): язык движка — на эту фразу (он запоминается в самой просьбе), затем снова
     *  русский. Голоса этого языка нет — обычная фраза. */
    public void speak(String id, String text, float rate, float pitch, String voice, boolean add, String lang) {
        if (lang == null || lang.isEmpty() || lang.startsWith("ru") || !ready) { speak(id, text, rate, pitch, voice, add); return; }
        Locale l = Locale.forLanguageTag(lang);
        try {
            if (tts.isLanguageAvailable(l) < TextToSpeech.LANG_AVAILABLE) { speak(id, text, rate, pitch, voice, add); return; }
            if (BtMic.isOn()) BtMic.offNow(ctx);
            tts.setSpeechRate(rate <= 0 ? 1f : rate);
            tts.setPitch(pitch <= 0 ? 1f : pitch);
            tts.setLanguage(l);
            Bundle p = new Bundle();
            p.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, id);
            tts.speak(text, add ? TextToSpeech.QUEUE_ADD : TextToSpeech.QUEUE_FLUSH, p, id);
        } catch (Throwable e) { ev("tts_done", id); }
        finally { try { tts.setLanguage(new Locale("ru", "RU")); } catch (Throwable ignored) { } }
    }

    public void stop() {
        gen++;                                            // фразы, что ещё в очереди, — не играть
        for (java.util.concurrent.CountDownLatch l : waits.values()) l.countDown();   // запасная фраза в очереди — не ждать
        waits.clear();
        synchronized (pending) { for (java.util.concurrent.Future<File> x : pending) x.cancel(true); }   // и не скачивать
        try { if (tts != null) tts.stop(); } catch (Throwable ignored) { }
        synchronized (this) {
            if (player != null) { try { player.stop(); player.release(); } catch (Throwable ignored) { } player = null; }
        }
        // остановленный плеер onCompletion не шлёт — будим play() сами (не внутри synchronized (this): play() берёт
        // замки в обратном порядке)
        synchronized (playLock) { playLock.notifyAll(); }
    }

    private synchronized boolean playing(MediaPlayer mp) { return player == mp; }

    /** Голос сервера: звук фразы скачивается сразу (до двух фраз одновременно — пока звучит одна, следующая уже
     *  готовится), а играют фразы строго по очереди. Раньше следующая начинала скачиваться, только когда отзвучала
     *  предыдущая, — между фразами были паузы на всё время синтеза (отзыв 11.10: «как у Алисы»). Короткие фразы
     *  («Хорошо.», «Пожалуйста!», «Наведите камеру на код.») запоминаются (VoiceCache) — второй раз звучат сразу. */
    private final java.util.concurrent.ExecutorService fetch = java.util.concurrent.Executors.newFixedThreadPool(2);
    private final java.util.List<java.util.concurrent.Future<File>> pending = new java.util.ArrayList<>();

    /** Фразы голоса телефона, которых ждёт очередь сервера (запасной голос внутри очереди — см. speakRemote fb). */
    private final java.util.Map<String, java.util.concurrent.CountDownLatch> waits = new java.util.concurrent.ConcurrentHashMap<>();
    private void release(String id) { java.util.concurrent.CountDownLatch l = waits.remove(id); if (l != null) l.countDown(); }

    public void speakRemote(final String id, final String url, final String key, final String body) { speakRemote(id, url, key, body, null); }

    /** fb — запасной голос телефона для этой фразы ({text, rate, pitch, voice}): сервер голоса не ответил — фраза звучит
     *  голосом телефона ЗДЕСЬ, в очереди, и следующая ждёт её конца. Раньше запасную фразу говорил app.js сам, а очередь
     *  тем временем играла следующую фразу сервера — два голоса разом (отчёт №93, 19.10: «наложение 2 голосовых ответов»). */
    public void speakRemote(final String id, final String url, final String key, final String body, final String fb) {
        final int my = gen;
        if (url == null || url.isEmpty()) {              // сервер голоса только что подвёл — фраза сразу голосом телефона, но в
            queue.execute(new Runnable() {                // той же очереди: после уже начатых фраз сервера, а не поверх них
                @Override public void run() { if (fb != null && ready && my == gen) sayAndWait("f" + id, fb); ev("tts_done", id); }
            });
            return;
        }
        final java.util.concurrent.Future<File> got = fetch.submit(new java.util.concurrent.Callable<File>() {
            @Override public File call() throws Exception { return my != gen ? null : VoiceCache.get(ctx.getCacheDir(), id, url, key, body); }
        });
        synchronized (pending) { pending.add(got); }
        queue.execute(new Runnable() {
            @Override public void run() {
                File f = null;
                try {
                    f = got.get();
                    boolean temp = f != null && !VoiceCache.cached(f);
                    if (my != gen || f == null) { if (temp) //noinspection ResultOfMethodCallIgnored
                        f.delete(); ev("tts_done", id); return; }
                    play(id, f, temp);
                } catch (java.util.concurrent.CancellationException e) {
                    ev("tts_done", id);
                } catch (Throwable e) {
                    Throwable c = e instanceof java.util.concurrent.ExecutionException && e.getCause() != null ? e.getCause() : e;
                    boolean own = fb != null && ready && my == gen;
                    try { sink.event("tts_error", new JSONObject().put("id", id).put("error", String.valueOf(c.getMessage())).put("fallback", own)); } catch (Exception ignored) { }
                    if (own) sayAndWait("f" + id, fb);
                    ev("tts_done", id);
                } finally {
                    synchronized (pending) { pending.remove(got); }
                }
            }
        });
    }

    /** Сказать фразу голосом телефона (fb — {text, rate, pitch, voice}) и дождаться её конца — в потоке очереди. */
    private void sayAndWait(String fid, String fb) {
        try {
            JSONObject o = new JSONObject(fb);
            java.util.concurrent.CountDownLatch l = new java.util.concurrent.CountDownLatch(1);
            waits.put(fid, l);
            speak(fid, o.optString("text"), (float) o.optDouble("rate", 1), (float) o.optDouble("pitch", 1), o.optString("voice"), true);
            l.await(120, java.util.concurrent.TimeUnit.SECONDS);
        } catch (Throwable ignored) { }
    }

    /** Проиграть файл и дождаться конца (не дольше 2 минут) в потоке очереди; temp — удалить после. Звук помечен как голос
     *  ассистента (USAGE_ASSISTANT, Android 8+; на старых — как медиа). */
    private void play(final String id, final File f, boolean temp) throws Exception {
        final Object lock = playLock;
        final boolean[] done = {false};
        MediaPlayer mp = new MediaPlayer();
        mp.setAudioAttributes(new AudioAttributes.Builder().setUsage(android.os.Build.VERSION.SDK_INT >= 26 ? 16 /* USAGE_ASSISTANT */ : AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
        mp.setDataSource(f.getAbsolutePath());
        mp.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {
            @Override public void onCompletion(MediaPlayer m) { synchronized (lock) { done[0] = true; lock.notifyAll(); } }
        });
        mp.setOnErrorListener(new MediaPlayer.OnErrorListener() {
            @Override public boolean onError(MediaPlayer m, int a, int b) { synchronized (lock) { done[0] = true; lock.notifyAll(); } return true; }
        });
        mp.prepare();
        if (BtMic.isOn()) BtMic.offNow(ctx);          // голосовой канал гарнитуры — выключить: ответ в обычном качестве
        synchronized (this) { player = mp; }
        ev("tts_start", id);
        mp.start();
        // ждём конца фразы, остановки (stop() убирает player и будит lock) или 2 минут — на случай, если плеер замолчал без событий
        synchronized (lock) { long end = System.currentTimeMillis() + 120000; while (!done[0] && playing(mp) && System.currentTimeMillis() < end) lock.wait(500); }
        synchronized (this) { if (player == mp) { player = null; } }
        try { mp.release(); } catch (Throwable ignored) { }
        //noinspection ResultOfMethodCallIgnored
        if (temp) f.delete();                         // запомненная фраза остаётся для следующего раза
        ev("tts_done", id);
    }

    public void shutdown() {
        stop();
        try { if (tts != null) tts.shutdown(); } catch (Throwable ignored) { }
    }
}
