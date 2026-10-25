package pro.dewiar.app;

import android.content.Context;
import android.content.Intent;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import org.json.JSONObject;

/** Слух: системное распознавание телефона (по-русски, без интернета, если есть пакет языка) или запись и распознавание
 *  на вашем сервере (OpenAI-совместимый /v1/audio/transcriptions — GigaAM, Whisper).
 *  Оба пути шлют в интерфейс одни и те же события: stt_start, stt_level {v 0..1}, stt_partial (только системное),
 *  stt_end, stt_result {text}, stt_error {code, msg}; коды ошибок — как у SpeechRecognizer (5 — отменено, 6 — не было
 *  речи), свои: -1 — системное не запустилось, -2 — сбой записи или сервера. Разбирает их app.js. */
public final class Speech {
    private final Context ctx;
    private final Net.Sink sink;
    private final Handler main = new Handler(Looper.getMainLooper());
    private SpeechRecognizer rec;
    private boolean renew = false;                   // распознаватель сломался (5, 8, 11) — в следующий раз создать новый
    private boolean active = false;                  // идёт сеанс распознавания (startListening без итога)
    private volatile boolean recording;              // идёт запись для сервера; false — отменено (cancel): без распознавания
    private volatile boolean finish;                 // stop(): закончить запись и распознать то, что успели записать
    private volatile int gen;                        // номер сеанса слушания: события несут его в поле g, app.js отбрасывает чужие

    public Speech(Context c, Net.Sink sink) { this.ctx = c; this.sink = sink; }

    public static boolean systemAvailable(Context c) { return SpeechRecognizer.isRecognitionAvailable(c); }

    private void ev(String type, JSONObject d) { sink.event(type, d); }

    /** Событие сеанса g: поздние события прежнего сеанса (например, «отменено» после cancel) не должны сбивать новый. */
    private void ev(int g, String type, JSONObject d) {
        try { d.put("g", g); } catch (Exception ignored) { }
        sink.event(type, d);
    }

    private static JSONObject o() { return new JSONObject(); }

    /** Системный распознаватель — только из главного потока (Android требует), поэтому через main.post.
     *  Каждый раз создаётся заново, прежний уничтожается. */
    /** Добавка к паузе конца фразы, мс (0…900): app.js учит её, когда человека обрывают на полуслове (pauseExtra). */
    volatile int extraMs = 0;
    /** «Удерживайте и говорите»: распознаватель просят ждать паузу подольше (меньше перезапусков посреди речи). */
    volatile boolean longPause = false;

    // ---------- «Триньк» системного распознавателя (отзыв 13.10: «пока держу кнопку — тринькает на каждой паузе») ----------
    // Google-распознаватель сам играет звук в начале и в конце каждого сеанса, а при удержании сеансы идут один за другим.
    // Пока держат кнопку, эти звуки глушим: потоки музыки, уведомлений и системный — без звука, а после — как было.
    // Что заглушили — в pref beep_muted: если приложение закроется посреди удержания, при следующем запуске звук вернётся
    // (restoreBeeps); дольше 2 минут без звука не бывает.
    private static final int[] BEEP_STREAMS = { AudioManager.STREAM_MUSIC, AudioManager.STREAM_NOTIFICATION, AudioManager.STREAM_SYSTEM };
    private final java.util.Set<Integer> muted = new java.util.HashSet<>();
    private final Runnable unmuteR = new Runnable() { @Override public void run() { unmuteNow(); } };

    public void quiet(final boolean on) {
        main.post(new Runnable() {
            @Override public void run() {
                main.removeCallbacks(unmuteR);
                if (!on) { main.postDelayed(unmuteR, 900); return; }   // последний «триньк» звучит после остановки
                AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
                for (int st : BEEP_STREAMS) {
                    try {
                        if (!muted.contains(st) && !am.isStreamMute(st)) { am.adjustStreamVolume(st, AudioManager.ADJUST_MUTE, 0); muted.add(st); }
                    } catch (Throwable ignored) { }                   // «Не беспокоить» и т. п. — этот поток не трогаем
                }
                saveMuted();
                main.postDelayed(unmuteR, 120000);
            }
        });
    }

