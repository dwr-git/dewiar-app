/* Эмоции в голосе (19.11) — тон фразы по её словам и настроению вопроса. То же, что core/tone.py на компьютере (менять
   вместе; проверка tone1119 сверяет обе на одних фразах). Телефон и веб-версия: голосу Dewiar — манера на фразу (instruct),
   всем голосам — чуть темп, лицу — window.DEWIAR_TONE. */
(function (root) {
  const W = "(?:^|[^а-яё])";              // без «взгляда назад» — старый Safari его не знает
  const INSTRUCT = {
    joy: "Speak with genuine joy, bright and smiling.",
    sympathy: "Speak softly and gently, with warm sympathy.",
    playful: "Speak playfully, with a light smile in the voice.",
    surprise: "Speak with lively, warm surprise.",
    calm: "Speak calmly and seriously, unhurried.",
  };
  const SPEED = { joy: 1.04, playful: 1.03, surprise: 1.03, sympathy: 0.94, calm: 0.96 };
  const rx = (s) => new RegExp(s, "i");
  const SAD = rx(W + "(?:умер|умерла|умерли|скончал|похорон|погиб|болею|заболел|болит|больно|плохо мне|мне плохо|грустн|тоскл|одинок|тяжело|устал[аи]?(?![а-яё])|депресс|плач|слёз|слез|расстав|бросил[аи]?(?![а-яё])|уволил|увольн|страшно|боюсь|тревож|переживаю|не спится|не могу уснуть|провалил|не получилось|потерял[аи]?(?![а-яё])|авари)");
  const JOY_Q = rx(W + "(?:ура(?![а-яё])|получилось|сдал[аи]?(?![а-яё])|выиграл|победил|родил|поженил|свадьб|повысили|взяли на работу|купил[аи]? (?:машину|квартиру|дом)|день рождения|юбилей|праздник|отпуск|наконец-то)");
  const JOY = rx(W + "(?:поздравляю|поздравля|ура(?![а-яё])|как здорово|это здорово|здорово!|вот это успех|браво|молодец|умница|как я рада|как я рад|я так рада|я так рад|рада за|рад за)");
  const SYM = rx(W + "(?:сочувствую|соболезн|мне (?:очень )?жаль|как (?:же )?(?:тяжело|грустно|обидно)|держитесь|берегите себя|понимаю, как|это непросто|вы не одн|обнимаю)");
  const PLAY = /(?:(?:^|[^а-яё])шутк|анекдот|хаха|ха-ха|😄|😂|😉|😁|(?:^|[^а-яё])хи-хи|забавн|смешн)/i;
  const SURP = rx(W + "(?:ого(?![а-яё])|ух ты|вот это да|неужели|не может быть|надо же|вот так новость)");
  const CALM = rx(W + "(?:осторожн|опасн|важно:|внимание|срочно|немедленно|обратитесь к врачу|вызовите скорую|не (?:стоит|советую|рекомендую)|будьте внимательн|предупрежда)");
  const low = (s) => String(s || "").toLowerCase().replace(/ё/g, "е");
  function moodOf(asked) {
    const t = low(String(asked || "").split("\n\nВложения:")[0].slice(0, 600));
    return SAD.test(t) ? "sad" : JOY_Q.test(t) ? "joy" : null;
  }
  function toneOf(sentence, mood) {
    const s = low(sentence);
    if (mood === "sad" || SYM.test(s)) return "sympathy";
    if (CALM.test(s)) return "calm";
    if (JOY.test(s) || (mood === "joy" && s.includes("!"))) return "joy";
    if (PLAY.test(s)) return "playful";
    if (SURP.test(s)) return "surprise";
    return null;
  }
  root.DewiarTone = { INSTRUCT, SPEED, moodOf, toneOf, speedOf: (t) => SPEED[t] || 1 };
})(typeof window !== "undefined" ? window : globalThis);
