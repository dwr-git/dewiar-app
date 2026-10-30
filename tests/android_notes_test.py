"""Заметки на телефоне — надёжно (отзыв 11.10: «Записала», а заметки нет; фото к заметке не прикрепить):
«запиши в заметки …» записывается сразу, без модели; голое «Записала.» без save_note ловится; фото из чата с просьбой
записать — в заметке; заметка открывается: правка, фото, файл, удаление вместе с вложениями; «Новая заметка»; новые
сверху; синхронизация не теряет вложения."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
png = tmp / "чек.png"
from PIL import Image  # noqa: E402
Image.new("RGB", (64, 48), (200, 80, 120)).save(png)
doc = tmp / "договор.pdf"; doc.write_bytes(b"%PDF-1.4 test")
PIX = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: d.accept())
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    r = pg.evaluate("""async () => { fileSave('notes.json', '[]'); await ask('Лира, запиши в заметки настроенный умный дом с компьютера не синхронизируется с телефоном');
      await new Promise(r => setTimeout(r, 200)); return [notes().map(x => [x.title, x.text]), document.querySelector('#bot').textContent]; }""")
    ok(len(r[0]) == 1 and r[0][0][1].startswith("Настроенный умный дом") and r[1].strip() == "Записала в заметки.", f"«запиши в заметки …» — сразу и без модели; вслух — без оборванного пересказа: {r}")
    r = pg.evaluate("() => [noteQuick('что у меня в заметках'), noteQuick('запиши расход 450'), noteQuick('заметка: позвонить Ольге в пять'), notes().length, notes().slice(-1)[0].text]")
    ok(r[0] == "" and r[1] == "" and r[2] == "Записала в заметки." and r[3] == 2 and r[4].startswith("Позвонить Ольге"), f"вопрос о заметках и расход — не заметка; «заметка: …» — заметка: {r}")
    r = pg.evaluate("""() => [!!claimedAction('Записала.', new Set(), 'запиши это в заметки'), !!claimedAction('Записала.', new Set(['save_note']), 'запиши в заметки'),
      (claimedAction('Записала.', new Set(), 'запиши расход 450 на продукты') || {}).tool]""")
    # расход — не заметка; «Записала.» без money_add на расход ловится уже как трата (№405, 29.10)
    ok(r == [True, False, "money_add"], f"«Записала.» без save_note после просьбы о заметке — ловится как заметка, на расход — как трата: {r}")
    # фото из чата с просьбой записать
    r = pg.evaluate(f"""async () => {{ await ask('Сохрани в заметки чек из магазина', {{ attach: [{{ kind: 'image', name: 'чек.jpg', url: '{PIX}' }}] }});
      await new Promise(r => setTimeout(r, 200)); const x = notes().find(n => /чек/i.test(n.title));
      return [x && (x.att || []).length, x && fileGet('natt-' + x.att[0].id).slice(0, 15), document.querySelector('#bot').textContent]; }}""")
    ok(r[0] == 1 and r[1] == "data:image/png;" and "вместе с фото" in r[2], f"фото из чата с «сохрани в заметки» — в заметке: {r}")
    # фото прикреплено в поле ввода, а просьба — голосом (отзыв 11.10: фото осталось висеть над полем)
    r = pg.evaluate(f"""async () => {{ attached = [{{ kind: 'image', name: 'скриншот.png', url: '{PIX}' }}]; renderAtts();
      sttActive = true; N.ev({{ type: 'stt_result', text: 'Сохрани заметку сканер не открывается' }});
      await new Promise(r => setTimeout(r, 300)); const x = notes().find(n => /сканер/i.test(n.text));
      return [x && (x.att || []).length, attached.length, document.querySelectorAll('#atts .at').length, document.querySelector('#bot').textContent]; }}""")
    ok(r[:3] == [1, 0, 0] and "вместе с фото" in r[3], f"фото из поля ввода + просьба голосом — фото в заметке, поле очищено: {r}")
    r = pg.evaluate(f"""async () => {{ turnAtt = [{{ kind: 'image', name: 'доска.jpg', url: '{PIX}' }}]; const t = await runTool('save_note', {{ title: 'Доска', text: 'схема' }});
      return [t, (notes().find(n => n.title === 'Доска').att || []).length]; }}""")
    ok("вложений: 1" in r[0] and r[1] == 1, f"модель записала заметку — фото этого хода с ней: {r}")
    # «Лира, открой сканер» — сразу сканер (имя не мешает); «Открыла сканер» без scan_code — ловится (заметка 11.10)
    r = pg.evaluate("""async () => { let opened = 0; const s0 = scanCode; scanCode = () => { opened++; };
      const a = await quick('Лира, открой сканер'), b = await quick('лира открой сканер'); await new Promise(r => setTimeout(r, 400)); scanCode = s0;
      return [a && a.say, b && b.say, opened, !!claimedAction('Открыла сканер, наведи камеру.', new Set(), 'сканер'), !!claimedAction('Открыла сканер.', new Set(['scan_code']), 'сканер')]; }""")
    ok(r == ["Наведите камеру на код.", "Наведите камеру на код.", 2, True, False], f"«Лира, открой сканер» — сканер открывается; «открыла» без открытия — ловится: {r}")
    # «стоп» ослышан («Вы: Ctop.» → «Хорошо, я слушаю.», отзыв 11.10) — всё равно стоп, без модели; «стол» — нет
    r = pg.evaluate("""async () => { const out = [];
      for (const t of ['Ctop.', 'Сстоп!', 'Стоб', 'Паузу.', 'Pauza', 'Лира, Ctop', 'ну всё, хватить']) { const q = await quick(t); out.push(q && q.say); }
      return [out, ['Стол', 'Стопа болит', 'Топ', 'сто'].map(stopPhrase)]; }""")
    ok(r[0] == ["Хорошо."] * 7 and r[1] == [None] * 4, f"телефон: ослышанное «стоп/пауза» — стоп без модели, похожие слова — нет: {r}")
    # «покажи заметки» — открывает заметки; поиск «заметки», «все» — последние, а не «заметок нет» (отзыв 11.10)
    r = pg.evaluate("""async () => { const a = await quick('Покажи заметки'), b = await quick('Лира, что у меня в заметках');
      await new Promise(r => setTimeout(r, 400)); const open = document.querySelector('#sh-day').classList.contains('on') && dayTab === 'notes';
      closeSheets(); const t1 = await runTool('find_notes', { query: 'заметки' }), t2 = await runTool('find_notes', { query: '' }), t3 = await runTool('find_notes', { query: 'Ольге' }),
      t4 = await runTool('find_notes', { query: 'квантовый телепорт' });
      return [a && a.say, b && b.say, open, t1.includes('Последние'), t2.includes('Всего заметок'), t3.includes('Позвонить Ольге') && !t3.includes('Всего'), t4.startsWith('По этим словам')]; }""")
    ok(r[0].startswith("Вот ваши заметки") and r[1].startswith("Вот ваши заметки") and r[2:] == [True, True, True, True, True],
       f"«покажи заметки» — открыты; find_notes с «заметки»/пусто — последние, по словам — найденные: {r}")
    # лист заметок: новые сверху, миниатюра, открыть и поправить
    pg.evaluate("() => { renderDay && openSheet('#sh-day'); dayTab = 'notes'; renderDay(); }"); pg.wait_for_timeout(200)
    r = pg.evaluate("() => [[...document.querySelectorAll('#day-body .it.note b')].map(b => b.textContent).slice(0, 2), !!document.querySelector('#day-body .nthumb')]")
    ok(r[0][0].startswith("Доска") and r[1], f"новые сверху, у заметки с фото — миниатюра: {r}")
    pg.click("#day-body .it.note"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#sh-note').classList.contains('on') && !!document.querySelector('#note-body .ntimg img')"), "заметка открывается целиком, с фото")
    pg.click("#nt-edit"); pg.wait_for_timeout(200)                     # 27.10: открытая заметка — сначала чтение, «Править» — правка
    pg.set_input_files("#nt-file", str(doc)); pg.wait_for_timeout(400)
    pg.fill("#nt-text", "схема на доске — переделать"); pg.click("#nt-save"); pg.wait_for_timeout(200)
    r = pg.evaluate("() => { const x = notes().find(n => n.title === 'Доска'); return [x.text, x.att.map(a => [a.name, a.type])]; }")
    ok(r[0] == "схема на доске — переделать" and len(r[1]) == 2 and r[1][1][0] == "договор.pdf", f"правка текста и файл к заметке: {r}")
    # новая заметка с фото
    pg.evaluate("() => openNote('')"); pg.wait_for_timeout(300)
    pg.fill("#nt-title", "Ремонт"); pg.fill("#nt-text", "обои в спальню"); pg.set_input_files("#nt-photo", str(png)); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('#nt-title').value") == "Ремонт", "добавили фото — набранное не стёрлось")
    pg.click("#nt-save"); pg.wait_for_timeout(200)
    r = pg.evaluate("() => { const x = notes().find(n => n.title === 'Ремонт'); return x && [x.text, (x.att || []).length, fileGet('natt-' + x.att[0].id).slice(0, 11)]; }")
    ok(r == ["обои в спальню", 1, "data:image/"], f"«Новая заметка» с фото: {r}")
    r = pg.evaluate("""async () => { const a0 = D.alarms; D.alarms = () => JSON.stringify([{ id: 'r1', at: Date.now() + 3600e3, title: 'позвонить маме' }]);
      const a = await quick('Лира, какие у меня напоминания'), t = await runTool('list_reminders', {}); D.alarms = a0;
      await new Promise(r => setTimeout(r, 400)); const open = dayTab === 'rem'; closeSheets(); return [a && a.say, t.includes('позвонить маме'), open]; }""")
    ok(r[0].startswith("Напоминаний: 1.") and "позвонить маме" in r[0] and r[1] and r[2], f"«какие у меня напоминания» — сразу, без модели, и открыты: {r}")
    # удалить — только из открытой заметки, с вопросом; «Вернуть» возвращает и вложения
    r = pg.evaluate("""async () => { const x = notes().find(n => n.title === 'Доска'); const aid = x.att[0].id;
      const crosses = document.querySelectorAll('#day-body .it.note .x').length;
      noteDelete(x.id, true); const gone = !notes().some(n => n.id === x.id) && fileGet('natt-' + aid) === '';
      document.querySelector('#undo button').click(); const back = notes().find(n => n.id === x.id);
      return [crosses, gone, !!back, fileGet('natt-' + aid).slice(0, 11)]; }""")
    ok(r == [0, True, True, "data:image/"], f"удаление — с вопросом и «Вернуть» (вместе с фото); крестиков в списке нет: {r}")
    # синхронизация с компьютера не теряет вложения; удаление убирает файлы
    r = pg.evaluate("""() => { const x = notes().find(n => n.title === 'Ремонт'); syncApply({ kind: 'note', id: x.id, data: { title: 'Ремонт', text: 'обои и краска' }, updated: Date.now() });
      const y = notes().find(n => n.id === x.id); const aid = y.att[0].id; noteDelete(y.id, false); return [y.text, y.att.length, notes().some(n => n.id === x.id), fileGet('natt-' + aid)]; }""")
    ok(r == ["обои и краска", 1, False, ""], f"правка с компьютера сохраняет вложения; удаление — вместе с файлами: {r}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
