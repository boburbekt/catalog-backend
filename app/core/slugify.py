"""Mahsulot/kategoriya nomidan URL-slug hosil qilish.

Lotin transliteratsiya (o‘zbek lotin + kirill), apostroflarni tozalash va
biznes ichida unikallashtirish. Bu modul DB'ga bog‘liq emas — chaqiruvchi tomon
band slug'lar to‘plamini uzatadi (cross-tenant emas, faqat shu biznes slug'lari).
"""

import re

# Kirill → lotin (o‘zbek/rus harflari). Ba'zi harflar bir nechta lotin belgiga o‘giriladi.
_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}

# Apostrof turlari: o‘ → o, g‘ → g bo‘lishi uchun ular oddiygina olib tashlanadi
# (‘ U+2018, ’ U+2019, ʻ U+02BB, ʼ U+02BC, ' ` ).
_APOSTROPHES = "'`‘’ʻʼ"

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Nomdan asosiy slug hosil qiladi (unikallik hisobga olinmaydi).

    Kichik harf → kirill lotinga → apostroflar olib tashlanadi → qolgan lotin bo‘lmagan
    belgilar defisga → chetdagi defislar qirqiladi. Bo‘sh natijada `"mahsulot"` qaytadi.
    """
    text = name.strip().lower()
    text = "".join(_CYRILLIC.get(ch, ch) for ch in text)
    text = "".join(ch for ch in text if ch not in _APOSTROPHES)
    text = _NON_SLUG.sub("-", text).strip("-")
    return text or "mahsulot"


def unique_slug(base: str, taken: set[str]) -> str:
    """`base` band bo‘lsa oxiriga `-2`, `-3` ... qo‘shib bo‘sh slug topadi.

    `taken` — shu biznes ichida allaqachon ishlatilgan slug'lar. Qaytarilgan slug
    `taken`ga qo‘shilmaydi; buni chaqiruvchi bajaradi.
    """
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"
