package pro.dewiar.app;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.net.Authenticator;
import java.net.InetSocketAddress;
import java.net.PasswordAuthentication;
import java.net.Proxy;
import java.net.URI;
import java.net.URL;
import java.net.URLConnection;
import java.net.URLDecoder;
import java.util.Locale;

/** Прокси только для серверов Dewiar (dewiar.pro, поддомены, сайт аккаунта и облака): у части провайдеров dewiar.pro
 *  заблокирован. Всё остальное (свой сервер моделей, распознавание в домашней сети) идёт напрямую — трафик прокси платный.
 *  Настраивает app.js (applyProxy → Dewiar.setProxy в Bridge.java), соединения открывают Net.java и другие через open().
 *  Части: set() — разбор адреса прокси; open() — выбор пути; relay/tunnel — свой мостик для HTTPS через HTTP-прокси с логином.
 *  Без зависимостей от Android — проверяется обычной Java (tests/android_proxy_test.py). */
public final class NetProxy {
    private static volatile Proxy proxy = null;
    private static volatile String[] hosts = { "dewiar.pro" };
    private static volatile String user = null, pass = null, proxyHost = null;
    private static volatile int proxyPort = 0;
    private static volatile ServerSocket relay = null;      // мостик на 127.0.0.1 для HTTPS через HTTP-прокси (см. open)

    private NetProxy() { }

    /** spec — socks5://user:pass@host:1080 | http://host:3128 | host:port (= http) | "" (выключить); hostsCsv — ещё адреса
     *  Dewiar через запятую (dewiar.pro есть всегда; localhost и 127.* не берём — к себе через прокси не ходят).
     *  Неверный адрес → IllegalArgumentException с текстом для человека, прокси выключается. Логин — в общий Authenticator
     *  (он один на процесс, поэтому отдаёт логин только самому прокси, не сайтам). */
    public static synchronized void set(String spec, String hostsCsv) {
        java.util.ArrayList<String> hs = new java.util.ArrayList<>();
        hs.add("dewiar.pro");
        if (hostsCsv != null) {
            for (String h : hostsCsv.split(",")) {
                String x = hostOf(h.trim());
                if (!x.isEmpty() && !hs.contains(x) && !x.equals("localhost") && !x.startsWith("127.")) hs.add(x);
            }
        }
        hosts = hs.toArray(new String[0]);
        String s = spec == null ? "" : spec.trim();
        if (s.isEmpty()) { proxy = null; user = pass = proxyHost = null; return; }
        try {
            URI u = new URI(s.contains("://") ? s : "http://" + s);
            String sch = u.getScheme() == null ? "http" : u.getScheme().toLowerCase(Locale.ROOT);
            if (u.getHost() == null || u.getPort() <= 0) throw new IllegalArgumentException("у прокси нужен адрес и порт");
            Proxy.Type t = sch.startsWith("socks") ? Proxy.Type.SOCKS : Proxy.Type.HTTP;
            String ui = u.getRawUserInfo();
            if (ui != null && !ui.isEmpty()) {
                int i = ui.indexOf(':');
                user = URLDecoder.decode(i < 0 ? ui : ui.substring(0, i), "UTF-8");
                pass = i < 0 ? "" : URLDecoder.decode(ui.substring(i + 1), "UTF-8");
            } else { user = pass = null; }
            proxyHost = u.getHost();
            proxyPort = u.getPort();
            // createUnresolved: имя сайта узнаёт прокси — блокировка по DNS у провайдера не мешает
            proxy = new Proxy(t, InetSocketAddress.createUnresolved(u.getHost(), u.getPort()));
            if (user != null) {
                Authenticator.setDefault(new Authenticator() {
                    @Override protected PasswordAuthentication getPasswordAuthentication() {
                        String rh = getRequestingHost();
                        boolean forProxy = getRequestorType() == RequestorType.PROXY || (rh != null && rh.equalsIgnoreCase(proxyHost))
                            || "SOCKS5".equalsIgnoreCase(getRequestingProtocol()) || "SOCKS authentication".equalsIgnoreCase(getRequestingPrompt());
                        String uu = user, pp = pass;
                        return forProxy && uu != null ? new PasswordAuthentication(uu, (pp == null ? "" : pp).toCharArray()) : null;
                    }
                });
            }
        } catch (Exception e) {
            proxy = null;
            throw new IllegalArgumentException("прокси — socks5://адрес:порт или http://адрес:порт");
        }
    }

