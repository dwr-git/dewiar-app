"""Проверки качества — кодом, а не на слово. Этот файл — единая точка входа: все прежние имена доступны как quality.<имя>,
а сами проверки разложены по смыслу (чистое ядро, 1.0.13 — docs/CORE_PLAN.md):
- quality_files — готовые файлы (пустые, оборванный HTML, битые JSON/CSV/Office/PDF/картинки, синтаксис Python, не UTF-8),
  подсказка по тексту ошибки скрипта, чтение файлов для сверки;
- quality_answer — ответ в разговоре: ложный отказ, «обещал, но не сделал», «сказала, что сделала, — а действия не было»,
  выдуманные числа и погода, стихи, что придержать до проверки (голос без пауз);
- quality_task — итог долгих задач: тупик LoopGuard, критик, проверка по существу (критерии), сверка ссылок и цифр
  с прочитанным, HTML в браузере, «посмотреть глазами», проверяющий с чистым контекстом;
- quality_lessons — уроки задач и поправки человека в разговоре («Память/Уроки задач.md», «Память/Уроки.md»).
Модули без состояния, кроме LoopGuard и файлов уроков. Тексты для модели (*_NUDGE, LOOP_*, CRITIC, VERIFY, REFLECT…) —
часть поведения.
"""
from quality_files import (  # noqa: F401,E402 — прежние имена quality.* на месте
    check_file, count_of, error_hint, file_text, HINTS, _html_problems, log, _nums, PIP_NAMES, quick_check, _range,
    SERVICE, summarize, TEXT_FILE_MAX, verify_outputs, zip_bomb, ZIP_MAX, ZIP_RATIO, _zread)
from quality_answer import (  # noqa: F401,E402 — прежние имена quality.* на месте
    _ACTION, _ACTION_ASK, action_claim, _ACTION_FUT, add_style_rule, _AGENDA_FREE, agenda_invented, agenda_missed,
    appt_ask, APPT_NOTE, APPT_TIME, APPT_WHAT, ask_places, _ASK_THINK, ask_url, _BARE_DONE, bare_done, _BRIEF_TODO,
    _BUDGET, _CALL_ASK, call_claim, _CALL_SAID, CALL_TOOLS, _CAP_RU, CHAT_ASK, CONFIRM_ECHO_RX, _CONFIRM_SAY,
    COUNCIL_ASK, council_missing, COUNCIL_NOTE, _DEG, DELIVERABLE, DIAGRAM_ASK, diagram_missing, _DO, _DOING,
    _DONE_ANY, DRAWN_TOOLS, _ending, _FACT, _FAIL_VERBS, failed_claim, failed_note, fake_call, FAKE_GIVEUP,
    _FAKE_HEAD, FAKE_NUDGE, _FAKE_WAIT, FEATURE_DENY, feature_deny, _FILLER, found_pics_claim, _FOUND_SAID, _GEN_PIC,
    _GENERIC, _HM, _HM_COLON, hold_sentence, hold_step, _HONEST_FAIL, HTML_DOC, INFO_TOOLS_ALL, INFO_TOOLS_Q,
    invented_numbers, system_invented, SYS_ASK, note_claim, plugin_offer_missed, habit_said, _LOOK_ONLY, looks_like_promise, looks_like_refusal, _MIN_SAID, _MONEY_ASK, money_claim,
    _MONEY_DONE, _MONEY_PLAN, _MONEY_VERB, _NET, NO_DEALS, NO_TOOLS_GIVEUP, no_tools_claim, _NOW, number_mismatch, _NUMW, _OFFER, OPEN_ASK,
    open_claim, OPEN_TOOLS, _OPENED, PAGE_ASK, page_html_in, _PLACE_IN_ASK, _place_root, PLUGIN_ASK, PLUGIN_EDIT_ASK,
    PLUGIN_NOTE, plugin_skipped, PLUGIN_TOOLS, poem_check, POEM_LINES, poem_lines, _POEM_MANY, _POEM_SING,
    _POEM_TITLE, PROMISE, PROMISE_GIVEUP, PROMISE_NOW, promise_nudge, _RATE, RATE_ASK, _READ_ASK, REFUSAL,
    REFUSAL_NUDGE, REMIND_CLAIM, remind_claim, _REMIND_DID, REMIND_NOT_SET, REMIND_TOOLS, reminder_missing, _rhymes,
    _SAVED, saved_claim, search_place_fix, self_fact, _SET_ASK, SHORT_DOING, SHOW_EMPTY, SITE_ASK, SITE_EDIT_ASK,
    SITE_NOTE, SITE_TOOLS, _SONG_LINE, SONGS_ASK, songs_count, _SOUND, _SPENT, strip_confirm_echo, _STYLE_DO,
    STYLE_PREFIX, style_rule, style_rules_line, _STYLE_WHAT, _TASK_CLAIM, task_claim, _TEACH, _TEACH_CMD, _TEACH_NOT,
    URL_RX, url_unread, _VOW, _WAIT, WATCH_ASK_RX, WATCH_NUDGE, WEATHER_ASK, weather_invented, _WEATHER_SAID, _WHERE,
    WRITING_ASK, writing_missing, WRITING_NOTE)
from quality_task import (  # noqa: F401,E402 — прежние имена quality.* на месте
    check_criteria, _claim_nums, claim_urls, CRIT_ALIAS, CRIT_CHECKS, crit_label, CRIT_MAX, criteria_note, CRITIC,
    critic, critic_note, _DATE_RX, _derived, _dm, _DM_RX, html_check, HTTP_RX, _inside, keep_facts, _LABEL_RX, LOOK,
    look_verdict, LOOP_DONE, LOOP_FINISH, LOOP_WARN, LoopGuard, _MULT, NET_NOISE, NO_NET_ARGS, norm_criteria,
    number_pool, parse_look, parse_verdict, pool_line, task_spent, unseen_urls, unsupported_numbers, _url_key,
    VERIFY, VERIFY_LOOK, verify_task)
from quality_lessons import (  # noqa: F401,E402 — прежние имена quality.* на месте
    _CORRECTION, digest, _err_hit, LEARN, learn_from_correction, LESSON_OK, lesson_status, LESSON_WEAK,
    lessons_block, LESSONS_FILE, LESSONS_MAX, LESSONS_META, lessons_meta, LESSONS_PROMPT_MAX, lessons_track,
    looks_like_correction, merge_lessons, norm_error, read_lessons, REFLECT, reflect, REFLECT_EVERY, REFLECT_MIN,
    _save_meta, save_trace, TALK_HEAD, talk_lessons_block, TALK_LESSONS_FILE, TALK_LESSONS_PROMPT_MAX, _words,
    write_lessons)
