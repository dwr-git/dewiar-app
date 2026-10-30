"""Готовые детали для рисунков «Художника»: модель пишет <use href="#dw-balloon" x y width height color="#7C6CF2"/>,
плагин сам вставляет нужные <symbol> в рисунок. Основной цвет — currentColor (атрибут color у <use>), блики и тени —
белым и чёрным с прозрачностью, поэтому деталь хорошо смотрится в любой гамме. Слабой модели так проще нарисовать
красиво: композиция — её, а шарик, сердце или ёлка — уже аккуратные."""

PARTS = {
    "balloon": ('0 0 100 170', 'воздушный шар (с ниткой)',
                '<path d="M50 4C76 4 94 26 94 56c0 36-28 60-44 72C34 116 6 92 6 56 6 26 24 4 50 4z" fill="currentColor"/>'
                '<path d="M50 128l-7 9h14z" fill="currentColor"/>'
                '<ellipse cx="33" cy="38" rx="9" ry="17" fill="#fff" opacity=".35" transform="rotate(-18 33 38)"/>'
                '<path d="M50 137c-6 10 6 18 0 30" stroke="currentColor" stroke-width="2" fill="none" opacity=".8"/>'),
    "heart": ('0 0 100 92', 'сердце',
              '<path d="M50 88C20 66 4 50 4 30 4 15 16 4 30 4c9 0 16 5 20 12 4-7 11-12 20-12 14 0 26 11 26 26 0 20-16 36-46 58z" fill="currentColor"/>'
              '<ellipse cx="27" cy="26" rx="8" ry="12" fill="#fff" opacity=".35" transform="rotate(-35 27 26)"/>'),
    "star": ('0 0 100 96', 'звезда',
             '<path d="M50 4l13.5 28 30.5 4.3-22.2 21.4 5.4 30.3L50 73.6 22.8 88l5.4-30.3L6 36.3l30.5-4.3z" fill="currentColor" stroke="currentColor" stroke-width="4" stroke-linejoin="round"/>'
             '<path d="M50 4l13.5 28L50 50z" fill="#fff" opacity=".22"/>'),
    "sparkle": ('0 0 100 100', 'искорка (четырёхлучевая)',
                '<path d="M50 0C54 34 66 46 100 50 66 54 54 66 50 100 46 66 34 54 0 50 34 46 46 34 50 0z" fill="currentColor"/>'),
    "snowflake": ('0 0 100 100', 'снежинка',
                  '<g stroke="currentColor" stroke-width="5" stroke-linecap="round" fill="none">'
                  + "".join(f'<g transform="rotate({a} 50 50)"><path d="M50 8v84"/><path d="M50 22l-9-9M50 22l9-9M50 78l-9 9M50 78l9 9"/></g>' for a in (0, 60, 120))
                  + '</g>'),
    "flower": ('0 0 100 100', 'цветок (сердцевина жёлтая)',
               "".join(f'<ellipse cx="50" cy="24" rx="16" ry="24" fill="currentColor" transform="rotate({a} 50 50)"/>' for a in range(0, 360, 72))
               + "".join(f'<ellipse cx="50" cy="28" rx="6" ry="14" fill="#fff" opacity=".22" transform="rotate({a} 50 50)"/>' for a in range(0, 360, 72))
               + '<circle cx="50" cy="50" r="13" fill="#FFC94D"/><circle cx="46" cy="46" r="4" fill="#fff" opacity=".5"/>'),
    "leaf": ('0 0 100 100', 'лист',
             '<path d="M10 90C10 40 40 10 92 8c-2 52-32 82-82 82z" fill="currentColor"/>'
             '<path d="M14 86C34 62 56 40 84 16" stroke="#fff" stroke-width="3" fill="none" opacity=".45" stroke-linecap="round"/>'
             '<path d="M10 90L4 96" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>'),
    "tree": ('0 0 100 130', 'ёлка',
             '<path d="M50 4L22 44h12L14 72h14L4 104h92L72 72h14L66 44h12z" fill="currentColor" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>'
             '<path d="M50 4L22 44h12L14 72h14L4 104h46z" fill="#000" opacity=".1"/>'
             '<rect x="42" y="104" width="16" height="22" rx="3" fill="#7A4A2A"/>'),
    "gift": ('0 0 100 100', 'подарок с бантом',
             '<rect x="8" y="40" width="84" height="56" rx="6" fill="currentColor"/><rect x="4" y="28" width="92" height="18" rx="5" fill="currentColor"/>'
             '<rect x="4" y="38" width="92" height="8" fill="#000" opacity=".12"/>'
             '<rect x="43" y="28" width="14" height="68" fill="#fff" opacity=".88"/>'
             '<path d="M50 28C38 6 14 4 16 18c2 10 20 10 34 10zM50 28C62 6 86 4 84 18c-2 10-20 10-34 10z" fill="#fff" opacity=".92"/>'
             '<path d="M50 28C40 14 26 12 24 18M50 28C60 14 74 12 76 18" stroke="#000" stroke-opacity=".12" stroke-width="2" fill="none"/>'
             '<circle cx="50" cy="28" r="6" fill="#fff"/>'),
    "sun": ('0 0 100 100', 'солнце с лучами',
            '<g stroke="currentColor" stroke-width="6" stroke-linecap="round">'
            + "".join(f'<path d="M50 6v12" transform="rotate({a} 50 50)"/>' for a in range(0, 360, 45)) + '</g>'
            '<circle cx="50" cy="50" r="24" fill="currentColor"/><circle cx="43" cy="43" r="8" fill="#fff" opacity=".35"/>'),
    "moon": ('0 0 100 100', 'месяц',
             '<path d="M64 8A44 44 0 1 0 92 70 36 36 0 1 1 64 8z" fill="currentColor"/>'
             '<circle cx="40" cy="60" r="5" fill="#000" opacity=".08"/><circle cx="30" cy="40" r="3" fill="#000" opacity=".08"/>'),
    "cloud": ('0 0 120 70', 'облако',
              '<path d="M28 66C14 66 4 57 4 45c0-11 9-20 20-20 3-13 15-22 29-22 15 0 27 10 30 24 2-1 5-1 7-1 13 0 24 10 24 22s-10 18-24 18z" fill="currentColor"/>'
              '<path d="M24 46c0-9 7-15 15-15" stroke="#fff" stroke-width="4" fill="none" opacity=".45" stroke-linecap="round"/>'),
    "mountain": ('0 0 160 100', 'горы со снежными вершинами',
                 '<path d="M0 100L52 22 78 58 104 30 160 100z" fill="currentColor"/>'
                 '<path d="M52 22L40 40l8-3 6 6 7-5zM104 30l-11 13 7-2 5 5 6-4z" fill="#fff" opacity=".9"/>'
                 '<path d="M52 22L0 100h40z" fill="#000" opacity=".12"/>'),
    "cup": ('0 0 100 100', 'чашка с паром',
            '<path d="M14 40h60v26c0 16-13 28-30 28S14 82 14 66z" fill="currentColor"/>'
            '<path d="M74 48h6c8 0 12 5 12 11s-5 12-13 12h-7" stroke="currentColor" stroke-width="7" fill="none"/>'
            '<ellipse cx="44" cy="40" rx="30" ry="6" fill="#000" opacity=".18"/>'
            '<g stroke="currentColor" stroke-width="4" fill="none" stroke-linecap="round" opacity=".55">'
            '<path d="M32 30c-6-6 6-10 0-18"/><path d="M46 30c-6-6 6-10 0-18"/><path d="M60 30c-6-6 6-10 0-18"/></g>'),
    "candle": ('0 0 40 120', 'свеча с огоньком',
               '<rect x="10" y="44" width="20" height="74" rx="5" fill="currentColor"/><rect x="10" y="44" width="6" height="74" rx="3" fill="#fff" opacity=".3"/>'
               '<ellipse cx="20" cy="22" rx="12" ry="18" fill="#FFD36E" opacity=".45"/>'
               '<path d="M20 6c9 12 8 24 0 30-8-6-9-18 0-30z" fill="#FF8A3D"/><path d="M20 18c4 6 4 12 0 15-4-3-4-9 0-15z" fill="#FFE08A"/>'),
    "confetti": ('0 0 200 120', 'конфетти (разноцветные)',
                 "".join(f'<rect x="{x}" y="{y}" width="9" height="16" rx="2" fill="{c}" transform="rotate({r} {x} {y})"/>'
                         for x, y, c, r in ((12, 20, "#7C6CF2", 20), (50, 70, "#3CC6B4", -30), (88, 14, "#FFB547", 40), (120, 84, "#E9567B", -15),
                                            (160, 30, "#7C6CF2", 35), (186, 90, "#FFB547", -40), (30, 104, "#E9567B", 25), (140, 6, "#3CC6B4", 10)))
                 + '<circle cx="70" cy="40" r="5" fill="#E9567B"/><circle cx="104" cy="52" r="4" fill="#7C6CF2"/><circle cx="176" cy="62" r="5" fill="#3CC6B4"/>'),
    "house": ('0 0 100 100', 'домик с окном',
              '<path d="M10 46L50 10l40 36v48H10z" fill="currentColor"/><path d="M4 50L50 8l46 42" stroke="#000" stroke-opacity=".25" stroke-width="7" fill="none" stroke-linejoin="round"/>'
              '<rect x="22" y="56" width="22" height="20" rx="3" fill="#FFD27A"/><rect x="58" y="60" width="18" height="34" rx="3" fill="#000" opacity=".25"/>'),
    "ribbon": ('0 0 300 80', 'лента-плашка для надписи (текст пишите поверх)',
               '<path d="M0 18h34v54H0l14-27z" fill="currentColor"/><path d="M300 18h-34v54h34l-14-27z" fill="currentColor"/>'
               '<path d="M22 72l12-10v10zM278 72l-12-10v10z" fill="#000" opacity=".3"/>'
               '<rect x="22" y="8" width="256" height="54" rx="4" fill="currentColor"/><rect x="22" y="8" width="256" height="10" fill="#fff" opacity=".18"/>'),
}


def symbol(name):
    vb, _, body = PARTS[name]
    return f'<symbol id="dw-{name}" viewBox="{vb}" overflow="visible">{body}</symbol>'


def catalog():
    return ", ".join(f"dw-{k} — {v[1]}" for k, v in PARTS.items())
