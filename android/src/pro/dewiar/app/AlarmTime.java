package pro.dewiar.app;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Locale;
import java.util.TimeZone;

/** Время напоминаний — без Android (только java.util): опоздание, пропущенное, «стенное» время будильника при смене
 *  часового пояса. Отдельно, чтобы проверка (tests/phone_alarm_late087_test.py) гоняла настоящий код на обычной Java.
 *  0.87 (владелец 11.11: «напоминание приходит на час позже, как будто телефон спал»): опоздавшее говорит об этом
 *  прямо — «(должно было в 14:00)», а пропущенное, пока телефон был выключен, не пропадает молча. */
final class AlarmTime {
    static final long LATE_MS = 2 * 60000L;          // с какого опоздания писать «должно было в …»
    static final long LOUD_LATE_MS = 30 * 60000L;    // пропущенное до получаса — звенит как обычно, позже — тихое «пропущено»
    static final long KEEP_MS = 24 * 3600000L;       // пропущенное больше суток назад — уже не показываем
    static final long RING_MS = 2 * 60000L;          // звонит 2 минуты, потом смолкает (уведомление с кнопками остаётся)
    static final long DUE_SOON_MS = 60000L;          // «только что»: до минуты назад — ставим как обычно, сработает сразу

    static final int NOT_MISSED = 0, MISSED_LOUD = 1, MISSED_QUIET = 2, MISSED_DROP = 3;

    private AlarmTime() { }

    /** Что делать со временем at, которое уже могло пройти: NOT_MISSED — не прошло или прошло меньше минуты назад
     *  (AlarmManager сработает сразу); MISSED_LOUD — опоздание до получаса, звонить сейчас; MISSED_QUIET — до суток,
     *  тихое уведомление «пропущено»; MISSED_DROP — старше суток, убрать молча (в журнал). */
    static int missed(long at, long now) {
        long late = now - at;
        if (late <= DUE_SOON_MS) return NOT_MISSED;
        if (late <= LOUD_LATE_MS) return MISSED_LOUD;
        if (late <= KEEP_MS) return MISSED_QUIET;
        return MISSED_DROP;
    }

    /** Подпись к опоздавшему: « (должно было в 14:00)», « (должно было вчера в 23:30)», « (должно было 10.11 в 14:00)».
     *  Вовремя (меньше 2 минут) или время неизвестно — "". */
    static String lateNote(long due, long now, TimeZone tz) {
        if (due <= 0 || now - due < LATE_MS) return "";
        SimpleDateFormat hm = new SimpleDateFormat("HH:mm", Locale.US);
        hm.setTimeZone(tz);
        Calendar d = Calendar.getInstance(tz), n = Calendar.getInstance(tz);
        d.setTimeInMillis(due);
        n.setTimeInMillis(now);
        int days = dayIndex(n) - dayIndex(d);
        String when;
        if (days == 0) when = "в " + hm.format(d.getTime());
        else if (days == 1) when = "вчера в " + hm.format(d.getTime());
        else {
            SimpleDateFormat dm = new SimpleDateFormat("dd.MM", Locale.US);
            dm.setTimeZone(tz);
            when = dm.format(d.getTime()) + " в " + hm.format(d.getTime());
        }
        return " (должно было " + when + ")";
    }

    /** Насколько опоздало, словами для журнала и подсказки: «47 мин», «2 ч 5 мин». */
    static String lateSpan(long ms) {
        long m = Math.max(0, ms) / 60000L;
        if (m < 60) return m + " мин";
        return (m / 60) + " ч" + (m % 60 == 0 ? "" : " " + (m % 60) + " мин");
    }

    private static int dayIndex(Calendar k) { return k.get(Calendar.YEAR) * 400 + k.get(Calendar.DAY_OF_YEAR); }

    /** Местное время момента at в поясе tz («2026-11-11 07:00:00») — то, что человек видел на часах, ставя будильник. */
    static String wall(long at, TimeZone tz) {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US);
        f.setTimeZone(tz);
        return f.format(new java.util.Date(at));
    }

    /** Обратно: те же часы на стене, но в поясе tz → мс. Не разобрали — -1. */
    static long fromWall(String wall, TimeZone tz) {
        if (wall == null || wall.isEmpty()) return -1;
        try {
            SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US);
            f.setTimeZone(tz);
            f.setLenient(false);
            return f.parse(wall).getTime();
        } catch (Exception e) { return -1; }
    }

    /** Пояс сменился (перелёт, телефон сам поправил пояс по сети): будильник и повторяющееся («каждый день в 8») живут по
     *  часам на стене — как будильник в «Часах»; разовое напоминание и таймер остаются в том же мгновении. */
    static boolean followsWall(String kind, String repeat) {
        return "alarm".equals(kind) || (repeat != null && !repeat.isEmpty() && !"timer".equals(kind));
    }

    /** Новое время для сигнала после смены пояса: следует стене — те же часы в новом поясе, иначе — прежнее. */
    static long moved(long at, String kind, String repeat, String oldTz, String wall, TimeZone now) {
        if (oldTz == null || oldTz.isEmpty() || oldTz.equals(now.getID()) || !followsWall(kind, repeat)) return at;
        long w = fromWall(wall, now);
        return w > 0 ? w : at;
    }
}
