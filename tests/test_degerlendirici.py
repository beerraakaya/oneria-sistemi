import pytest

from oneri.degerlendirici import KarmaDegerlendirici, karar_celiskileri, uygunsuz_ifadeler
from oneri.istem import GEREKCELER
from oneri.ollama import GecersizCevap, Ollama
from oneri.uygulama import asistani_kur

from yardimci import YENI_TARZ_OLUMLU, YENI_TARZ_OLUMSUZ


def _karar(gerekce: str, onerilen_sey: str = "Basamaklara kaymaz bant yapıştırmak.") -> dict:
    return {"onerilen_sey": onerilen_sey, "gerekce": gerekce}


def _metin(gerekce: str, degerlendirme: str) -> dict:
    return {"gerekce": gerekce, "degerlendirme": degerlendirme}


def _kontrol(cevap: str, aciklama: str = "Aşınan bant aynısıyla yenileniyor.") -> dict:
    return {"aciklama": aciklama, "cevap": cevap}


@pytest.fixture
def asistan(ayarlar, sahte_ollama):
    asistan = asistani_kur(ayarlar, Ollama(sahte_ollama.adres))
    yield asistan
    asistan.kapat()


def _oneri(asistan, satir):
    return next(o for o in asistan.oneriler if o.satir == satir)


def test_once_karar_sonra_karar_belliyken_metin_istenir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Rutin iş"),
        _kontrol("Evet"),
        _metin("Rutin iş", "Aşınan bantların yenilenmesi rutin bakım işidir."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    karar, _, metin = sahte_ollama.sohbetler()
    assert list(karar["format"]["properties"]) == ["onerilen_sey", "gerekce"]
    assert karar["format"]["properties"]["gerekce"]["enum"] == list(GEREKCELER)
    assert karar["messages"][1]["content"].startswith("EKİBİN BENZER")
    assert "KARAR adımı" in karar["messages"][1]["content"]

    # Metin adımında karar belli; yalnızca o karara uyan gerekçeler seçilebilir.
    assert 'kararı "Öneri Değil" olarak belirlendi' in metin["messages"][1]["content"]
    assert "Geçerli öneri" not in metin["format"]["properties"]["gerekce"]["enum"]

    assert (taslak.onay_durumu, taslak.durum, taslak.gerekce) == ("Öneri Değil", "Red Edildi", "Rutin iş")
    assert taslak.degerlendirme == "Aşınan bantların yenilenmesi rutin bakım işidir."
    assert taslak.onerilen_sey == "Basamaklara kaymaz bant yapıştırmak."


def test_oneri_karari_devam_ediyor_yazar(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [_karar("Geçerli öneri"), _metin("Geçerli öneri", " Uygulanabilir. ")]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert (taslak.onay_durumu, taslak.durum, taslak.degerlendirme) == ("Öneri", "Devam Ediyor", "Uygulanabilir.")
    assert sahte_ollama.sohbetler()[1]["format"]["properties"]["gerekce"]["enum"] == ["Geçerli öneri"]


def test_istemde_kurallar_yeni_oneri_ve_ekibin_degerlendirmeleri_var(asistan, sahte_ollama, ayarlar):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    sohbet = sahte_ollama.sohbetler()[0]
    sistem, kullanici = sohbet["messages"][0]["content"], sohbet["messages"][1]["content"]

    assert "Rutin bakım işleri öneri sayılmaz." in sistem
    assert "Ekip gibi bak" in sistem
    assert "YENİ ÖNERİ" in kullanici
    assert "Basamaklara yeni kaymaz bant" in kullanici
    assert YENI_TARZ_OLUMLU in kullanici and YENI_TARZ_OLUMSUZ in kullanici
    assert sohbet["model"] == ayarlar.dil_modeli
    assert sohbet["options"] == {
        "temperature": 0.0,
        "seed": ayarlar.tohum,
        "num_ctx": ayarlar.baglam_uzunlugu,
        "num_predict": ayarlar.en_fazla_token,
    }


def test_yalnizca_ekibin_kendi_yazdigi_degerlendirmeler_gosterilir(asistan, sahte_ollama):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    kullanici = sahte_ollama.sohbetler()[0]["messages"][1]["content"]
    assert "incelemeye devam edilecektir" not in kullanici  # eski kalıp metin
    assert "Kompresör hatlarında" not in kullanici  # kalıp metinli kayıt hiç gösterilmez


def test_tuzla_test_kaydi_ve_kisi_adlari_isteme_girmez(asistan, sahte_ollama):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    for sohbet in sahte_ollama.sohbetler():
        kullanici = sohbet["messages"][1]["content"]
        assert "Makaralar ambalajsız" not in kullanici  # Tuzla
        assert "denene" not in kullanici  # test kaydı
        assert "Test Kişi" not in kullanici
        assert "Sorumlu Kişi" not in kullanici


def test_haric_tutulan_satirin_cevabi_gorunmez(asistan, sahte_ollama):
    asistan.degerlendirici.degerlendir(_oneri(asistan, 6), haric_satir=6)
    for sohbet in sahte_ollama.sohbetler():
        assert YENI_TARZ_OLUMLU not in sohbet["messages"][1]["content"]


def test_gecersiz_gerekce_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = _karar("Belki")
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))


