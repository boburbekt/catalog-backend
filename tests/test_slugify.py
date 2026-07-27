"""slugify util: transliteratsiya, tozalash va unikallashtirish unit testlari."""

from app.core.slugify import slugify, unique_slug


def test_oddiy_nom_kichik_harf_va_defis():
    assert slugify("Divan Milano") == "divan-milano"


def test_apostrof_olib_tashlanadi():
    # o‘ → o, g‘ → g (apostroflar tozalanadi, bo‘shliqqa aylanmaydi).
    assert slugify("O‘rindiq") == "orindiq"
    assert slugify("Yog‘och stol") == "yogoch-stol"


def test_maxsus_belgilar_defisga():
    assert slugify("Divan / Krovat (yangi)!") == "divan-krovat-yangi"


def test_kirill_lotinga_ogiriladi():
    assert slugify("Диван") == "divan"
    assert slugify("Стол №1") == "stol-1"


def test_chetdagi_defislar_qirqiladi():
    assert slugify("  --Divan--  ") == "divan"


def test_bosh_natija_zaxira_slug():
    assert slugify("!!!") == "mahsulot"
    assert slugify("   ") == "mahsulot"


def test_unique_slug_bosh_toplamda_ozgarmaydi():
    assert unique_slug("divan", set()) == "divan"


def test_unique_slug_band_bolsa_raqam_qoshadi():
    assert unique_slug("divan", {"divan"}) == "divan-2"
    assert unique_slug("divan", {"divan", "divan-2"}) == "divan-3"
