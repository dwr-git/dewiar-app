package pro.dewiar.app;

import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.database.Cursor;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.Uri;
import android.os.BatteryManager;
import android.provider.ContactsContract;
import java.util.List;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONObject;

/** Руки на телефоне: звонок, SMS, приложения, сайты, фонарик, громкость, батарея. Зовётся из Bridge.java по просьбе
 *  инструментов модели в app.js. Сравнение имён (контакты, приложения) — в Names.java, чтобы проверять его без Android.
 *  Чужие приложения видны только те, что перечислены в <queries> AndroidManifest.xml (Android 11+): новое намерение
 *  добавляй и туда. */
public final class Phone {
    private Phone() { }

    static String norm(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT).replace('ё', 'е').trim(); }

    static int score(String want, String have) { return Names.score(want, have); }

    /** Для названий приложений: «Яндекс.Музыка», «Яндекс-Музыка», «яндекс музыка» — одно и то же. */
    static String flat(String s) { return norm(s).replaceAll("[.\\-_·:/]+", " ").replaceAll("\\s+", " ").trim(); }

    /** Контакт по имени -> {name, number, alts: [{name, number}]} или null. alts — другие люди с почти таким же совпадением:
     *  тогда лучше спросить, кому звонить, чем звонить не тому. Нужно разрешение READ_CONTACTS. */
    public static JSONObject contact(Context c, String who) {
        Cursor cur = null;
        try {
            cur = c.getContentResolver().query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                    new String[]{ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER,
                            ContactsContract.CommonDataKinds.Phone.IS_SUPER_PRIMARY}, null, null, null);
            if (cur == null) return null;
            java.util.List<Object[]> all = new java.util.ArrayList<Object[]>();
            while (cur.moveToNext()) {
                String name = cur.getString(0), num = cur.getString(1);
                if (name == null || num == null) continue;
                int s = score(who, name);
                if (s >= 43) all.add(new Object[]{s + (cur.getInt(2) > 0 ? 1 : 0), name, num});   // основной номер контакта — на балл выше
            }
            if (all.isEmpty()) return null;
            java.util.Collections.sort(all, new java.util.Comparator<Object[]>() {
                @Override public int compare(Object[] x, Object[] y) { return (Integer) y[0] - (Integer) x[0]; }
            });
            Object[] top = all.get(0);
            JSONArray alts = new JSONArray();
            java.util.Set<String> seen = new java.util.HashSet<String>();
            seen.add(norm((String) top[1]));
            for (Object[] o : all) {                    // другие имена не дальше 3 баллов от лучшего, до 4 штук
                if ((Integer) o[0] >= (Integer) top[0] - 3 && seen.add(norm((String) o[1])) && alts.length() < 4)
                    alts.put(new JSONObject().put("name", o[1]).put("number", o[2]));
            }
            return new JSONObject().put("name", top[1]).put("number", top[2]).put("alts", alts);
        } catch (Throwable ignored) {
        } finally { if (cur != null) cur.close(); }
        return null;
    }

    /** direct — звонить сразу (нужно разрешение CALL_PHONE), иначе открыть набор номера. */
    public static boolean call(Context c, String number, boolean direct) {
        try {
            Intent i = new Intent(direct ? Intent.ACTION_CALL : Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(number)))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            c.startActivity(i);
            return true;
        } catch (Throwable e) { return false; }
    }

    /** Открыть SMS с готовым текстом — отправляет человек сам. */
    public static boolean sms(Context c, String number, String text) {
        try {
            Intent i = new Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + Uri.encode(number == null ? "" : number)))
                    .putExtra("sms_body", text).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            c.startActivity(i);
            return true;
        } catch (Throwable e) { return false; }
    }

    private static List<ResolveInfo> launchers(Context c) {
        Intent i = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        return c.getPackageManager().queryIntentActivities(i, 0);
    }

    public static JSONArray apps(Context c) {
        JSONArray a = new JSONArray();
        PackageManager pm = c.getPackageManager();
        for (ResolveInfo r : launchers(c)) a.put(String.valueOf(r.loadLabel(pm)));
        return a;
    }

    /** Открыть приложение по названию -> настоящее название или "". Кроме Names.score: точное название — 100, одно
     *  начинается с другого («телеграм» / «Телеграм X») — 70, содержит — 55; меньше 45 — не открываем.
     *  Правила «начинается»/«содержит» — от 3 букв: «те» начинается и у «Телефона», и у «Телеграма» (Names.score короткое
     *  слово и так засчитывает только целиком). */
    public static String openApp(Context c, String name) {
        PackageManager pm = c.getPackageManager();
        ResolveInfo best = null;
        int bs = 0;
        String w = flat(name);
        if (w.isEmpty()) return "";
        for (ResolveInfo r : launchers(c)) {
            String label = String.valueOf(r.loadLabel(pm));
            String l = flat(label);
            int s = l.equals(w) ? 100 : score(w, label);
            if (s < 100 && w.length() >= 3) {
                if (l.startsWith(w)) s = Math.max(s, 70);
                else if (l.length() >= 3 && w.startsWith(l)) {
                    // №290 (пакет 27.10): «открой Яндекс Музыку» открыло «Яндекс» (браузер): метка короче запроса подходит,
                    // только если остаток — общие слова («приложение»), а не другое название
                    String rest = w.substring(l.length()).trim();
                    boolean generic = rest.isEmpty() || rest.matches("(?:приложени\\S*|app|прилож\\S*|на телефоне|пожалуйста|\\s)+");
                    s = generic ? Math.max(s, 70) : Math.min(s, 40);
                }
                else if (l.contains(w)) s = Math.max(s, 55);
            }
            if (s > bs) { bs = s; best = r; }
        }
        if (best == null || bs < 45) return "";
        Intent i = pm.getLaunchIntentForPackage(best.activityInfo.packageName);
        if (i == null) return "";
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { c.startActivity(i); } catch (ActivityNotFoundException e) { return ""; }
        return String.valueOf(best.loadLabel(pm));
    }

    public static boolean openUrl(Context c, String url) {
        try {
            c.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return true;
        } catch (Throwable e) { return false; }
    }

    /** Фонарик — вспышка первой камеры, у которой она есть. false — вспышки нет или камера занята. */
    public static boolean torch(Context c, boolean on) {
        try {
            CameraManager cm = (CameraManager) c.getSystemService(Context.CAMERA_SERVICE);
            for (String id : cm.getCameraIdList()) {
                Boolean f = cm.getCameraCharacteristics(id).get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                if (f != null && f) { cm.setTorchMode(id, on); return true; }
            }
        } catch (Throwable ignored) { }
        return false;
    }

    /** op: up, down, set (value 0–100), mute, unmute -> громкость музыки в процентах. */
    public static int volume(Context c, String op, int value) {
        AudioManager am = (AudioManager) c.getSystemService(Context.AUDIO_SERVICE);
        int st = AudioManager.STREAM_MUSIC, max = am.getStreamMaxVolume(st);
        try {
            if ("up".equals(op) || "down".equals(op)) {      // «тише» — заметно: шаг value% (по умолчанию 20%), не меньше одного деления
                int step = Math.max(1, Math.round(max * (value > 0 ? Math.min(100, value) : 20) / 100f));
                int cur = am.getStreamVolume(st), to = Math.max(0, Math.min(max, cur + ("up".equals(op) ? step : -step)));
                if (to == 0 && cur > 1 && "down".equals(op)) to = 1;   // «тише» не выключает звук совсем
                am.setStreamVolume(st, to, AudioManager.FLAG_SHOW_UI);
            }
            else if ("mute".equals(op)) am.adjustStreamVolume(st, AudioManager.ADJUST_MUTE, AudioManager.FLAG_SHOW_UI);
            else if ("unmute".equals(op)) am.adjustStreamVolume(st, AudioManager.ADJUST_UNMUTE, AudioManager.FLAG_SHOW_UI);
            else if ("set".equals(op)) am.setStreamVolume(st, Math.round(max * Math.max(0, Math.min(100, value)) / 100f), AudioManager.FLAG_SHOW_UI);
        } catch (Throwable ignored) { }
        return Math.round(100f * am.getStreamVolume(st) / Math.max(1, max));
    }

    public static JSONObject battery(Context c) {
        JSONObject o = new JSONObject();
        try {
            BatteryManager bm = (BatteryManager) c.getSystemService(Context.BATTERY_SERVICE);
            o.put("percent", bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY));
            o.put("charging", bm.isCharging());
        } catch (Throwable ignored) { }
        return o;
    }
}