def test_bos_degerlendirme_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [_karar("Geçerli öneri"), _metin("Geçerli öneri", "  ")]
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))


def test_bozuk_cevapta_bir_kez_daha_yuksek_sicaklikla_denenir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        '{"onerilen_sey": "aynı aynı aynı aynı',  # döngüye girip kesilmiş cevap
        _karar("Geçerli öneri"),
        _metin("Geçerli öneri", "Uygulanabilir."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    assert [s["options"]["temperature"] for s in sahte_ollama.sohbetler()] == [0.0, 0.3, 0.0]
    assert taslak.degerlendirme == "Uygulanabilir."


def test_uygunsuz_ifade_bulunur():
    assert uygunsuz_ifadeler("Özürlü çalışanlar ve özürlülere yönelik rampa") == ["Özürlü", "özürlülere"]
    assert uygunsuz_ifadeler("Engelli erişimi için rampa; sakatlanma riski azalır.") == []


def test_uygunsuz_ifade_bir_kez_duzelttirilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Geçerli öneri"),
        _metin("Geçerli öneri", "Özürlü çalışanlar için erişimi artırır."),
        _metin("Geçerli öneri", "Engelli çalışanlar için erişimi artırır."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    assert taslak.degerlendirme == "Engelli çalışanlar için erişimi artırır."
    duzeltme = sahte_ollama.sohbetler()[-1]["messages"][-1]["content"]
    assert "'Özürlü' yerine 'engelli'" in duzeltme


def test_duzeltmeden_sonra_da_kullanirsa_taslak_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Geçerli öneri"),
        _metin("Geçerli öneri", "Özürlü çalışanlar için uygundur."),
    ]
    with pytest.raises(GecersizCevap, match="uygunsuz ifade"):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert len(sahte_ollama.sohbetler()) == 3


def test_her_gerekce_bir_onay_durumuna_karsilik_gelir():
    assert GEREKCELER["Geçerli öneri"] == "Öneri"
    assert {onay for ad, onay in GEREKCELER.items() if ad != "Geçerli öneri"} == {"Öneri Değil"}


def test_sabit_kararda_karar_adimi_atlanir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = _metin("Geçerli öneri", "Uygulanabilir.")
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9), sabit_onay="Öneri")
    assert len(sahte_ollama.sohbetler()) == 1
    assert taslak.onay_durumu == "Öneri"


def test_sabit_karara_uymayan_gerekce_reddedilir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = _metin("Rutin iş", "Rutin bakım işidir.")
    with pytest.raises(GecersizCevap):
        asistan.degerlendirici.degerlendir(_oneri(asistan, 9), sabit_onay="Öneri")


def test_karma_benzerler_guclu_ayniysa_karari_onlar_verir(asistan, sahte_ollama):
    # 9. satıra en benzer 5 örneğin 4'ü "Öneri"; eşik 4 -> karar sabitlenir.
    sahte_ollama.sohbet_cevabi = _metin("Geçerli öneri", "Uygulanabilir.")
    karma = KarmaDegerlendirici(asistan.hafiza, asistan.degerlendirici, adet=5, esik=4)
    taslak = karma.degerlendir(_oneri(asistan, 9))

    (sohbet,) = sahte_ollama.sohbetler()
    assert sohbet["format"]["properties"]["gerekce"]["enum"] == ["Geçerli öneri"]
    assert 'kararı "Öneri" olarak belirlendi' in sohbet["messages"][1]["content"]
    assert taslak.gerekce == "Geçerli öneri - karar: benzer öneriler 4/5"