    private void unmuteNow() {
        AudioManager am = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
        for (int st : muted) { try { am.adjustStreamVolume(st, AudioManager.ADJUST_UNMUTE, 0); } catch (Throwable ignored) { } }
        muted.clear();
        saveMuted();
    }

    private void saveMuted() {
        StringBuilder b = new StringBuilder();
        for (int st : muted) b.append(b.length() > 0 ? "," : "").append(st);
        ctx.getSharedPreferences("dewiar", Context.MODE_PRIVATE).edit().putString("beep_muted", b.toString()).apply();
    }

    /** При запуске: звук, заглушенный прошлым удержанием (приложение закрылось на полуслове), — вернуть. */
    public static void restoreBeeps(Context c) {
        android.content.SharedPreferences p = c.getSharedPreferences("dewiar", Context.MODE_PRIVATE);
        String v = p.getString("beep_muted", "");
        if (v.isEmpty()) return;
        AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
        for (String x : v.split(",")) { try { am.adjustStreamVolume(Integer.parseInt(x.trim()), AudioManager.ADJUST_UNMUTE, 0); } catch (Throwable ignored) { } }
        p.edit().putString("beep_muted", "").apply();
    }

    public void release() {
        main.removeCallbacks(unmuteR); unmuteNow(); BtMic.offNow(ctx);
        main.post(new Runnable() {
            @Override public void run() {
                if (rec != null) { try { rec.destroy(); } catch (Throwable ignored) { } rec = null; }
            }
        });
    }

    /** Слушать микрофоном Bluetooth-наушников, если они подключены (BtMic; настройка «Микрофон наушников», по умолчанию да). */
    volatile boolean btMic = true;

    /** Включить микрофон наушников перед слушанием (не из главного потока); сообщить интерфейсу, вышло ли. */
    private boolean btUp(int g) {
        if (!btMic || !BtMic.available(ctx)) return false;
        boolean was = BtMic.isOn(), ok = BtMic.start(ctx, 2500);
        if (!was) { try { ev(g, "stt_bt", o().put("on", ok)); } catch (Exception ignored) { } }
        return ok;
    }

