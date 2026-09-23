import pytest

from oneri.degerlendirici import KarmaDegerlendirici, karar_celiskileri, uygunsuz_ifadeler
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
        "num_predict": ayarlar.en_fazla_token,
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


def test_karma_benzerler_guclu_ayniysa_karari_onlar_verir(asistan, sahte_ollama):
    # 9. satıra en benzer 5 örneğin 4'ü "Öneri"; eşik 4 -> karar sabitlenir.
    karma = KarmaDegerlendirici(asistan.hafiza, asistan.degerlendirici, adet=5, esik=4)
    taslak = karma.degerlendir(_oneri(asistan, 9))

    sohbet = sahte_ollama.sohbetler()[-1]
    assert sohbet["format"]["properties"]["gerekce"]["enum"] == ["Geçerli öneri"]
    assert 'kararı "Öneri" olarak belirlendi' in sohbet["messages"][1]["content"]
    assert taslak.onay_durumu == "Öneri"
    assert taslak.gerekce == "Geçerli öneri - karar: benzer öneriler 4/5"


def test_karma_benzerler_bolunmusse_karari_model_verir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"gerekce": "Rutin iş", "degerlendirme": "Rutin bakım işidir."}
    karma = KarmaDegerlendirici(asistan.hafiza, asistan.degerlendirici, adet=5, esik=5)
    taslak = karma.degerlendir(_oneri(asistan, 9))

    sohbet = sahte_ollama.sohbetler()[-1]
    assert sohbet["format"]["properties"]["gerekce"]["enum"] == list(GEREKCELER)
    assert "olarak belirlendi" not in sohbet["messages"][1]["content"]
    assert taslak.onay_durumu == "Öneri Değil"
    assert taslak.gerekce == "Rutin iş - karar: model (benzer öneriler bölünmüş: 4/5)"


def test_sabit_karara_uymayan_gerekce_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"gerekce": "Rutin iş", "degerlendirme": "Rutin bakım işidir."}
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9), sabit_onay="Öneri")


def test_model_once_onerilen_seyi_ozetler(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {
        "onerilen_sey": "Basamaklara kaymaz bant yapıştırmak.",
        "gerekce": "Rutin iş",
        "degerlendirme": "Aşınan bantın yenilenmesi rutin bakımdır.",
    }
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    sema = sahte_ollama.sohbetler()[-1]["format"]
    assert list(sema["properties"])[:2] == ["onerilen_sey", "gerekce"]
    assert taslak.onerilen_sey == "Basamaklara kaymaz bant yapıştırmak."
    assert "Karar mevcut duruma değil, önerilen şeye göre verilir." in sahte_ollama.sohbetler()[-1]["messages"][0]["content"]


def test_karar_celiskisi_bulunur():
    assert karar_celiskileri("Öneri Değil", "Öneri niteliğindedir; maliyet hesaplanmalıdır.") == ["Öneri niteliğindedir"]
    assert karar_celiskileri("Öneri", "Bu kayıt öneri sayılmaz.") == ["öneri sayılmaz"]
    assert karar_celiskileri("Öneri", "Öneri niteliğindedir; pilot uygulanmalıdır.") == []
    assert karar_celiskileri("Öneri Değil", "Rutin bakım işidir; öneri sayılmaz.") == []
    # "Öneri Değil" kararıyla uyumlu olumsuz cümleler yanlış alarm vermemeli.
    assert karar_celiskileri("Öneri Değil", "Bu haliyle değerlendirmeye devam edilemez.") == []
    assert karar_celiskileri("Öneri Değil", "Bu, geçerli bir öneri değildir.") == []
    assert karar_celiskileri("Öneri Değil", "Geçerli bir öneridir.") == ["Geçerli bir öneridir"]


def test_kararla_celisen_metin_bir_kez_duzelttirilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        {"onerilen_sey": "x", "gerekce": "Rutin iş", "degerlendirme": "Öneri niteliğindedir ama bakım işidir."},
        {"onerilen_sey": "x", "gerekce": "Rutin iş", "degerlendirme": "Aşınan bantın yenilenmesi rutin bakımdır."},
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    assert taslak.degerlendirme == "Aşınan bantın yenilenmesi rutin bakımdır."
    duzeltme = sahte_ollama.sohbetler()[-1]["messages"][-1]["content"]
    assert 'karar "Öneri Değil"' in duzeltme and "'Öneri niteliğindedir'" in duzeltme


def test_celiski_surerse_taslak_uyariyla_tutulur(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = {"gerekce": "Rutin iş", "degerlendirme": "Öneri niteliğindedir."}
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert len(sahte_ollama.sohbetler()) == 2
    assert taslak.onay_durumu == "Öneri Değil"
    assert taslak.gerekce == "Rutin iş (uyarı: metin kararla çelişebilir: Öneri niteliğindedir)"


def test_bozuk_cevapta_bir_kez_daha_yuksek_sicaklikla_denenir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        '{"onerilen_sey": "aynı aynı aynı aynı',  # döngüye girip kesilmiş cevap
        {"onerilen_sey": "x", "gerekce": "Geçerli öneri", "degerlendirme": "Uygulanabilir."},
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    sohbetler = sahte_ollama.sohbetler()
    assert [s["options"]["temperature"] for s in sohbetler] == [0.0, 0.3]
    assert taslak.degerlendirme == "Uygulanabilir."
