package pro.dewiar.app;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.File;
import java.io.FileInputStream;
import java.io.ByteArrayOutputStream;

/** Окно для чужого HTML: мини-программы, которые написала модель («Сделанное»), и страницы-результаты задач.
 *  Свой WebView БЕЗ моста Dewiar: addJavascriptInterface попадает во все фреймы страницы, в том числе в iframe sandbox,
 *  поэтому показывать такой код в главном окне нельзя — он дотянулся бы до настроек, ключей и телефона.
 *  Здесь: нет моста, нет доступа к файлам, ссылки уходят во внешний браузер. HTML приходит файлом в кэше (Bridge.viewHtml),
 *  «В «Загрузки»» закрывает окно с ответом save — сохраняет уже приложение (MainActivity → событие htmlview). */
public class HtmlView extends Activity {
    static final int REQ = 7311;
    private WebView web;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        String path = getIntent().getStringExtra("path"), title = getIntent().getStringExtra("title");
        String html = read(path);
        if (html == null) { finish(); return; }
        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#101018"));
        w.setNavigationBarColor(Color.parseColor("#101018"));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.parseColor("#101018"));
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(dp(16), dp(8), dp(6), dp(8));
        TextView t = new TextView(this);
        t.setText(title == null ? "" : title);
        t.setTextColor(Color.WHITE);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setSingleLine(true);
        t.setEllipsize(android.text.TextUtils.TruncateAt.END);
        bar.addView(t, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
        bar.addView(button("В «Загрузки»", new View.OnClickListener() { @Override public void onClick(View v) { done(true); } }));
        bar.addView(button("✕", new View.OnClickListener() { @Override public void onClick(View v) { done(false); } }));
        root.addView(bar, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setTextZoom(100);
        web.setWebViewClient(new WebViewClient() {
            @SuppressWarnings("deprecation")
            @Override public boolean shouldOverrideUrlLoading(WebView v, String url) {
                Uri u = Uri.parse(url);
                String sc = u.getScheme() == null ? "" : u.getScheme();
                if (sc.equals("http") || sc.equals("https") || sc.equals("mailto") || sc.equals("tel")) Phone.openUrl(HtmlView.this, url);
                return true;                                         // само окно никуда не уходит
            }
        });
        root.addView(web, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
        Compat.edgeInsets(root);
        web.loadDataWithBaseURL("https://view.dewiar.invalid/", html, "text/html", "utf-8", null);
    }

    private TextView button(String label, View.OnClickListener l) {
        TextView x = new TextView(this);
        x.setText(label);
        x.setTextColor(Color.parseColor("#C9C9F5"));
        x.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        x.setPadding(dp(12), dp(10), dp(12), dp(10));
        x.setOnClickListener(l);
        return x;
    }

    private void done(boolean save) {
        setResult(save ? RESULT_OK : RESULT_CANCELED, new Intent().putExtra("save", save));
        finish();
    }

    @Override protected void onDestroy() {
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }

    private static String read(String path) {
        if (path == null) return null;
        try (FileInputStream in = new FileInputStream(new File(path))) {
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            byte[] buf = new byte[65536]; int n;
            while ((n = in.read(buf)) > 0) o.write(buf, 0, n);
            return o.toString("UTF-8");
        } catch (Exception e) { return null; }
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
