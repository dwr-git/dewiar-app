package pro.dewiar.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLConnection;
import java.security.MessageDigest;
import org.json.JSONObject;

/** Обновление внутри приложения (18.10: «скачивая новые версии, в Загрузках много этих версий, и не каждый разберётся,
 *  куда зайти, чтобы удалить»). Новая версия качается не браузером в «Загрузки», а сюда — в кэш приложения
 *  (cache/update/Dewiar.apk), проверяется по sha256 из latest.json и отдаётся установщику Android через UpdateProvider.
 *  После установки (или при следующем запуске) файл удаляется сам — мусора не остаётся. Android 8+ один раз спросит
 *  разрешение «Установка неизвестных приложений» — для Dewiar, а не для браузера.
 *  События в интерфейс: upd_progress {pct}, upd_ready {size}, upd_error {error}. */
public final class Update {
    static final String AUTH = "pro.dewiar.app.update";
    private static volatile Thread job;

    private Update() { }

    static File apk(Context c) {
        File d = new File(c.getCacheDir(), "update");
        //noinspection ResultOfMethodCallIgnored
        d.mkdirs();
        return new File(d, "Dewiar.apk");
    }

    /** №1057 (25.11, Huawei): «Не скачалось: файл пришёл повреждённым» раз за разом — у других та же версия ставилась.
     *  Значит, файл портит дорога: оборванная связь без ошибки или кэш по пути (у провайдера, в прокси) отдаёт старый
     *  кусок. Теперь: оборвалось раньше заявленного размера — это обрыв, а не порча; до трёх попыток, со второй — мимо
     *  кэшей (свой адрес и Cache-Control: no-cache). */
    static void download(final MainActivity a, final String url, final String sha256) {
        if (job != null && job.isAlive()) return;
        job = new Thread(new Runnable() { @Override public void run() {
            File part = new File(apk(a).getParentFile(), "Dewiar.apk.part");
            String err = "";
            for (int t = 1; t <= 3; t++) {
                try {
                    long got = fetch(a, t == 1 ? url : url + (url.contains("?") ? "&" : "?") + "nc=" + System.currentTimeMillis(), sha256, part, t > 1);
                    File f = apk(a);
                    //noinspection ResultOfMethodCallIgnored
                    f.delete();
                    if (!part.renameTo(f)) throw new Exception("не удалось сохранить файл");
                    a.event("upd_ready", new JSONObject().put("size", got).put("tries", t));
                    return;
                } catch (Exception e) {
                    //noinspection ResultOfMethodCallIgnored
                    part.delete();
                    err = String.valueOf(e.getMessage());
                    try { a.event("upd_retry", new JSONObject().put("try", t).put("error", err)); } catch (Exception ignored) { }
                }
            }
            try { a.event("upd_error", new JSONObject().put("error", err)); } catch (Exception ignored) { }
        } });
        job.start();
    }

    private static long fetch(MainActivity a, String url, String sha256, File part, boolean fresh) throws Exception {
        URLConnection uc = NetProxy.open(new URL(url));
        uc.setConnectTimeout(15000); uc.setReadTimeout(60000);
        if (fresh) { uc.setUseCaches(false); uc.setRequestProperty("Cache-Control", "no-cache"); uc.setRequestProperty("Pragma", "no-cache"); }
        if (uc instanceof HttpURLConnection && ((HttpURLConnection) uc).getResponseCode() >= 400)
            throw new Exception("сервер ответил " + ((HttpURLConnection) uc).getResponseCode());
        long total = uc.getContentLength(), got = 0;
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        InputStream in = uc.getInputStream();
        FileOutputStream out = new FileOutputStream(part);
        try {
            byte[] buf = new byte[65536];
            int n, last = -1;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n); md.update(buf, 0, n); got += n;
                int pct = total > 0 ? (int) (got * 100 / total) : -1;
                if (pct != last && (pct % 5 == 0 || pct < 0)) { last = pct; a.event("upd_progress", new JSONObject().put("pct", pct)); }
            }
        } finally { out.close(); in.close(); }
        if (total > 0 && got < total)
            throw new Exception("связь оборвалась на " + (got * 100 / total) + "% — попробуйте ещё раз");
        StringBuilder hex = new StringBuilder();
        for (byte b : md.digest()) hex.append(String.format("%02x", b));
        if (sha256 != null && !sha256.isEmpty() && !sha256.equalsIgnoreCase(hex.toString()))
            throw new Exception("файл пришёл повреждённым (" + (got / 1024) + " КБ)");
        return got;
    }

    /** Можно ли Dewiar открывать установщик (Android 8+: «Установка неизвестных приложений»). Сборка — против API 23,
     *  поэтому метод нового API — через отражение. */
    static boolean canInstall(Context c) {
        if (Build.VERSION.SDK_INT < 26) return true;
        try { return (Boolean) PackageManager.class.getMethod("canRequestPackageInstalls").invoke(c.getPackageManager()); }
        catch (Exception e) { return true; }
    }

    /** -> "ok" (установщик открыт), "perm" (открыли настройку разрешения — вернуться и нажать ещё раз), "none" (файла нет). */
    static String install(Activity a) {
        if (!apk(a).isFile()) return "none";
        if (!canInstall(a)) {
            a.startActivity(new Intent("android.settings.MANAGE_UNKNOWN_APP_SOURCES", Uri.parse("package:" + a.getPackageName())));
            return "perm";
        }
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(Uri.parse("content://" + AUTH + "/Dewiar.apk"), "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        a.startActivity(i);
        return "ok";
    }

    /** При запуске: скачанная версия уже стоит (или старее) — файл больше не нужен. */
    static void cleanup(Context c) {
        File f = apk(c);
        if (!f.isFile()) return;
        try {
            PackageManager pm = c.getPackageManager();
            PackageInfo got = pm.getPackageArchiveInfo(f.getPath(), 0), cur = pm.getPackageInfo(c.getPackageName(), 0);
            if (got == null || got.versionCode <= cur.versionCode) //noinspection ResultOfMethodCallIgnored
                f.delete();
        } catch (Exception e) {
            //noinspection ResultOfMethodCallIgnored
            f.delete();
        }
    }
}
