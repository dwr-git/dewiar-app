"""№847 (17.11, Mac mini M4, macOS 27): «значок в строке меню не отражается, клик по Dewiar в Доке — никакой
реакции; до настроек — только голосом». Значок в Доке — у процесса интерфейса с делегатом pywebview: ни повторного
открытия, ни меню Дока. Теперь (macui.dock_hooks): клик в Доке — виджет в трее → показать, иначе — студия; правый
клик по значку в Доке — «Показать Dewiar», «Студия», «Закинуть идею», «Перезапустить ядро». Без Mac — на поддельном
Cocoa: какие методы добавлены делегату и что они делают."""
import os, sys, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "ui"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class Item:
    def __init__(self, t): self.t, self.tag, self.target = t, None, None
    def initWithTitle_action_keyEquivalent_(self, t, a, k): self.t = t; return self
    def setTarget_(self, x): self.target = x
    def setTag_(self, i): self.tag = i


class Menu:
    def __init__(self): self.items = []
    def init(self): return self
    def addItem_(self, x): self.items.append(x)
    def numberOfItems(self): return len(self.items)


AppKit = types.ModuleType("AppKit")
AppKit.NSMenu = types.SimpleNamespace(alloc=lambda: Menu())
AppKit.NSMenuItem = types.SimpleNamespace(alloc=lambda: Item(""))
added = {}
objc = types.ModuleType("objc")
objc.selector = lambda fn, selector=b"", signature=b"": (selector, fn)
objc.classAddMethods = lambda cls, sels: added.update(dict(sels))
cocoa = types.ModuleType("webview.platforms.cocoa")
cocoa.BrowserView = types.SimpleNamespace(AppDelegate=object)
sys.modules.update({"AppKit": AppKit, "objc": objc, "webview.platforms.cocoa": cocoa})
sys.modules.setdefault("webview", types.ModuleType("webview")); sys.modules.setdefault("webview.platforms", types.ModuleType("webview.platforms"))

import macui  # noqa: E402
calls = []
api = types.SimpleNamespace(in_tray=True, from_tray=lambda: calls.append("from_tray"), bring_back=lambda: calls.append("bring_back"),
                            open_settings=lambda *a: calls.append("studio"), show_capture=lambda: 0, to_tray=lambda: 0,
                            restart_core=lambda: 0, quit_all=lambda: 0)
items = [("Показать Dewiar", api.from_tray), ("Студия", lambda: api.open_settings()), ("Закинуть идею", api.show_capture),
         ("Убрать в трей", api.to_tray), (None, None), ("Перезапустить ядро", api.restart_core), (None, None), ("Выйти из Dewiar", api.quit_all)]
macui.STATUS[:] = ["item", "target", "menu"]
macui.dock_hooks(api, items)
ok(set(added) == {b"applicationShouldHandleReopen:hasVisibleWindows:", b"applicationDockMenu:"}, "делегату добавлены клик в Доке и меню Дока")
menu = added[b"applicationDockMenu:"](None, None)
ok([x.t for x in menu.items] == ["Показать Dewiar", "Студия", "Закинуть идею", "Перезапустить ядро"] and all(x.target == "target" for x in menu.items),
   "меню Дока — те же пункты, что у значка в строке меню (без «Выйти» и «Убрать в трей»)")
ok([x.tag for x in menu.items] == [0, 1, 2, 5], "номера пунктов — как в меню значка (одно действие на пункт)")
ok(added[b"applicationShouldHandleReopen:hasVisibleWindows:"](None, None, False) is False, "клик в Доке обрабатываем сами")
time.sleep(0.3)
ok(calls == ["from_tray", "bring_back"], f"виджет убран — клик в Доке его показывает: {calls}")
calls.clear(); api.in_tray = False
added[b"applicationShouldHandleReopen:hasVisibleWindows:"](None, None, True); time.sleep(0.3)
ok(calls == ["studio"], f"виджет виден — клик в Доке открывает студию: {calls}")
src = (ROOT / "ui/macui.py").read_text(encoding="utf-8")
ok("dock_hooks(api, items)" in src, "подключается вместе со значком в строке меню")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
