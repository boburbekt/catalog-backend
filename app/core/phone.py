import re


class InvalidPhoneError(ValueError):
    """Telefon raqamini E.164 ga keltirib bo‘lmadi."""


_DIGITS = re.compile(r"\D")


def normalize_phone(raw: str) -> str:
    """Turli formatdagi raqamni E.164 (`+998901234567`) ko‘rinishiga keltiradi.

    Qoidalar:
      * 9 xonali lokal raqam (`90 123 45 67`) → `+998` qo‘shiladi;
      * `998...` bilan boshlangan raqam → faqat `+` qo‘shiladi;
      * boshqa xalqaro raqam (7–15 raqam) → `+` bilan E.164;
      * bo‘sh yoki chegaradan tashqari uzunlik → `InvalidPhoneError`.

    Ajratuvchilar (bo‘sh joy, `-`, `()`, boshidagi `+`) e'tiborsiz qoldiriladi.
    """
    if raw is None:
        raise InvalidPhoneError("Telefon raqami majburiy")

    digits = _DIGITS.sub("", raw)
    if not digits:
        raise InvalidPhoneError("Telefon raqami noto‘g‘ri")

    if len(digits) == 9:
        # O‘zbek lokal mobil raqami — mamlakat kodini oldiga qo‘yamiz.
        normalized = "998" + digits
    else:
        # `998...` bo‘lsa ham, boshqa xalqaro raqam bo‘lsa ham — raqamlarning o‘zi E.164 tanasi.
        normalized = digits

    # E.164: mamlakat kodi bilan birga 7–15 raqam.
    if not 7 <= len(normalized) <= 15:
        raise InvalidPhoneError("Telefon raqami noto‘g‘ri")

    return "+" + normalized
