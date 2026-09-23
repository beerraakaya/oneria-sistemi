from datetime import date

import openpyxl
import pytest

from oneri.excel import ExcelHatasi, onerileri_oku


def test_satirlari_sade_kayitlara_cevirir(ornek_excel):
    oneriler = {o.satir: o for o in onerileri_oku(ornek_excel, "Genel Tablo")}

    assert sorted(oneriler) == [2, 3, 4, 5, 6, 7, 8, 9]  # boş 10. satır atlanır
    ilk = oneriler[2]
    assert ilk.fabrika == "Denizli"
    assert ilk.bolum == "Üretim"
    assert ilk.konu == "Enerji Verimliliği"
    assert ilk.mevcut_durum.startswith("Kompresör hatlarında")
    assert ilk.onerilen_durum.startswith("Kaçak tespit cihazıyla")
    assert ilk.durum == "Devam Ediyor"


def test_onay_durumundaki_yazim_farklarini_duzeltir(ornek_excel):
    oneriler = {o.satir: o for o in onerileri_oku(ornek_excel, "Genel Tablo")}
    assert oneriler[2].onay_durumu == "Öneri"  # Excel'de "Öneri " yazıyor


def test_iki_tarih_bicimini_de_okur(ornek_excel):
    oneriler = {o.satir: o for o in onerileri_oku(ornek_excel, "Genel Tablo")}
    assert oneriler[2].tarih == date(2025, 3, 1)
    assert oneriler[3].tarih == date(2025, 4, 2)  # "2025-04-02T00:00:00+00:27"


def test_bekleyen_oneriyi_tanir(ornek_excel):
    oneriler = {o.satir: o for o in onerileri_oku(ornek_excel, "Genel Tablo")}
    assert oneriler[9].bekliyor
    assert not oneriler[2].bekliyor


def test_kisi_adlarini_okumaz(ornek_excel):
    for oneri in onerileri_oku(ornek_excel, "Genel Tablo"):
        assert "Test Kişi" not in repr(oneri)
        assert "Sorumlu Kişi" not in repr(oneri)


def test_eksik_sayfa_icin_anlasilir_hata(ornek_excel):
    with pytest.raises(ExcelHatasi, match="'Yok' sayfası bulunamadı"):
        onerileri_oku(ornek_excel, "Yok")


def test_eksik_sutun_icin_anlasilir_hata(tmp_path):
    kitap = openpyxl.Workbook()
    kitap.active.title = "Genel Tablo"
    kitap.active.append(["Tarih", "Öneri Konusu"])
    yol = tmp_path / "eksik.xlsx"
    kitap.save(yol)
    with pytest.raises(ExcelHatasi, match="sütunu bulunamadı"):
        onerileri_oku(yol, "Genel Tablo")


def test_olmayan_dosya_icin_anlasilir_hata(tmp_path):
    with pytest.raises(ExcelHatasi, match="bulunamadı"):
        onerileri_oku(tmp_path / "yok.xlsx", "Genel Tablo")
