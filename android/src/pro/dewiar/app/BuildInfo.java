package pro.dewiar.app;

/** Версия приложения — единственное место, где она записана. tools/build_apk.sh берёт её отсюда (versionName и
 *  versionCode = мажор·10000 + минор·100 + патч — каждая часть меньше 100); её же видят отчёт о падении (App.java),
 *  User-Agent запросов (Net.java) и интерфейс через Dewiar.info() (Bridge.java). */
public final class BuildInfo {
    public static final String VERSION = "0.7.1";
    private BuildInfo() { }
}
