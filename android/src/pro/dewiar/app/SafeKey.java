package pro.dewiar.app;

import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyPermanentlyInvalidatedException;
import android.security.keystore.KeyProperties;
import android.security.keystore.UserNotAuthenticatedException;
import android.util.Base64;

import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Сейф — открыть отпечатком, лицом или PIN телефона (идея №224, 15 голосов: «мастер-пароль из 15 символов на каждом входе
 *  на телефоне вводить невозможно»). Ключ сейфа (тот, что получается из мастер-пароля, — не сам пароль) лежит в настройках
 *  приложения шифром AES-GCM; ключ шифра — в хранилище ключей Android (AndroidKeyStore, из телефона не достать) и работает
 *  только 30 секунд после того, как человек подтвердил себя экраном блокировки системы (отпечаток, лицо, PIN — что включено в
 *  телефоне). Сменили отпечатки или сняли блокировку экрана — Android сам делает ключ негодным: снова мастер-пароль.
 *  Без подтверждения — исключение UserNotAuthenticated: показываем системный экран и повторяем то же действие. Ответ в
 *  интерфейс — событием safebio {op: save|open, ok, key?, error?}. API 23 без библиотек (сборка — против android.jar 23). */
final class SafeKey {
    static final int REQ = 7321;
    private static final String ALIAS = "dewiar_safe_bio", PREFS = "safebio";
    private static String pendingOp = null, pendingKey = null;

    private SafeKey() { }

    /** none — нет блокировки экрана (или Android старше 6): отпечатком не открыть; off — не включено; on — включено. */
    static String state(Context c) {
        if (Build.VERSION.SDK_INT < 23) return "none";
        KeyguardManager km = (KeyguardManager) c.getSystemService(Context.KEYGUARD_SERVICE);
        if (km == null || !km.isKeyguardSecure()) return "none";
        return prefs(c).getString("ct", "").isEmpty() ? "off" : "on";
    }

    static void forget(Context c) {
        prefs(c).edit().clear().apply();
        try { KeyStore ks = KeyStore.getInstance("AndroidKeyStore"); ks.load(null); ks.deleteEntry(ALIAS); } catch (Exception ignored) { }
    }

    /** Сохранить ключ сейфа (base64) под защитой экрана блокировки. */
    static void save(MainActivity a, String keyB64) { run(a, "save", keyB64, true); }

    /** Достать ключ сейфа: событие safebio {op: open, ok, key}. */
    static void open(MainActivity a) { run(a, "open", null, true); }

    /** Системный экран подтверждения закрыли: подтвердили — повторяем действие, нет — так и говорим. */
    static void onResult(MainActivity a, boolean ok) {
        String op = pendingOp, k = pendingKey;
        pendingOp = null; pendingKey = null;
        if (op == null) return;
        if (!ok) { reply(a, op, false, null, "cancel"); return; }
        run(a, op, k, false);
    }

    private static void run(MainActivity a, String op, String keyB64, boolean mayAsk) {
        try {
            if ("save".equals(op)) {
                Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
                ci.init(Cipher.ENCRYPT_MODE, key(mayAsk));         // повтор после подтверждения — тот же ключ, не новый
                byte[] ct = ci.doFinal(Base64.decode(keyB64, Base64.NO_WRAP));
                prefs(a).edit().putString("iv", Base64.encodeToString(ci.getIV(), Base64.NO_WRAP))
                        .putString("ct", Base64.encodeToString(ct, Base64.NO_WRAP)).apply();
                reply(a, op, true, null, null);
            } else {
                SharedPreferences p = prefs(a);
                if (p.getString("ct", "").isEmpty()) { reply(a, op, false, null, "off"); return; }
                Cipher ci = Cipher.getInstance("AES/GCM/NoPadding");
                ci.init(Cipher.DECRYPT_MODE, key(false), new GCMParameterSpec(128, Base64.decode(p.getString("iv", ""), Base64.NO_WRAP)));
                byte[] k = ci.doFinal(Base64.decode(p.getString("ct", ""), Base64.NO_WRAP));
                reply(a, op, true, Base64.encodeToString(k, Base64.NO_WRAP), null);
                java.util.Arrays.fill(k, (byte) 0);
            }
        } catch (UserNotAuthenticatedException e) {
            if (!mayAsk) { reply(a, op, false, null, "auth"); return; }
            KeyguardManager km = (KeyguardManager) a.getSystemService(Context.KEYGUARD_SERVICE);
            Intent i = km == null ? null : km.createConfirmDeviceCredentialIntent("Сейф Dewiar",
                    "save".equals(op) ? "Подтвердите, что это вы: дальше сейф будет открываться так же" : "Подтвердите, что это вы");
            if (i == null) { reply(a, op, false, null, "none"); return; }
            pendingOp = op; pendingKey = keyB64;
            a.startActivityForResult(i, REQ);
        } catch (KeyPermanentlyInvalidatedException e) {
            forget(a);                                      // сменили отпечатки или блокировку — только мастер-паролем
            reply(a, op, false, null, "changed");
        } catch (Exception e) {
            reply(a, op, false, null, String.valueOf(e.getMessage()));
        }
    }

    private static SecretKey key(boolean create) throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(ALIAS)) {
            if (!create) return (SecretKey) ks.getKey(ALIAS, null);
            ks.deleteEntry(ALIAS);                          // включают заново — новый ключ (старый мог стать негодным)
        } else if (!create) throw new IllegalStateException("off");
        KeyGenerator g = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        g.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setUserAuthenticationRequired(true).setUserAuthenticationValidityDurationSeconds(30).build());
        return g.generateKey();
    }

    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE); }

    private static void reply(MainActivity a, String op, boolean ok, String key, String err) {
        try {
            org.json.JSONObject o = new org.json.JSONObject().put("op", op).put("ok", ok);
            if (key != null) o.put("key", key);
            if (err != null) o.put("error", err);
            a.event("safebio", o);
        } catch (Exception ignored) { }
    }
}
