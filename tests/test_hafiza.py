from oneri.excel import onerileri_oku
from oneri.hafiza import Hafiza, VektorOnbellegi, ilk_cumle, ornek_alinabilir_mi, ozgun_satirlar

from yardimci import sahte_gomucu


def _denizli_ornekleri(ornek_excel):
    return [
        o
        for o in onerileri_oku(ornek_excel, "Genel Tablo")
        if o.fabrika == "Denizli" and ornek_alinabilir_mi(o, 40)
    ]


class SayanGomucu:
    def __init__(self):
        self.metin_sayisi = 0

    def __call__(self, metinler):
        self.metin_sayisi += len(metinler)
        return sahte_gomucu(metinler)


def test_test_kayitlari_ve_bekleyenler_ornek_alinmaz(ornek_excel):
    assert [o.satir for o in _denizli_ornekleri(ornek_excel)] == [2, 3, 4, 6, 7]


def test_ilk_cumle():
    assert ilk_cumle("Birinci cümle. İkinci cümle.") == "Birinci cümle."
    assert ilk_cumle("Noktasız metin") == "Noktasız metin"


def test_ilk_cumlesi_tekrar_eden_metinler_kalip_sayilir(ornek_excel):
    ornekler = _denizli_ornekleri(ornek_excel)
    assert ozgun_satirlar(ornekler, kalip_tekrar_esigi=3) == {6, 7}
    assert ozgun_satirlar(ornekler, kalip_tekrar_esigi=4) == {2, 3, 4, 6, 7}


def test_en_benzer_oneriyi_bulur(ornek_excel, tmp_path):
    onbellek = VektorOnbellegi(tmp_path / "hafiza.db", "bge-m3", sahte_gomucu)
    hafiza = Hafiza.olustur(_denizli_ornekleri(ornek_excel), onbellek, kalip_tekrar_esigi=3)
    forklift = next(o.oneri for o in hafiza.ornekler if o.oneri.satir == 6)

    assert hafiza.benzerler(forklift, 1)[0].oneri.satir == 6
    assert 6 not in [o.oneri.satir for o in hafiza.benzerler(forklift, 5, haric_satir=6)]
    assert {o.oneri.satir for o in hafiza.benzerler(forklift, 5, sadece_ozgun=True)} == {6, 7}
    onbellek.kapat()


def test_vektorler_bir_kez_hesaplanip_dosyada_saklanir(ornek_excel, tmp_path):
    ornekler = _denizli_ornekleri(ornek_excel)
    gomucu = SayanGomucu()

    onbellek = VektorOnbellegi(tmp_path / "hafiza.db", "bge-m3", gomucu)
    Hafiza.olustur(ornekler, onbellek, kalip_tekrar_esigi=3)
    onbellek.kapat()
    assert gomucu.metin_sayisi == len(ornekler)

    onbellek = VektorOnbellegi(tmp_path / "hafiza.db", "bge-m3", gomucu)
    Hafiza.olustur(ornekler, onbellek, kalip_tekrar_esigi=3)
    onbellek.kapat()
    assert gomucu.metin_sayisi == len(ornekler)  # ikinci seferde hiç hesaplanmadı


def test_model_degisince_vektorler_yeniden_hesaplanir(ornek_excel, tmp_path):
    ornekler = _denizli_ornekleri(ornek_excel)
    gomucu = SayanGomucu()
    for model in ("bge-m3", "baska-model"):
        onbellek = VektorOnbellegi(tmp_path / "hafiza.db", model, gomucu)
        Hafiza.olustur(ornekler, onbellek, kalip_tekrar_esigi=3)
        onbellek.kapat()
    assert gomucu.metin_sayisi == 2 * len(ornekler)
