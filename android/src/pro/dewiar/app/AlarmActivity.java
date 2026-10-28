package pro.dewiar.app;

import android.app.Activity;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.Ringtone;
import android.media.RingtoneManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Vibrator;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONObject;

/** Окно будильника поверх блокировки (открывает AlarmReceiver): текст крупно, звонок и вибрация, «Понял» и «Отложить
 *  на 10 минут». Звук — выбранный в настройках (Sounds): по кругу, сначала тихо, за 20 секунд — до полной громкости;
 *  уведомление при этом переходит в тихий канал, чтобы не звучать вторым голосом. Звонит 2 минуты, потом смолкает,
 *  окно остаётся. Разметка — кодом, без XML-ресурсов.
 *  «Отложить» ставит новое разовое напоминание через Alarms.put с id вида «<id>-s<секунды>», исходное не трогает. */
public class AlarmActivity extends Activity {
    private Ringtone ring;                          // запасной путь: свой файл не открылся — системная мелодия
    private MediaPlayer player;
    private float vol = 0.25f;
    private Vibrator vib;
    private final Handler h = new Handler();
    private String id, title, kind;

    @SuppressWarnings("deprecation")
    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        // флаги окна — для Android до 8.1; новым хватает showWhenLocked/turnScreenOn в AndroidManifest.xml
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON | WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD);
        id = getIntent().getStringExtra("id");
        title = getIntent().getStringExtra("title");
        kind = getIntent().getStringExtra("kind");
        if (id == null) { finish(); return; }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(28), dp(40), dp(28), dp(40));
        GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TL_BR, new int[]{0xFF1B1530, 0xFF0B0B12, 0xFF231433});
        root.setBackground(bg);
        String who = Faces.name(this, getIntent().getStringExtra("who"));
        android.graphics.Bitmap face = Faces.bitmap(this, getIntent().getStringExtra("who"));
        if (face != null) {                               // кто напоминает — лицо персонажа над временем
            android.widget.ImageView iv = new android.widget.ImageView(this);
            iv.setImageBitmap(face);
            LinearLayout.LayoutParams fl = new LinearLayout.LayoutParams(dp(96), dp(96));
            fl.gravity = Gravity.CENTER_HORIZONTAL;
            fl.bottomMargin = dp(14);
            root.addView(iv, fl);
        }
        TextView head = new TextView(this);
        String what = "alarm".equals(kind) ? "Будильник" : "timer".equals(kind) ? "Таймер" : "Напоминание";
        head.setText(who.isEmpty() ? what : who + " · " + what);
        head.setTextColor(0xFFA9ADC8);
        head.setTextSize(16);
        head.setGravity(Gravity.CENTER);
        head.setLetterSpacing(0.12f);
        TextView clock = new TextView(this);
        clock.setText(new java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(new java.util.Date()));
        clock.setTextColor(Color.WHITE);
        clock.setTextSize(64);
        clock.setTypeface(Typeface.create("sans-serif-light", Typeface.NORMAL));
        clock.setGravity(Gravity.CENTER);
        TextView text = new TextView(this);
        text.setText(title == null ? "" : title);
        text.setTextColor(0xFFF2F3FA);
        text.setTextSize(26);
        text.setGravity(Gravity.CENTER);
        text.setPadding(0, dp(18), 0, dp(40));
        // напоминание о деле — главная кнопка «Сделано ✓» (дело уходит в журнал «Дела»), «Понял» — просто закрыть
        boolean task = !"alarm".equals(kind) && !"timer".equals(kind);
        // лекарство («Для старших», 0.62: «Выпить: …», таблетки, капли) — «Выпил(а) ✓»: телефон отметит и не скажет близким
        boolean med = task && title != null && java.util.regex.Pattern.compile("^Выпить:|таблет|лекарств|капл[иею]|капсул|укол|инсулин|давлени|сироп|витамин",
                java.util.regex.Pattern.CASE_INSENSITIVE | java.util.regex.Pattern.UNICODE_CASE).matcher(title).find();
        Button made = task ? button(med ? "Выпил(а) ✓" : "Сделано ✓", 0xFF2FB67E, 0xFF1F8F86) : null;
        Button ok = task ? button("Понял", 0x22FFFFFF, 0x22FFFFFF) : button("Понял", 0xFF667EEA, 0xFF764BA2);
        Button snooze = button("Отложить на 10 минут", 0x22FFFFFF, 0x22FFFFFF);
        final String note = AlarmReceiver.noteFor(this, id);
        Button look = note.isEmpty() ? null : button("Посмотреть вложения", 0xFF5B6CFF, 0xFF8A5BFF);
        if (look != null) look.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { openNote(note); } });
        if (made != null) made.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { AlarmReceiver.made(AlarmActivity.this, id, title); done(); } });
        ok.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { done(); } });
        snooze.setOnClickListener(new View.OnClickListener() { @Override public void onClick(View v) { snooze(); } });
        root.addView(head);
        root.addView(clock);
        root.addView(text);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(58));
        lp.bottomMargin = dp(12);
        if (look != null) root.addView(look, lp);
        if (made != null) root.addView(made, lp);
        root.addView(ok, lp);
        root.addView(snooze, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(58)));
        setContentView(root);
        start();
        h.postDelayed(new Runnable() { @Override public void run() { stopSound(); } }, 120000);   // не звонить бесконечно, если человека нет рядом
    }

    private Button button(String t, int c1, int c2) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        b.setTextColor(Color.WHITE);
        b.setTextSize(17);
        GradientDrawable d = new GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, new int[]{c1, c2});
        d.setCornerRadius(dp(18));
        b.setBackground(d);
        return b;
    }

    private int dp(int v) { return (int) (v * getResources().getDisplayMetrics().density + 0.5f); }

    /** Сначала несколько секунд звучит само уведомление (оно же уходит на часы: Honor/Huawei Health пересылают только
     *  уведомление, которое живёт в шторке, а не снятое через долю секунды), потом окно берёт звук на себя — по кругу и
     *  нарастая, а уведомление тихо обновляется (не снимается: на часах остаётся с кнопками). Открыли окно позже
     *  (нажали уведомление) — звук сразу. */
    private void start() {
        long fired = getIntent().getLongExtra("fired", 0);
        long wait = fired > 0 ? Math.max(0, SOUND_DELAY_MS - (System.currentTimeMillis() - fired)) : 0;
        try {
            vib = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
            if (vib != null) vib.vibrate(new long[]{0, 400, 900, 400, 2400}, 0);   // два мягких толчка и пауза, по кругу
        } catch (Throwable ignored) { }
        h.postDelayed(new Runnable() { @Override public void run() { if (!isFinishing()) startSound(); } }, wait);
    }

    static final long SOUND_DELAY_MS = 4500;

    @SuppressWarnings("deprecation")
    private void startSound() {
        AlarmReceiver.quiet(this, id, title == null ? "" : title, kind == null ? "reminder" : kind,
                getIntent().getStringExtra("who") == null ? "" : getIntent().getStringExtra("who"));
        player = Sounds.play(this, Sounds.current(this), true, vol);
        if (player != null) {
            h.postDelayed(new Runnable() { @Override public void run() {       // мягко нарастает: не вскакивать от звонка
                if (player == null) return;
                vol = Math.min(1f, vol + 0.0375f);
                try { player.setVolume(vol, vol); } catch (Throwable ignored) { }
                if (vol < 1f) h.postDelayed(this, 1000);
            } }, 1000);
        } else try {
            android.net.Uri u = Sounds.uri(this, "system");
            ring = RingtoneManager.getRingtone(this, u);
            if (ring != null) {
                ring.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build());
                if (Build.VERSION.SDK_INT >= 28) {         // повтор мелодии — с Android 9, отражением (собираем против API 23)
                    try { Ringtone.class.getMethod("setLooping", boolean.class).invoke(ring, true); } catch (Throwable ignored) { }
                }
                ring.play();
            }
        } catch (Throwable ignored) { }
    }

    private void stopSound() {
        try { if (ring != null) ring.stop(); } catch (Throwable ignored) { }
        try { if (player != null) { player.stop(); player.release(); } } catch (Throwable ignored) { }
        player = null;
        try { if (vib != null) vib.cancel(); } catch (Throwable ignored) { }
    }

    private void done() {
        stopSound();
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(id.hashCode());
        finish();
    }

    /** «Посмотреть вложения»: звонок смолкает, приложение открывает заметку с фото и файлами (MainActivity → pro.dewiar.NOTE →
     *  app.js handleIntent → openNote). На заблокированном экране сначала просим снять блокировку. */
    private void openNote(final String note) {
        stopSound();
        ((NotificationManager) getSystemService(NOTIFICATION_SERVICE)).cancel(id.hashCode());
        final Intent i = new Intent(this, MainActivity.class).setAction("pro.dewiar.NOTE").putExtra("note", note)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        android.app.KeyguardManager km = (android.app.KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (Build.VERSION.SDK_INT >= 26 && km != null && km.isKeyguardLocked()) {
            try {                                       // API 26+, а собираем против 23 — отражением; без ответа: окно закроется в onStop
                Class<?> cb = Class.forName("android.app.KeyguardManager$KeyguardDismissCallback");
                android.app.KeyguardManager.class.getMethod("requestDismissKeyguard", Activity.class, cb).invoke(km, this, null);
            } catch (Throwable ignored) { }
        }
        leaving = true;
        startActivity(i);
    }

    private boolean leaving;                            // ушли смотреть вложения: приложение открылось поверх — окно больше не нужно

    @Override protected void onStop() { super.onStop(); if (leaving) finish(); }

    private void snooze() {
        snoozeLater(this, id, title, kind, getIntent().getStringExtra("who"));
        done();
    }

    /** «Отложить на 10 минут» — из окна и из кнопки уведомления (в том числе на часах). */
    static void snoozeLater(Context c, String id, String title, String kind, String who) {
        try {
            JSONObject x = new JSONObject().put("id", id + "-s" + (System.currentTimeMillis() / 1000)).put("title", title == null ? "Напоминание" : title)
                    .put("kind", kind == null ? "reminder" : kind).put("repeat", "").put("at", System.currentTimeMillis() + 10 * 60000L)
                    .put("who", who == null ? "" : who);
            String note = AlarmReceiver.noteFor(c, id);
            if (!note.isEmpty()) x.put("note", note);                        // отложенное — с теми же фото и файлами
            Alarms.put(c, x);
        } catch (Exception ignored) { }
    }

    // открытое окно — чтобы кнопка уведомления (с часов) могла его закрыть
    private static java.lang.ref.WeakReference<AlarmActivity> open = new java.lang.ref.WeakReference<>(null);

    static void closeIfOpen(final String id) {
        final AlarmActivity a = open.get();
        if (a != null && id.equals(a.id)) a.runOnUiThread(new Runnable() { @Override public void run() { a.stopSound(); a.finish(); } });
    }

    @Override protected void onResume() { super.onResume(); open = new java.lang.ref.WeakReference<>(this); }

    @Override protected void onDestroy() { stopSound(); h.removeCallbacksAndMessages(null); if (open.get() == this) open.clear(); super.onDestroy(); }
}