    static String hostOf(String url) {
        if (url == null || url.isEmpty()) return "";
        try {
            String h = new URI(url.contains("://") ? url : "https://" + url).getHost();
            return h == null ? "" : h.toLowerCase(Locale.ROOT);
        } catch (Exception e) { return ""; }
    }

    /** Пойдёт ли адрес через прокси: прокси задан и хост — один из адресов Dewiar или их поддомен. */
    public static boolean uses(URL u) {
        if (proxy == null || u == null || u.getHost() == null) return false;
        String h = u.getHost().toLowerCase(Locale.ROOT);
        for (String d : hosts) if (h.equals(d) || h.endsWith("." + d)) return true;
        return false;
    }

    /** №1113 (26.11): «Не проверилось: unexpected end of stream on null» — с 0.9.81 по 0.9.93 на одном телефоне, на
     *  мобильной связи и в Wi-Fi, а сайт в браузере открывается. «…on null» Android пишет, только когда прокси на пути
     *  (свой, прокси Dewiar или прокси из настроек Wi-Fi/VPN) молча закрыл связь на CONNECT. Такой отказ — признак
     *  прокси, а не сервера: следующий раз — напрямую, мимо любых прокси (Net.request), и, если так открылось, DIRECT_MS
     *  все запросы к этому адресу — напрямую. Повтор безопасен: до сервера запрос не дошёл. */
    static final long DIRECT_MS = 15 * 60 * 1000L;
    private static final java.util.concurrent.ConcurrentHashMap<String, Long> DIRECT = new java.util.concurrent.ConcurrentHashMap<>();

    /** Отказ похож на отказ прокси (а не сервера): EOF на CONNECT, ответ прокси вместо туннеля, SOCKS. */
    public static boolean proxyFail(Throwable e) {
        String m = String.valueOf(e == null ? "" : e.getMessage());
        return m.contains("end of stream on null") || m.contains("response code for CONNECT") || m.contains("authenticate with proxy")
            || m.contains("SOCKS") || m.contains("Proxy Authentication");
    }

    /** Пошёл бы этот адрес через какой-нибудь прокси: свой/Dewiar (uses) или системный (настройки Wi-Fi, VPN). */
    public static boolean viaAnyProxy(URL u) {
        if (uses(u)) return true;
        try {
            for (Proxy x : java.net.ProxySelector.getDefault().select(u.toURI())) if (x.type() != Proxy.Type.DIRECT) return true;
        } catch (Throwable ignored) { }
        return false;
    }

    /** Напрямую, мимо любых прокси. */
    public static URLConnection openDirect(URL u) throws IOException { return u.openConnection(Proxy.NO_PROXY); }

    /** Напрямую открылось, когда через прокси — нет: DIRECT_MS к этому адресу ходим напрямую. */
    public static void directOk(URL u) { if (u != null && u.getHost() != null) DIRECT.put(u.getHost().toLowerCase(Locale.ROOT), System.currentTimeMillis() + DIRECT_MS); }

    static boolean directNow(URL u) {
        if (u == null || u.getHost() == null) return false;
        Long t = DIRECT.get(u.getHost().toLowerCase(Locale.ROOT));
        return t != null && System.currentTimeMillis() < t;
    }

