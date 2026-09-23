import pytest

from oneri.degerlendirici import uygunsuz_ifadeler
from oneri.istem import GEREKCELER
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
    sahte_ollama.sohbet_cevabi = {"gerekce": "Rutin iş", "degerlendirme": "Rutin bakım işidir."}
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert (taslak.gerekce, taslak.onay_durumu, taslak.durum) == ("Rutin iş", "Öneri Değil", "Red Edildi")

    sahte_ollama.sohbet_cevabi = {"gerekce": "Geçerli öneri", "degerlendirme": " Uygulanabilir. "}
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
    assert sohbet["options"] == {
        "temperature": 0.0,
        "seed": ayarlar.tohum,
        "num_ctx": ayarlar.baglam_uzunlugu,
    }


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
    sahte_ollama.sohbet_cevabi = {"gerekce": "Belki", "degerlendirme": "Bilemedim."}
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))


def test_bos_degerlendirme_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"gerekce": "Geçerli öneri", "degerlendirme": "  "}
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))


def test_uygunsuz_ifade_bulunur():
    assert uygunsuz_ifadeler("Özürlü çalışanlar ve özürlülere yönelik rampa") == ["Özürlü", "özürlülere"]
    assert uygunsuz_ifadeler("Engelli erişimi için rampa; sakatlanma riski azalır.") == []


def test_uygunsuz_ifade_bir_kez_duzelttirilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        {"gerekce": "Geçerli öneri", "degerlendirme": "Özürlü çalışanlar için erişimi artırır."},
        {"gerekce": "Geçerli öneri", "degerlendirme": "Engelli çalışanlar için erişimi artırır."},
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    assert taslak.degerlendirme == "Engelli çalışanlar için erişimi artırır."
    duzeltme = sahte_ollama.sohbetler()[-1]["messages"][-1]["content"]
    assert "'Özürlü' yerine 'engelli'" in duzeltme


def test_duzeltmeden_sonra_da_kullanirsa_taslak_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"gerekce": "Geçerli öneri", "degerlendirme": "Özürlü çalışanlar için uygundur."}
    with pytest.raises(GecersizCevap, match="uygunsuz ifade"):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert len(sahte_ollama.sohbetler()) == 2


def test_eski_kalip_metinler_istemde_gosterilmez(asistan, sahte_ollama):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    kullanici = _kullanici_mesaji(sahte_ollama)
    assert "incelemeye devam edilecektir" not in kullanici  # kalıp metin
    assert "Kompresör hatlarında" in kullanici or "Bobin değişiminde" in kullanici  # öneri yine görünür


def test_her_gerekce_bir_onay_durumuna_karsilik_gelir():
    assert GEREKCELER["Geçerli öneri"] == "Öneri"
    assert {onay for ad, onay in GEREKCELER.items() if ad != "Geçerli öneri"} == {"Öneri Değil"}
