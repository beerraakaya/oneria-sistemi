"""Bir öneri için Onay Durumu, Durum ve Değerlendirme taslağı üretir."""

from dataclasses import dataclass

from .ayarlar import Ayarlar
from .excel import BASLANGIC_DURUMU, Oneri
from .hafiza import Hafiza
from .istem import CEVAP_SEMASI, kullanici_mesaji, sistem_mesaji
from .ollama import GecersizCevap, Ollama


@dataclass(frozen=True)
class Taslak:
    onay_durumu: str
    durum: str
    degerlendirme: str


class Degerlendirici:
    def __init__(self, hafiza: Hafiza, ollama: Ollama, ayarlar: Ayarlar, kurallar: str):
        self._hafiza = hafiza
        self._ollama = ollama
        self._ayarlar = ayarlar
        self._sistem = sistem_mesaji(kurallar)

    def degerlendir(self, oneri: Oneri, haric_satir: int | None = None) -> Taslak:
        """`haric_satir` verilirse o satır örnek olarak gösterilmez (kör test için)."""
        tarz = self._hafiza.benzerler(
            oneri, self._ayarlar.tarz_ornegi_sayisi, sadece_ozgun=True, haric_satir=haric_satir
        )
        tarzdaki_satirlar = {ornek.oneri.satir for ornek in tarz}
        karar = [
            ornek
            for ornek in self._hafiza.benzerler(
                oneri, self._ayarlar.karar_ornegi_sayisi + len(tarz), haric_satir=haric_satir
            )
            if ornek.oneri.satir not in tarzdaki_satirlar
        ][: self._ayarlar.karar_ornegi_sayisi]

        cevap = self._ollama.json_sohbet(
            self._ayarlar.dil_modeli,
            [
                {"role": "system", "content": self._sistem},
                {"role": "user", "content": kullanici_mesaji(oneri, karar, tarz)},
            ],
            CEVAP_SEMASI,
            {"temperature": self._ayarlar.sicaklik, "num_ctx": self._ayarlar.baglam_uzunlugu},
        )

        onay = cevap.get("onay_durumu")
        metin = str(cevap.get("degerlendirme") or "").strip()
        if onay not in BASLANGIC_DURUMU or not metin:
            raise GecersizCevap(f"Modelin cevabı beklenen biçimde değil: {cevap}")
        return Taslak(onay, BASLANGIC_DURUMU[onay], metin)