    /** Открыть соединение: адреса Dewiar — через прокси (если задан), остальное — напрямую. */
    public static URLConnection open(URL u) throws IOException {
        if (directNow(u)) return openDirect(u);
        Proxy p = proxy;
        if (p != null && uses(u) && p.type() == Proxy.Type.HTTP && "https".equalsIgnoreCase(u.getProtocol())) {
            // HTTPS через HTTP-прокси. Android (OkHttp) шлёт CONNECT без логина и ждёт ответа 407, а платные
            // прокси просто рвут такую связь («unexpected end of stream»). Поэтому туннель строит свой мостик на
            // 127.0.0.1: он сразу передаёт прокси логин (как браузеры и Dewiar на компьютере) и повторяет соединение,
            // если прокси ответил 5xx или оборвал его — такие прокси нередко пропускают не с первого раза.
            return u.openConnection(new Proxy(Proxy.Type.HTTP, new InetSocketAddress(InetAddress.getByName("127.0.0.1"), relayPort())));
        }
        if (p != null && uses(u)) {
            URLConnection c = u.openConnection(p);
            String uu = user, pp = pass;
            if (uu != null && p.type() == Proxy.Type.HTTP && "http".equalsIgnoreCase(u.getProtocol())) {   // http через HTTP-прокси: логин в каждом запросе, без ожидания 407
                c.setRequestProperty("Proxy-Authorization", "Basic " + b64((uu + ":" + (pp == null ? "" : pp)).getBytes("UTF-8")));
            }
            return c;
        }
        return u.openConnection();                    // напрямую — по сетевым настройкам телефона
    }

    private static synchronized int relayPort() throws IOException {
        ServerSocket ss = relay;
        if (ss != null && !ss.isClosed()) return ss.getLocalPort();
        final ServerSocket srv = new ServerSocket(0, 50, InetAddress.getByName("127.0.0.1"));
        relay = srv;
        // без лямбд: javac против android.jar API 23 (tools/build_apk.sh) их не собирает
        Thread t = new Thread(new Runnable() { @Override public void run() {
            while (!srv.isClosed()) {
                try {
                    final Socket c = srv.accept();
                    Thread w = new Thread(new Runnable() { @Override public void run() { tunnel(c); } }, "dewiar-proxy");
                    w.setDaemon(true);
                    w.start();
                } catch (IOException e) { if (srv.isClosed()) return; }
            }
        } }, "dewiar-proxy-relay");
        t.setDaemon(true);
        t.start();
        return srv.getLocalPort();
    }

