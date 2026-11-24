package pro.dewiar.app;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Iterator;
import java.util.concurrent.ConcurrentHashMap;
import org.json.JSONObject;

/** HTTP для интерфейса в обход ограничений CORS у WebView: app.js зовёт Dewiar.http(id, …) (Bridge.java), ответ приходит
 *  событиями N.ev с тем же id — http_chunk (поток строк, SSE от модели), http_done {status, body}, http_error {error}.
 *  Все соединения открываются через NetProxy.open: адреса Dewiar — через прокси, если он задан.
 *  Здесь же readAll и postMultipart (отправка записи голоса на сервер распознавания, Speech.java). */
public final class Net {
    public interface Sink { void event(String type, JSONObject data); }

    private static final ConcurrentHashMap<String, HttpURLConnection> RUNNING = new ConcurrentHashMap<>();

    private Net() { }

    /** Запрос в своём потоке. headers — JSON-объект строк. Ответ 4xx/5xx — это http_done со статусом и телом ошибки
     *  (поток при этом не включается); http_error — только сбой связи или abort(). timeoutMs ≤ 0 — 2 минуты на чтение. */
    public static void request(final String id, final String method, final String url, final String headers, final String body,
                               final boolean stream, final int timeoutMs, final Sink sink) {
        new Thread(new Runnable() {
            @Override public void run() {
                HttpURLConnection c = null;
                boolean got = false;                                  // ответ уже начал приходить — повторять нельзя
                for (int attempt = 0; ; attempt++) {
                try {
                    c = (HttpURLConnection) NetProxy.open(new URL(url));
                    // №994 (24.11): «Не проверилось: unexpected end of stream on null» — обновление и отчёт с телефона. Сервер
                    // закрыл соединение, не ответив (старое «живое» соединение или обрыв сети по пути). Второй раз —
                    // новым соединением, без повторного использования
                    if (attempt > 0) c.setRequestProperty("Connection", "close");
                    RUNNING.put(id, c);
                    c.setRequestMethod(method == null || method.isEmpty() ? "GET" : method);
                    c.setConnectTimeout(15000);
                    c.setReadTimeout(timeoutMs > 0 ? timeoutMs : 120000);
                    c.setRequestProperty("User-Agent", "Dewiar-Android/" + BuildInfo.VERSION);
                    boolean gz = false;
                    if (headers != null && !headers.isEmpty()) {
                        JSONObject h = new JSONObject(headers);
                        Iterator<String> it = h.keys();
                        while (it.hasNext()) {
                            String k = it.next(), v = h.getString(k);
                            c.setRequestProperty(k, v);
                            if ("content-encoding".equalsIgnoreCase(k) && "gzip".equalsIgnoreCase(v.trim())) gz = true;
                        }
                    }
                    if (body != null && !body.isEmpty()) {
                        c.setDoOutput(true);
                        byte[] b = body.getBytes("UTF-8");
                        // 1.0.67: «Content-Encoding: gzip» от страницы — тело сжимаем здесь (запрос к облаку Dewiar: 60–150 КБ
                        // подсказки, а сети по пути «замирают» на больших запросах к зарубежным адресам)
                        if (gz) {
                            ByteArrayOutputStream zb = new ByteArrayOutputStream(b.length / 3 + 64);
                            java.util.zip.GZIPOutputStream zo = new java.util.zip.GZIPOutputStream(zb);
                            zo.write(b);
                            zo.close();
                            b = zb.toByteArray();
                        }
                        c.setFixedLengthStreamingMode(b.length);
                        OutputStream os = c.getOutputStream();
                        os.write(b);
                        os.close();
                    }
                    int code = c.getResponseCode();
                    got = true;
                    InputStream in = code >= 400 ? c.getErrorStream() : c.getInputStream();
                    if (stream && code < 400 && in != null) {
                        BufferedReader r = new BufferedReader(new InputStreamReader(in, "UTF-8"));
                        String line;
                        StringBuilder batch = new StringBuilder();
                        long last = System.currentTimeMillis();
                        while ((line = r.readLine()) != null) {
                            batch.append(line).append('\n');
                            long now = System.currentTimeMillis();
                            if (now - last > 40 || batch.length() > 4000) {      // пачками: каждый вызов evaluateJavascript дорог
                                sink.event("http_chunk", new JSONObject().put("id", id).put("text", batch.toString()));
                                batch.setLength(0);
                                last = now;
                            }
                        }
                        if (batch.length() > 0) sink.event("http_chunk", new JSONObject().put("id", id).put("text", batch.toString()));
                        sink.event("http_done", new JSONObject().put("id", id).put("status", code).put("body", ""));
                    } else {
                        String text = in == null ? "" : readAll(in);
                        // url — куда привели переадресации (короткая ссылка на карту → полный адрес с координатами)
                        sink.event("http_done", new JSONObject().put("id", id).put("status", code).put("body", text).put("url", c.getURL().toString()));
                    }
                    break;
                } catch (Throwable e) {
                    String m = String.valueOf(e.getMessage());
                    boolean again = attempt == 0 && !got && RUNNING.containsKey(id) && (e instanceof java.io.IOException)
                            && (m.contains("unexpected end of stream") || m.contains("Connection reset") || m.contains("closed"));
                    if (again) {
                        try { c.disconnect(); } catch (Throwable ignored) { }
                        try { Thread.sleep(700); } catch (InterruptedException ignored) { }
                        continue;
                    }
                    try { sink.event("http_error", new JSONObject().put("id", id).put("error", String.valueOf(e.getMessage() == null ? e : e.getMessage()))); }
                    catch (Throwable ignored) { }
                    break;
                } finally {
                    if (c != null) c.disconnect();
                }
                }
                RUNNING.remove(id);
            }
        }, "http-" + id).start();
    }

