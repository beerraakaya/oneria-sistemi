import pytest

from oneri.ollama import GecersizCevap, Ollama
from oneri.uygulama import asistani_kur

from yardimci import YENI_TARZ_OLUMLU


def _kullanici_mesaji(sahte_ollama) -> str:
    return sahte_ollama.sohbetler()[-1]["messages"][1]["content"]


@pytest.fixture
def asistan(ayarlar, sahte_ollama):
    asistan = asistani_kur(ayarlar, Ollama(sahte_ollama.adres))
    yield asistan
    asistan.kapat()


def _oneri(asistan, satir):
    return next(o for o in asistan.oneriler if o.satir == satir)


def test_durumu_onay_durumuna_gore_yazar(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"onay_durumu": "Öneri Değil", "degerlendirme": "Rutin bakım işidir."}
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert (taslak.onay_durumu, taslak.durum) == ("Öneri Değil", "Red Edildi")

    sahte_ollama.sohbet_cevabi = {"onay_durumu": "Öneri", "degerlendirme": " Uygulanabilir. "}
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert (taslak.onay_durumu, taslak.durum, taslak.degerlendirme) == ("Öneri", "Devam Ediyor", "Uygulanabilir.")


def test_istemde_yeni_oneri_kurallar_ve_ornekler_var(asistan, sahte_ollama, ayarlar):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    sohbet = sahte_ollama.sohbetler()[-1]
    sistem, kullanici = sohbet["messages"][0]["content"], sohbet["messages"][1]["content"]

    assert "Rutin bakım işleri öneri sayılmaz." in sistem
    assert "YENİ ÖNERİ" in kullanici
    assert kullanici.rstrip().endswith("JSON olarak ver.")
    assert "Basamaklara yeni kaymaz bant" in kullanici
    assert YENI_TARZ_OLUMLU in kullanici
    assert sohbet["model"] == ayarlar.dil_modeli
    assert sohbet["options"] == {"temperature": ayarlar.sicaklik, "num_ctx": ayarlar.baglam_uzunlugu}


def test_tuzla_test_kaydi_ve_kisi_adlari_isteme_girmez(asistan, sahte_ollama):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    kullanici = _kullanici_mesaji(sahte_ollama)
    assert "Makaralar ambalajsız" not in kullanici  # Tuzla
    assert "denene" not in kullanici  # test kaydı
    assert "Test Kişi" not in kullanici
    assert "Sorumlu Kişi" not in kullanici


def test_haric_tutulan_satirin_cevabi_gorunmez(asistan, sahte_ollama):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 6), haric_satir=6)
    assert YENI_TARZ_OLUMLU not in _kullanici_mesaji(sahte_ollama)


def test_gecersiz_karar_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"onay_durumu": "Belki", "degerlendirme": "Bilemedim."}
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))


def test_bos_degerlendirme_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"onay_durumu": "Öneri", "degerlendirme": "  "}
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