    /** Одна связь через мостик: CONNECT от приложения → CONNECT к прокси с логином → дальше байты как есть (TLS — между
     *  приложением и сервером, мостик его не видит). Ответа прокси так и не дал — приложению уходит 407 (последняя попытка:
     *  прокси молча закрыл связь, чаще всего неверный логин) или 502 (не принял соединение). */
    private static void tunnel(Socket c) {
        Socket up = null;
        try {
            c.setSoTimeout(30000);
            InputStream cin = c.getInputStream();
            OutputStream cout = c.getOutputStream();
            String head = readHead(cin);
            String[] first = head.split("\r\n", 2)[0].split(" ");
            if (first.length < 2 || !"CONNECT".equalsIgnoreCase(first[0])) { cout.write("HTTP/1.1 405 Method Not Allowed\r\n\r\n".getBytes("UTF-8")); return; }
            String target = first[1];
            int colon = target.lastIndexOf(':');
            String th = colon > 0 ? target.substring(0, colon) : target;
            if (!uses(new URL("https://" + th + "/"))) {      // мостик слушает 127.0.0.1, куда может постучаться любая программа телефона — пускаем только к адресам Dewiar
                cout.write("HTTP/1.1 403 Forbidden\r\n\r\n".getBytes("UTF-8"));
                return;
            }
            // Платные и общие прокси нередко отвечают «502 Bad Gateway» или молча рвут связь, а со второго-третьего раза
            // пропускают. До сервера Dewiar запрос ещё не дошёл — повторяем сами, человек ошибки не видит.
            String resp = null;
            boolean closed = false;
            for (int attempt = 0; attempt < 4; attempt++) {
                if (attempt > 0) {
                    try { Thread.sleep(attempt == 1 ? 400 : attempt == 2 ? 1200 : 2500); } catch (InterruptedException ie) { break; }
                }
                if (up != null) { try { up.close(); } catch (IOException e) { } up = null; }
                try {
                    up = new Socket();
                    up.connect(new InetSocketAddress(proxyHost, proxyPort), 15000);
                    up.setSoTimeout(30000);
                } catch (IOException e) {
                    closed = false; resp = null;
                    continue;                                 // прокси не принял соединение — ещё раз
                }
                String uu = user, pp = pass;
                String req = "CONNECT " + target + " HTTP/1.1\r\nHost: " + target + "\r\n"
                    + (uu != null ? "Proxy-Authorization: Basic " + b64((uu + ":" + (pp == null ? "" : pp)).getBytes("UTF-8")) + "\r\n" : "")
                    + "Proxy-Connection: Keep-Alive\r\n\r\n";
                OutputStream uout = up.getOutputStream();
                uout.write(req.getBytes("UTF-8"));
                uout.flush();
                try { resp = readHead(up.getInputStream()); closed = false; }
                catch (IOException e) { resp = null; closed = true; continue; }   // молча закрыл — бывает и сбой, и неверный логин
                String[] s0 = resp.split(" ", 3);
                if (s0.length >= 2 && s0[1].length() == 3 && s0[1].charAt(0) == '5') continue;   // 502/503/504 — повторим
                break;
            }
            if (resp == null) {
                cout.write((closed ? "HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 0\r\n\r\n"
                                   : "HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n").getBytes("UTF-8"));
                return;
            }
            cout.write(resp.getBytes("ISO-8859-1"));
            cout.flush();
            String[] st = resp.split(" ", 3);
            if (st.length < 2 || !st[1].equals("200")) return;
            c.setSoTimeout(0);
            up.setSoTimeout(0);
            final Socket fu = up, fc = c;
            Thread back = new Thread(new Runnable() { @Override public void run() { pump(fu, fc); } }, "dewiar-proxy-in");
            back.setDaemon(true);
            back.start();
            pump(c, up);
            back.join();
        } catch (Exception e) {
            // связь оборвалась — приложение получит ошибку соединения и покажет её
        } finally {
            try { c.close(); } catch (IOException e) { }
            if (up != null) try { up.close(); } catch (IOException e) { }
        }
    }

    private static void pump(Socket from, Socket to) {
        byte[] b = new byte[16384];
        try {
            InputStream in = from.getInputStream();
            OutputStream out = to.getOutputStream();
            for (int n; (n = in.read(b)) > 0; ) { out.write(b, 0, n); out.flush(); }
        } catch (IOException e) { }
        try { to.shutdownOutput(); } catch (IOException e) { }
    }

    /** Заголовок HTTP до пустой строки (не больше 16 КБ). */
    private static String readHead(InputStream in) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        int a1 = 0, a2 = 0, a3 = 0;                        // три предыдущих байта
        while (b.size() < 16384) {
            int x = in.read();
            if (x < 0) throw new IOException("прокси закрыл соединение");
            b.write(x);
            if ((x == '\n' && a1 == '\r' && a2 == '\n' && a3 == '\r') || (x == '\n' && a1 == '\n')) return b.toString("ISO-8859-1");
            a3 = a2; a2 = a1; a1 = x;
        }
        throw new IOException("слишком длинный ответ прокси");
    }

    private static String b64(byte[] b) {
        final String A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
        StringBuilder s = new StringBuilder();
        for (int i = 0; i < b.length; i += 3) {
            int n = (b[i] & 0xff) << 16 | (i + 1 < b.length ? (b[i + 1] & 0xff) << 8 : 0) | (i + 2 < b.length ? b[i + 2] & 0xff : 0);
            s.append(A.charAt(n >> 18 & 63)).append(A.charAt(n >> 12 & 63));
            s.append(i + 1 < b.length ? A.charAt(n >> 6 & 63) : '=').append(i + 2 < b.length ? A.charAt(n & 63) : '=');
        }
        return s.toString();
    }
}
