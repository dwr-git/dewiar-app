package pro.dewiar.app;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Звук фраз голоса сервера (Голос Dewiar, ElevenLabs, свой сервер): скачать во временный файл или взять запомненный.
 *  Короткие фразы (тело запроса до CACHE_BODY знаков: «Хорошо.», «Пожалуйста!») запоминаются в cacheDir/tts по отпечатку
 *  адреса и тела запроса (текст, голос, скорость — всё в теле), не больше CACHE_MAX файлов: давно не звучавшие удаляются.
 *  Без Android — проверяется обычной Java (tests/voice_cache_test.py). */
final class VoiceCache {
    static final int CACHE_BODY = 600, CACHE_MAX = 200;
    static final long SLOT_MS = 12L * 3600 * 1000;
    static final String DIR = "tts";

    private VoiceCache() { }

    /** Запомненный файл (его после проигрыша не удаляют) или временный. */
    static boolean cached(File f) { return f != null && f.getParentFile() != null && DIR.equals(f.getParentFile().getName()); }

    /** Звук фразы -> файл: из запомненных (короткая фраза с тем же голосом, скоростью и текстом) или с сервера. */
    static File get(File cacheDir, String id, String url, String key, String body) throws Exception {
        File dir = new File(cacheDir, DIR);
        File hit = null;
        if (body.length() <= CACHE_BODY) {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-1");
            // владелец 11.11: «заменил голос Патрика — а „Привет! Это Патрик“ на телефоне прежним голосом»: в теле запроса —
            // имя персонажа, а не сам голос сервера, и запомненная фраза звучала старым голосом вечно. Теперь запомненное
            // живёт не дольше SLOT_MS: новый голос на сервере — слышен и в коротких фразах не позже чем через полдня
            long slot = System.currentTimeMillis() / SLOT_MS;
            byte[] h = md.digest((url + "\n" + body + "\n" + slot).getBytes("UTF-8"));
            StringBuilder sb = new StringBuilder();
            for (byte x : h) sb.append(String.format("%02x", x));
            hit = new File(dir, sb + ".audio");
            if (hit.length() > 0) { hit.setLastModified(System.currentTimeMillis()); return hit; }
        }
        HttpURLConnection c = (HttpURLConnection) NetProxy.open(new URL(url));
        c.setConnectTimeout(10000);
        c.setReadTimeout(60000);
        c.setRequestMethod("POST");
        c.setDoOutput(true);
        c.setRequestProperty("Content-Type", "application/json");
        if (key != null && key.startsWith("xi-api-key:")) c.setRequestProperty("xi-api-key", key.substring(11));   // ElevenLabs
        else if (key != null && !key.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + key);
        OutputStream os = c.getOutputStream();
        os.write(body.getBytes("UTF-8"));
        os.close();
        if (c.getResponseCode() >= 400) throw new Exception("сервер голоса ответил " + c.getResponseCode());
        //noinspection ResultOfMethodCallIgnored
        cacheDir.mkdirs();
        File f = new File(cacheDir, "say-" + id + ".audio");
        InputStream in = c.getInputStream();
        FileOutputStream fo = new FileOutputStream(f);
        byte[] buf = new byte[16384];
        int n;
        long total = 0;
        while ((n = in.read(buf)) > 0) { fo.write(buf, 0, n); total += n; }
        fo.close();
        in.close();
        if (hit != null && total > 0) {                       // запомнить короткую фразу; старые — прочь, когда их много
            dir.mkdirs();
            if (f.renameTo(hit)) {
                File[] all = dir.listFiles();
                if (all != null && all.length > CACHE_MAX) {
                    java.util.Arrays.sort(all, new java.util.Comparator<File>() {
                        @Override public int compare(File a, File b) { return Long.compare(a.lastModified(), b.lastModified()); }
                    });
                    for (int i = 0; i < all.length - CACHE_MAX; i++) //noinspection ResultOfMethodCallIgnored
                        all[i].delete();
                }
                return hit;
            }
        }
        return f;
    }

}