    public void listenSystem(final int g) {
        gen = g;
        final Runnable go = new Runnable() {
            @Override public void run() {
                try {
                    if (g != gen) return;                      // пока ждали — начали новый сеанс
                    // Один распознаватель на всё время работы, а не новый на каждую фразу. Раньше: destroy() прежнего и
                    // сразу createSpeechRecognizer() — служба распознавания (Google) ещё отключалась от старого, и новый
                    // получал ERROR_SERVER_DISCONNECTED (11): «распознавание ещё занято (11) — пробую снова» почти на
                    // каждой фразе, у 50 телефонов из 178 (пакет здоровья 20.10), лишние полсекунды до «слушаю».
                    // Пересоздаём, только если он сам сломался (ошибки 5, 8, 11 — отпускаем сразу; не запустился — флаг renew).
                    if (rec != null && renew) { try { rec.destroy(); } catch (Throwable ignored) { } rec = null; }
                    if (rec == null) { rec = SpeechRecognizer.createSpeechRecognizer(ctx); renew = false; }   // первый раз или после поломки
                    else if (active) { try { rec.cancel(); } catch (Throwable ignored) { } }   // прежний сеанс ещё идёт — прервать
                    final long t0 = android.os.SystemClock.elapsedRealtime();
                    final boolean[] ready = {false};
                    active = true;
                    rec.setRecognitionListener(new RecognitionListener() {
                        @Override public void onReadyForSpeech(Bundle b) { ready[0] = true; ev(g, "stt_start", o()); }
                        @Override public void onBeginningOfSpeech() { }
                        @Override public void onRmsChanged(float v) {
                            // v — дБ примерно от −2 до 10: переводим в 0..1 для анимации облика
                            try { ev(g, "stt_level", o().put("v", Math.max(0, Math.min(1, (v + 2) / 12.0)))); } catch (Exception ignored) { }
                        }
                        @Override public void onBufferReceived(byte[] b) { }
                        @Override public void onEndOfSpeech() { ev(g, "stt_end", o()); }
                        @Override public void onError(int code) {
                            // «прервано» от прерванного прежнего сеанса прилетает уже сюда, до готовности нового — не наше
                            if (code == SpeechRecognizer.ERROR_CLIENT && !ready[0] && android.os.SystemClock.elapsedRealtime() - t0 < 600) return;
                            active = false;
                            if ((code == SpeechRecognizer.ERROR_CLIENT || code == SpeechRecognizer.ERROR_RECOGNIZER_BUSY || code == 11) && rec != null) {
                                // сломался — отпустить сразу, а не перед следующей фразой: к ней служба успеет отключиться
                                final SpeechRecognizer old = rec;
                                rec = null;
                                main.post(new Runnable() { @Override public void run() { try { old.destroy(); } catch (Throwable ignored) { } } });
                            }
                            BtMic.stopSoon();
                            try { ev(g, "stt_error", o().put("code", code).put("msg", errText(code))); } catch (Exception ignored) { }
                        }
                        @Override public void onResults(Bundle b) {
                            active = false;
                            BtMic.stopSoon();
                            ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                            try { ev(g, "stt_result", o().put("text", r != null && !r.isEmpty() ? r.get(0) : "")); } catch (Exception ignored) { }
                        }
                        @Override public void onPartialResults(Bundle b) {
                            ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                            if (r != null && !r.isEmpty()) {
                                try { ev(g, "stt_partial", o().put("text", r.get(0))); } catch (Exception ignored) { }
                            }
                        }
                        @Override public void onEvent(int t, Bundle b) { }
                    });
                    Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                    i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                    i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ru-RU");
                    // и «только по-русски» — для распознавателей, что берут язык системы (отчёт №253: телефон без русской
                    // прошивки слышал английский и китайский)
                    i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "ru-RU");
                    i.putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, true);
                    i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
                    i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
                    // пожелание (не все распознаватели слушают): дать договорить — человек вспоминает имя или слово
                    i.putExtra("android.speech.extra.SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS", longPause ? 8000L : 2000L + extraMs);
                    i.putExtra("android.speech.extra.SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS", longPause ? 6000L : 1600L + extraMs);
                    i.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, ctx.getPackageName());
                    rec.startListening(i);
                } catch (Throwable e) {
                    active = false; renew = true;
                    BtMic.stopSoon();
                    try { ev(g, "stt_error", o().put("code", -1).put("msg", "распознавание телефона не запустилось: " + e.getMessage())); } catch (Exception ignored) { }
                }
            }
        };
        // наушники с микрофоном — сначала их голосовой канал (до 2,5 с, в своём потоке), потом распознаватель
        if (btMic && !BtMic.isOn() && BtMic.available(ctx)) {
            new Thread(new Runnable() { @Override public void run() { btUp(g); main.post(go); } }, "btmic").start();
        } else {
            if (BtMic.isOn()) btUp(g);                    // уже включён — только отменить выключение
            main.post(go);
        }
    }

    /** Закончить слушать: системное распознавание отдаст то, что успело услышать, запись для сервера — заканчивается
     *  и уходит на распознавание (человек нажал «хватит» — сказанное не теряется). */
    public void stop() {
        finish = true;
        main.post(new Runnable() {
            @Override public void run() {
                if (rec != null) {
                    try { rec.stopListening(); } catch (Throwable ignored) { }
                }
            }
        });
    }

    public void cancel() {
        recording = false;
        BtMic.stopSoon();
        main.post(new Runnable() {
            @Override public void run() {
                if (rec != null && active) {                 // распознаватель остаётся — следующая фраза без переподключения
                    try { rec.cancel(); } catch (Throwable ignored) { }
                }
                active = false;
            }
        });
    }

    private static String errText(int c) {
        switch (c) {
            case SpeechRecognizer.ERROR_NO_MATCH: return "не расслышал";
            case SpeechRecognizer.ERROR_SPEECH_TIMEOUT: return "не услышал речи";
            case SpeechRecognizer.ERROR_NETWORK: case SpeechRecognizer.ERROR_NETWORK_TIMEOUT: return "нет сети для распознавания";
            case SpeechRecognizer.ERROR_AUDIO: return "микрофон недоступен";
            case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS: return "нет разрешения на микрофон";
            case SpeechRecognizer.ERROR_RECOGNIZER_BUSY: return "распознавание занято";
            case SpeechRecognizer.ERROR_CLIENT: return "распознавание прервано";
            case 11: return "служба распознавания переподключается";
            default: return "ошибка распознавания " + c;
        }
    }

    /** Запись до паузы после речи (или 15 с) → WAV 16 кГц моно → сервер распознавания (Net.postMultipart, в своём потоке).
     *  Повторный вызов во время записи ничего не делает. Тишину от речи отличает простой порог громкости: первые 0,3 с —
     *  замер шума, речь — громче шума втрое (+200) хотя бы 0,15 с подряд; пока речи не было, порог подстраивается под шум. */
    /** «Удерживайте и говорите» для сервера (отзыв 13.10, планшет Huawei: «держу, диктую — и ничего»): запись идёт, пока
     *  держат кнопку (до 2 минут), без проверки «была ли речь» — отпустили, и вся запись уходит на распознавание, как
     *  голосовое в Telegram; сервер сам скажет, если там тишина. */
    volatile boolean holdRec = false;

    public void listenServer(final int g, final String url, final String key, final String model) {
        if (recording) return;
        gen = g;
        final boolean hold = holdRec;
        recording = true;
        finish = false;
        new Thread(new Runnable() {
            @Override public void run() {
                AudioRecord ar = null;
                try {
                    final int rate = 16000;
                    int min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
                    // микрофон наушников — через голосовой канал гарнитуры (источник «связь»), иначе — телефона
                    int source = btUp(g) ? MediaRecorder.AudioSource.VOICE_COMMUNICATION : MediaRecorder.AudioSource.VOICE_RECOGNITION;
                    ar = new AudioRecord(source, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(min, rate));
                    ar.startRecording();
                    ev(g, "stt_start", o());
                    ByteArrayOutputStream pcm = new ByteArrayOutputStream();
                    short[] buf = new short[rate / 20];               // 50 мс
                    double noise = 300, peak = 0;
                    int speech = 0, quiet = 0, frames = 0;
                    boolean heard = false;
                    final int endQuiet = 30 + extraMs / 50;          // 1,5 с тишины + добавка под манеру речи
                    while (recording && !finish) {
                        int n = ar.read(buf, 0, buf.length);
                        if (n <= 0) break;
                        double s = 0;
                        for (int i = 0; i < n; i++) s += (double) buf[i] * buf[i];
                        double rms = Math.sqrt(s / n);
                        byte[] b = new byte[n * 2];
                        for (int i = 0; i < n; i++) { b[2 * i] = (byte) (buf[i] & 0xff); b[2 * i + 1] = (byte) ((buf[i] >> 8) & 0xff); }
                        pcm.write(b);
                        frames++;
                        peak = Math.max(peak, rms);
                        ev(g, "stt_level", o().put("v", Math.min(1.0, rms / 4000.0)));   // каждые 50 мс — для анимации облика
                        // источник «для распознавания» на некоторых планшетах (Huawei) отдаёт почти тишину — тогда обычный микрофон
                        if (frames == 20 && peak < 25 && source == MediaRecorder.AudioSource.VOICE_RECOGNITION) {
                            try { ar.stop(); ar.release(); } catch (Throwable ignored) { }
                            source = MediaRecorder.AudioSource.MIC;
                            ar = new AudioRecord(source, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(min, rate));
                            ar.startRecording();
                            pcm.reset(); frames = 0; peak = 0; noise = 300;
                            continue;
                        }
                        if (frames < 6) { noise = Math.max(150, (noise + rms) / 2); continue; }
                        // речь — заметно громче шума (было втрое + 200: тихий микрофон планшета «не слышал» речи вовсе)
                        if (rms > noise * 2.2 + 120) { speech++; quiet = 0; if (speech >= 3) heard = true; }
                        else { quiet++; if (!heard) noise = noise * 0.95 + rms * 0.05; }
                        if (hold) { if (frames > 2400) break; continue; }   // держат кнопку — пишем до «отпустили» (2 мин максимум)
                        if (heard && quiet >= endQuiet) break;          // 1,5 с тишины после речи (было 0,9 — перебивало на полуслове)
                        if (!heard && frames > 160) break;              // 8 с — так и не заговорили
                        if (frames > 300) break;                        // 15 с максимум
                    }
                    ar.stop();
                    ev(g, "stt_end", o());
                    if (!recording) { ev(g, "stt_error", o().put("code", 5).put("msg", "отменено")); return; }
                    recording = false;
                    if (!heard && hold) heard = frames >= 8 && peak > 40;        // держали кнопку — отправляем всё, сервер решит
                    if (!heard && peak > noise * 1.8 + 60) heard = true;       // было что-то громче шума — пусть решит сервер
                    if (!heard) {
                        ev(g, "stt_error", o().put("code", 6).put("msg", "не услышал речи (громкость " + Math.round(peak) + ", шум " + Math.round(noise)
                                + (source == MediaRecorder.AudioSource.MIC ? ", микрофон" : "") + ")"));
                        return;
                    }
                    byte[] wav = wav(pcm.toByteArray(), rate);
                    // whisper-1 — имя по умолчанию в OpenAI-совместимом API; свой сервер обычно принимает любое
                    JSONObject f = new JSONObject().put("model", model == null || model.isEmpty() ? "whisper-1" : model).put("language", "ru");
                    String r = Net.postMultipart(url, key, wav, "speech.wav", "audio/wav", f);
                    String text;
                    try { text = new JSONObject(r).optString("text", r); } catch (Exception e) { text = r; }   // {"text": …} или просто текст
                    ev(g, "stt_result", o().put("text", text.trim()).put("cut", !hold && frames > 300));   // cut — оборвали по лимиту, человек ещё говорит
                } catch (Throwable e) {
                    try { ev(g, "stt_error", o().put("code", -2).put("msg", String.valueOf(e.getMessage()))); } catch (Exception ignored) { }
                } finally {
                    recording = false;
                    BtMic.stopSoon();
                    if (ar != null) { try { ar.release(); } catch (Throwable ignored) { } }
                }
            }
        }, "record").start();
    }

    /** 44-байтовый заголовок WAV (PCM, моно, 16 бит) + сами отсчёты. */
    static byte[] wav(byte[] pcm, int rate) {
        int len = pcm.length;
        byte[] h = new byte[44];
        String[] tags = {"RIFF", "WAVE", "fmt ", "data"};
        System.arraycopy(tags[0].getBytes(), 0, h, 0, 4);
        le(h, 4, 36 + len);
        System.arraycopy(tags[1].getBytes(), 0, h, 8, 4);
        System.arraycopy(tags[2].getBytes(), 0, h, 12, 4);
        le(h, 16, 16); h[20] = 1; h[22] = 1;
        le(h, 24, rate); le(h, 28, rate * 2); h[32] = 2; h[34] = 16;
        System.arraycopy(tags[3].getBytes(), 0, h, 36, 4);
        le(h, 40, len);
        byte[] out = new byte[44 + len];
        System.arraycopy(h, 0, out, 0, 44);
        System.arraycopy(pcm, 0, out, 44, len);
        return out;
    }

    private static void le(byte[] b, int at, int v) {
        b[at] = (byte) v; b[at + 1] = (byte) (v >> 8); b[at + 2] = (byte) (v >> 16); b[at + 3] = (byte) (v >> 24);
    }
}