def test_karma_benzerler_bolunmusse_karari_model_verir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Rutin iş"),
        _kontrol("Evet"),
        _metin("Rutin iş", "Rutin bakım işidir."),
    ]
    karma = KarmaDegerlendirici(asistan.hafiza, asistan.degerlendirici, adet=5, esik=5)
    taslak = karma.degerlendir(_oneri(asistan, 9))

    assert len(sahte_ollama.sohbetler()) == 3
    assert taslak.onay_durumu == "Öneri Değil"
    assert taslak.gerekce == "Rutin iş - karar: model (benzer öneriler bölünmüş: 4/5)"


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
        _karar("Rutin iş"),
        _kontrol("Evet"),
        _metin("Rutin iş", "Öneri niteliğindedir ama bakım işidir."),
        _metin("Rutin iş", "Aşınan bantın yenilenmesi rutin bakımdır."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    assert taslak.degerlendirme == "Aşınan bantın yenilenmesi rutin bakımdır."
    duzeltme = sahte_ollama.sohbetler()[-1]["messages"][-1]["content"]
    assert 'karar "Öneri Değil"' in duzeltme and "'Öneri niteliğindedir'" in duzeltme


def test_celiski_surerse_taslak_uyariyla_tutulur(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Rutin iş"),
        _kontrol("Evet"),
        _metin("Rutin iş", "Öneri niteliğindedir."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert len(sahte_ollama.sohbetler()) == 4
    assert taslak.onay_durumu == "Öneri Değil"
    assert taslak.gerekce == "Rutin iş (uyarı: metin kararla çelişebilir: Öneri niteliğindedir)"


def test_red_gerekcesi_kontrol_sorusuyla_dogrulanir(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Rutin iş"),
        _kontrol("Evet"),
        _metin("Rutin iş", "Aşınan bantın yenilenmesi rutin bakımdır."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    kontrol = sahte_ollama.sohbetler()[1]
    assert kontrol["format"]["properties"]["cevap"]["enum"] == ["Evet", "Hayır"]
    # Kontrol sorusunda örnekler ve kurallar yok; yalnızca öneri ve soru.
    assert "EKİBİN BENZER" not in kontrol["messages"][1]["content"]
    assert "KURALLAR" not in kontrol["messages"][0]["content"]
    assert "Basamaklara yeni kaymaz bant" in kontrol["messages"][1]["content"]
    assert "eski hâline" in kontrol["messages"][1]["content"]
    assert (taslak.onay_durumu, taslak.gerekce) == ("Öneri Değil", "Rutin iş")


def test_dogrulanmayan_red_gerekcesinde_karar_oneri_olur(asistan, sahte_ollama):
    sahte_ollama.sohbet_cevabi = [
        _karar("Politika/sosyal hak talebi"),
        _kontrol("Hayır", "Asıl fayda iş güvenliğine."),
        _metin("Geçerli öneri", "Kayma riskini azaltabilir. Maliyet belirlenmelidir."),
    ]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))

    assert "kişisel yararına" in sahte_ollama.sohbetler()[1]["messages"][1]["content"]
    assert 'kararı "Öneri" olarak belirlendi' in sahte_ollama.sohbetler()[2]["messages"][1]["content"]
    assert (taslak.onay_durumu, taslak.durum) == ("Öneri", "Devam Ediyor")
    assert taslak.gerekce == (
        'Geçerli öneri (kontrol: "Politika/sosyal hak talebi" doğrulanmadı, karar Öneri yapıldı: '
        "Asıl fayda iş güvenliğine.)"
    )


@pytest.mark.parametrize("gerekce", ["Somut çözüm yok", "Yasal/İSG yükümlülüğü"])
def test_diger_red_gerekceleri_kontrol_edilmez(asistan, sahte_ollama, gerekce):
    sahte_ollama.sohbet_cevabi = [_karar(gerekce), _metin(gerekce, "Çözüm yazılmalıdır.")]
    taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    assert len(sahte_ollama.sohbetler()) == 2
    assert taslak.onay_durumu == "Öneri Değil"


def test_red_kontrolu_ayarla_kapatilabilir(ayarlar, sahte_ollama):
    from dataclasses import replace

    asistan = asistani_kur(replace(ayarlar, red_kontrolu=False), Ollama(sahte_ollama.adres))
    try:
        sahte_ollama.sohbet_cevabi = [_karar("Rutin iş"), _metin("Rutin iş", "Rutin bakımdır.")]
        taslak = asistan.degerlendirici.degerlendir(_oneri(asistan, 9))
    finally:
        asistan.kapat()
    assert len(sahte_ollama.sohbetler()) == 2
    assert taslak.onay_durumu == "Öneri Değil"