    /** Оборвать запрос: поток запроса получит ошибку и пришлёт http_error. */
    public static void abort(String id) {
        HttpURLConnection c = RUNNING.remove(id);
        if (c != null) {
            try { c.disconnect(); } catch (Throwable ignored) { }
        }
    }

    /** -> содержимое потока; null (getErrorStream() у ответа с ошибкой без тела) — "", иначе вместо кода ответа
     *  наружу уйдёт NullPointerException. */
    public static String readAll(InputStream in) throws java.io.IOException {
        if (in == null) return "";
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        byte[] buf = new byte[16384];
        int n;
        while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
        in.close();
        return bo.toString("UTF-8");
    }

    /** multipart/form-data: файл (WAV) + поля — для распознавания речи на сервере. Блокирует — звать не из потока UI.
     *  -> тело ответа; 4xx/5xx — исключение. */
    public static String postMultipart(String url, String key, byte[] file, String fileName, String mime, JSONObject fields) throws Exception {
        String bnd = "----dewiar" + System.nanoTime();
        HttpURLConnection c = (HttpURLConnection) NetProxy.open(new URL(url));
        c.setConnectTimeout(15000);
        c.setReadTimeout(60000);
        c.setDoOutput(true);
        c.setRequestMethod("POST");
        c.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + bnd);
        if (key != null && !key.isEmpty()) c.setRequestProperty("Authorization", "Bearer " + key);
        ByteArrayOutputStream bo = new ByteArrayOutputStream();
        Iterator<String> it = fields.keys();
        while (it.hasNext()) {
            String k = it.next();
            bo.write(("--" + bnd + "\r\nContent-Disposition: form-data; name=\"" + k + "\"\r\n\r\n" + fields.getString(k) + "\r\n").getBytes("UTF-8"));
        }
        bo.write(("--" + bnd + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + fileName + "\"\r\nContent-Type: " + mime + "\r\n\r\n").getBytes("UTF-8"));
        bo.write(file);
        bo.write(("\r\n--" + bnd + "--\r\n").getBytes("UTF-8"));
        byte[] all = bo.toByteArray();
        c.setFixedLengthStreamingMode(all.length);
        OutputStream os = c.getOutputStream();
        os.write(all);
        os.close();
        int code = c.getResponseCode();
        String text = readAll(code >= 400 ? c.getErrorStream() : c.getInputStream());
        c.disconnect();
        if (code >= 400) {                                  // и что сказал сервер («Заряд Dewiar Облака закончился…») — приложение решит, что делать
            String why = "";
            try { why = new JSONObject(text).getJSONObject("error").optString("message", ""); } catch (Exception ignored) { }
            throw new Exception("сервер распознавания ответил " + code + (why.isEmpty() ? "" : ": " + (why.length() > 200 ? why.substring(0, 200) : why)));
        }
        return text;
    }
}
