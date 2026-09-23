"""Parçaları bir araya getirir: Excel -> hafıza -> değerlendirici."""

from dataclasses import dataclass

from .ayarlar import Ayarlar
from .degerlendirici import Degerlendirici
from .excel import Oneri, onerileri_oku
from .hafiza import Hafiza, VektorOnbellegi, ornek_alinabilir_mi
from .ollama import Ollama


def fabrika_onerileri(ayarlar: Ayarlar) -> list[Oneri]:
    """Excel'deki önerilerden yalnızca ayarlardaki fabrikaya ait olanlar."""
    return [
        oneri
        for oneri in onerileri_oku(ayarlar.excel_yolu, ayarlar.sayfa_adi)
        if oneri.fabrika.casefold() == ayarlar.fabrika.casefold()
    ]


@dataclass
class Asistan:
    oneriler: list[Oneri]
    hafiza: Hafiza
    degerlendirici: Degerlendirici
    _onbellek: VektorOnbellegi

    def kapat(self) -> None:
        self._onbellek.kapat()


def asistani_kur(ayarlar: Ayarlar, ollama: Ollama) -> Asistan:
    oneriler = fabrika_onerileri(ayarlar)
    kurallar = ayarlar.kurallar_yolu.read_text(encoding="utf-8")
    onbellek = VektorOnbellegi(
        ayarlar.hafiza_yolu,
        ayarlar.gomme_modeli,
        lambda metinler: ollama.gom(ayarlar.gomme_modeli, metinler),
    )
    try:
        hafiza = Hafiza.olustur(
            [o for o in oneriler if ornek_alinabilir_mi(o, ayarlar.en_kisa_degerlendirme)],
            onbellek,
            ayarlar.kalip_tekrar_esigi,
        )
    except BaseException:
        onbellek.kapat()
        raise
    return Asistan(oneriler, hafiza, Degerlendirici(hafiza, ollama, ayarlar, kurallar), onbellek)
