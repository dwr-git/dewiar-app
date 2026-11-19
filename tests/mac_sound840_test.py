"""№840 (17.11, Mac mini, macOS 27): 1) «в «Звук и поведение» микрофон и динамики — только «Системные по умолчанию»»:
список устройств на Mac был пуст (его брали только на Windows, а Mac тоже слушает через PortAudio / CoreAudio);
2) «окно портит линия сверху с тремя кнопками» — строка заголовка студии теперь прозрачная, страница под ней."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "ui"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sd = types.ModuleType("sounddevice")
sd.query_devices = lambda *a: [{"name": "MacBook Pro Microphone", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
                               {"name": "Shure MV7", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
                               {"name": "Studio Display Speakers", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2}]
sd.default = types.SimpleNamespace(device=[0, 2]); sd._terminate = lambda: None; sd._initialize = lambda: None
sys.modules["sounddevice"] = sd
import audio_io  # noqa: E402
audio_io.MAC, audio_io.WIN = True, False
devs = audio_io.list_devices()
ok([d["name"] for d in devs if d["kind"] == "source"] == ["MacBook Pro Microphone", "Shure MV7"]
   and [d["name"] for d in devs if d["kind"] == "sink"] == ["Studio Display Speakers"],
   f"Mac: микрофоны и динамики видны в списке: {[d['name'] for d in devs]}")
ok(audio_io._sd_index("Shure MV7", "source") == 1, "выбранный внешний микрофон открывается по своему номеру")
mac = (ROOT / "ui/macui.py").read_text(encoding="utf-8")
ok("setTitlebarAppearsTransparent_(True)" in mac and "(1 << 15)" in mac and "seamless(win)" in mac,
   "студия на Mac: строка заголовка прозрачная, страница под ней")
ok("mac-seam" in mac and "html.mac-seam main" in (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8"),
   "страница даёт место светофору сверху")
# №879 (18.11, 1.0.32: «полоса всё ещё портит интерфейс»): native бывает обёрткой — окно берём у неё; без линии под
# строкой; страница — во всю высоту; результат — в журнал окна
import types as _ty  # noqa: E402
sys.path.insert(0, str(ROOT / "ui"))
_pt = _ty.ModuleType("PyObjCTools"); _ah = _ty.ModuleType("PyObjCTools.AppHelper"); _ah.callAfter = lambda fn: fn(); _pt.AppHelper = _ah
sys.modules.setdefault("PyObjCTools", _pt); sys.modules.setdefault("PyObjCTools.AppHelper", _ah)
import macui  # noqa: E402
_calls = []


class _NS:
    m = 15
    def setTitlebarAppearsTransparent_(self, v): _calls.append("transparent")
    def setTitleVisibility_(self, v): _calls.append("notitle")
    def styleMask(self): return self.m
    def setStyleMask_(self, v): self.m = v
    def setTitlebarSeparatorStyle_(self, v): _calls.append(("sep", v))
    def contentView(self): return _ty.SimpleNamespace(setFrameSize_=lambda x: _calls.append(("full", x)))
    def frame(self): return _ty.SimpleNamespace(size=_ty.SimpleNamespace(width=1200, height=800))


macui.seamless(_ty.SimpleNamespace(native=_ty.SimpleNamespace(window=_NS())))
ok("transparent" in _calls and ("sep", 1) in _calls and ("full", (1200, 800)) in _calls,
   f"№879: окно берётся и у обёртки pywebview; без линии; страница во всю высоту: {_calls}")
ok("win.events.loaded += lambda *a: (seamless(win)" in mac, "№879: ещё раз — когда страница загрузилась")
# №898 (19.11, macOS 27, 1.0.40: «полоса осталась», журнал — «прозрачная»): WKWebView сам отодвигал страницу под строку
# заголовка (automaticallyAdjustsContentInsets) — серую подложку окна было видно. Отступ снимаем у WebView окна
_wv_calls = []


class WKWebView:
    def _setAutomaticallyAdjustsContentInsets_(self, v): _wv_calls.append(("auto", v))
    def _setTopContentInset_(self, v): _wv_calls.append(("top", v))
    def subviews(self): return []


_calls.clear()
_ns = _NS(); _ns.contentView = lambda: _ty.SimpleNamespace(setFrameSize_=lambda x: None, subviews=lambda: [WKWebView()])
macui.seamless(_ty.SimpleNamespace(native=_ty.SimpleNamespace(window=_ns)))
ok(("auto", False) in _wv_calls and ("top", 0.0) in _wv_calls, f"№898: WebView не отодвигает страницу под строку заголовка: {_wv_calls}")
_wv_calls.clear()
ok(macui._no_insets(_ty.SimpleNamespace(native=_ty.SimpleNamespace(webview=WKWebView())), None) == 1 and _wv_calls,
   "№898: WebView pywebview (native.webview) — тоже")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
