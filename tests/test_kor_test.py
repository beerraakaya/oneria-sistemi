import pytest

from oneri.degerlendirici import Taslak
from oneri.excel import onerileri_oku
from oneri.kor_test import kor_test_calistir, ozetle
from oneri.ollama import OllamaHatasi


class SiraliDegerlendirici:
    """Her çağrıda sıradaki cevabı döndürür; cevap bir hataysa onu fırlatır."""

    def __init__(self, cevaplar):
        self._cevaplar = iter(cevaplar)
        self.haric_tutulanlar = []

    def degerlendir(self, oneri, haric_satir=None):
        self.haric_tutulanlar.append(haric_satir)
        cevap = next(self._cevaplar)
        if isinstance(cevap, BaseException):
            raise cevap
        return cevap


@pytest.fixture
def oneriler(ornek_excel):
    return [o for o in onerileri_oku(ornek_excel, "Genel Tablo") if o.satir in (6, 7)]


def test_her_oneri_kendisi_haric_tutularak_degerlendirilir(oneriler):
    degerlendirici = SiraliDegerlendirici([Taslak("Öneri", "Devam Ediyor", "a")] * 2)
    kor_test_calistir(degerlendirici, oneriler, ilerleme=lambda _: None)
    assert degerlendirici.haric_tutulanlar == [6, 7]


@pytest.mark.parametrize(
    ("hata", "mesaj"),
    [
        (KeyboardInterrupt(), "Test yarıda kesildi: kullanıcı durdurdu"),
        (OllamaHatasi("Ollama'ya bağlanılamadı"), "Test yarıda kesildi: Ollama'ya bağlanılamadı"),
    ],
)
def test_yarida_kesilirse_o_ana_kadarki_sonuclar_doner(oneriler, hata, mesaj):
    degerlendirici = SiraliDegerlendirici([Taslak("Öneri", "Devam Ediyor", "a"), hata])
    mesajlar = []

    sonuclar = kor_test_calistir(degerlendirici, oneriler, ilerleme=mesajlar.append)

    assert [s.oneri.satir for s in sonuclar] == [6]
    assert mesajlar[-1] == mesaj
    ozet = ozetle(sonuclar)
    assert (ozet.toplam, ozet.cevaplanan, ozet.ayni_karar) == (1, 1, 1)


def test_bos_sonuc_ozeti():
    ozet = ozetle([])
    assert (ozet.toplam, ozet.oran, ozet.ortalama_sure) == (0, 0.0, 0.0)
