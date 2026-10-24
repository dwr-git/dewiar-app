package pro.dewiar.app;

import android.app.NotificationManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.RingtoneManager;
import android.net.Uri;
import android.os.Build;
import java.io.File;
import java.lang.reflect.Constructor;
import java.util.List;

/** Звук напоминаний и будильников. Выбор — в настройках интерфейса («Ещё» → «Звук напоминаний», Bridge.alarmSound*),
 *  хранится в SharedPreferences "dewiar" под ключом alarm_sound:
 *    signature (фирменный: «Струна», 24.10) | chasha | kolodec | hor | glubina (tools/brand_sounds.py) | motif (прежний мотив Dewiar) |
 *    drops | orbit | chime | marimba | harp | dawn — свои мелодии (res/raw/alarm_*.ogg, синтез — tools/alarm_sounds.py);
 *    system — системный звук будильника; custom — свой файл (files/alarm_custom, отдаёт SoundProvider).
 *  Канал уведомлений Android запоминает звук при создании, поэтому у каждого звука свой канал alarm_<звук> (у своего
 *  файла — ещё и с отметкой времени файла); при смене прежний канал удаляется. Уведомление играет мелодию один раз,
 *  окно будильника (AlarmActivity) — по кругу, начиная тихо и плавно прибавляя громкость. */
final class Sounds {
    static final String DEFAULT = "signature";
    static final String QUIET = "alarm_watch";        // окно будильника открыто: уведомление остаётся (и на часах), но молчит
    private Sounds() { }

    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences("dewiar", Context.MODE_PRIVATE); }

    static File customFile(Context c) { return new File(c.getFilesDir(), "alarm_custom"); }

    /** Выбранный звук; свой файл пропал — мелодия по умолчанию. */
    static String current(Context c) {
        String s = prefs(c).getString("alarm_sound", DEFAULT);
        if ("custom".equals(s) && !customFile(c).isFile()) return DEFAULT;
        return res(s) != 0 || "system".equals(s) || "custom".equals(s) ? s : DEFAULT;
    }

    static void set(Context c, String id) {
        prefs(c).edit().putString("alarm_sound", id).apply();
        channel(c);
    }

    static int res(String id) {
        switch (id == null ? "" : id) {
            case "signature": return R.raw.alarm_signature;
            case "chasha": return R.raw.alarm_chasha;
            case "kolodec": return R.raw.alarm_kolodec;
            case "hor": return R.raw.alarm_hor;
            case "glubina": return R.raw.alarm_glubina;
            case "motif": return R.raw.alarm_motif;
            case "drops": return R.raw.alarm_drops;
            case "orbit": return R.raw.alarm_orbit;
            case "chime": return R.raw.alarm_chime;
            case "marimba": return R.raw.alarm_marimba;
            case "harp": return R.raw.alarm_harp;
            case "dawn": return R.raw.alarm_dawn;
            default: return 0;
        }
    }

    static String label(String id) {
        switch (id) {
            case "signature": return "Струна";
            case "chasha": return "Чаша";
            case "kolodec": return "Колодец";
            case "hor": return "Хор";
            case "glubina": return "Глубина";
            case "motif": return "Прежний мотив";
            case "drops": return "Капли";
            case "orbit": return "Орбита";
            case "chime": return "Колокольчики";
            case "marimba": return "Маримба";
            case "harp": return "Арфа";
            case "dawn": return "Рассвет";
            case "system": return "Системный";
            default: return "Свой звук";
        }
    }

    static Uri uri(Context c, String id) {
        if ("system".equals(id)) {
            Uri u = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM);
            return u != null ? u : RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION);
        }
        if ("custom".equals(id)) return Uri.parse("content://" + SoundProvider.AUTH + "/custom?v=" + customFile(c).lastModified());
        // по имени, а не по числу: числа R.raw меняются, когда добавляются звуки (24.10), а канал хранит адрес навсегда
        return Uri.parse("android.resource://" + c.getPackageName() + "/raw/" + c.getResources().getResourceEntryName(res(id)));
    }

    static AudioAttributes attrs() {
        return new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();
    }

    /** Канал для будильников под текущий звук (создаёт; лишние alarm_* и старый «alarms» убирает). До Android 8 — без каналов. */
    static String channel(Context c) {
        String sound = current(c);
        // «_2» (24.10): прежние каналы помнили звук по числу ресурса и фирменный стал «Струной» — каналы пересоздаются
        String id = "alarm_" + sound + ("custom".equals(sound) ? "_" + customFile(c).lastModified() : "_2");
        if (Build.VERSION.SDK_INT < 26) return id;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            Class<?> chc = Class.forName("android.app.NotificationChannel");
            if (NotificationManager.class.getMethod("getNotificationChannel", String.class).invoke(nm, id) == null) {
                Constructor<?> k = chc.getConstructor(String.class, CharSequence.class, int.class);
                Object ch = k.newInstance(id, "Напоминания · " + label(sound), 4 /* IMPORTANCE_HIGH */);
                chc.getMethod("setSound", Uri.class, AudioAttributes.class).invoke(ch, uri(c, sound), attrs());
                chc.getMethod("enableVibration", boolean.class).invoke(ch, true);
                NotificationManager.class.getMethod("createNotificationChannel", chc).invoke(nm, ch);
            }
            List<?> all = (List<?>) NotificationManager.class.getMethod("getNotificationChannels").invoke(nm);
            for (Object ch : all) {
                String cid = (String) chc.getMethod("getId").invoke(ch);
                if ((cid.startsWith("alarm_") && !cid.equals(id) && !cid.equals(QUIET)) || cid.equals(Compat.CH_ALARM))
                    NotificationManager.class.getMethod("deleteNotificationChannel", String.class).invoke(nm, cid);
            }
        } catch (Throwable ignored) { }
        return id;
    }

    /** Тихий канал: окно будильника уже звучит само — уведомление в шторке остаётся, но не играет второй раз. */
    static String quietChannel(Context c) {
        if (Build.VERSION.SDK_INT < 26) return QUIET;
        try {
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (NotificationManager.class.getMethod("getNotificationChannel", String.class).invoke(nm, QUIET) == null) {
                Class<?> chc = Class.forName("android.app.NotificationChannel");
                // важный, но без звука и вибрации телефона: звучит само окно, а часы показывают только важные уведомления
                Object ch = chc.getConstructor(String.class, CharSequence.class, int.class).newInstance(QUIET, "Напоминание на экране и на часах", 4 /* IMPORTANCE_HIGH */);
                chc.getMethod("setSound", Uri.class, AudioAttributes.class).invoke(ch, null, null);
                chc.getMethod("enableVibration", boolean.class).invoke(ch, false);
                NotificationManager.class.getMethod("createNotificationChannel", chc).invoke(nm, ch);
            }
        } catch (Throwable ignored) { }
        return QUIET;
    }

    /** Проиграть звук будильника (loop — по кругу) с громкостью vol; не вышло (файл повреждён) — null. */
    static MediaPlayer play(Context c, String id, boolean loop, float vol) {
        MediaPlayer p = new MediaPlayer();
        try {
            p.setAudioAttributes(attrs());
            if ("custom".equals(id)) p.setDataSource(customFile(c).getAbsolutePath());
            else p.setDataSource(c, uri(c, id));
            p.setLooping(loop);
            p.setVolume(vol, vol);
            p.prepare();
            p.start();
            return p;
        } catch (Throwable e) {
            try { p.release(); } catch (Throwable ignored) { }
            return null;
        }
    }
}
