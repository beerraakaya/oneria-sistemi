"""Bir öneri için Onay Durumu, Durum ve Değerlendirme taslağı üretir."""

import json
import re
from collections import Counter
from dataclasses import dataclass

from .ayarlar import Ayarlar
from .excel import BASLANGIC_DURUMU, Oneri
from .hafiza import Hafiza
from .istem import CEVAP_SEMASI, GEREKCELER, kullanici_mesaji, sistem_mesaji
from .ollama import GecersizCevap, Ollama


@dataclass(frozen=True)
class Taslak:
    onay_durumu: str
    durum: str
    degerlendirme: str
    gerekce: str = ""  # modelin seçtiği kural, örn. "Rutin iş"


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

        mesajlar = [
            {"role": "system", "content": self._sistem},
            {"role": "user", "content": kullanici_mesaji(oneri, karar, tarz)},
        ]
        cevap = self._sor(mesajlar)
        uygunsuz = uygunsuz_ifadeler(cevap["degerlendirme"])
        if uygunsuz:
            # Bir kez düzelttirilir; yine kullanırsa taslak hiç kabul edilmez.
            mesajlar += [
                {"role": "assistant", "content": json.dumps(cevap, ensure_ascii=False)},
                {"role": "user", "content": _duzeltme_istegi(uygunsuz)},
            ]
            cevap = self._sor(mesajlar)
            uygunsuz = uygunsuz_ifadeler(cevap["degerlendirme"])
            if uygunsuz:
                raise GecersizCevap(
                    f"Model uygunsuz ifade kullanmayı sürdürdü: {', '.join(uygunsuz)}"
                )
        onay = GEREKCELER[cevap["gerekce"]]
        return Taslak(onay, BASLANGIC_DURUMU[onay], cevap["degerlendirme"], cevap["gerekce"])

    def _sor(self, mesajlar: list[dict]) -> dict:
        cevap = self._ollama.json_sohbet(
            self._ayarlar.dil_modeli,
            mesajlar,
            CEVAP_SEMASI,
            {
                "temperature": self._ayarlar.sicaklik,
                "seed": self._ayarlar.tohum,
                "num_ctx": self._ayarlar.baglam_uzunlugu,
            },
        )
        gerekce = cevap.get("gerekce")
        metin = str(cevap.get("degerlendirme") or "").strip()
        if gerekce not in GEREKCELER or not metin:
            raise GecersizCevap(f"Modelin cevabı beklenen biçimde değil: {cevap}")
        return {"gerekce": gerekce, "degerlendirme": metin}


class KomsuDegerlendirici:
    """Karşılaştırma ölçütü: modele sormadan, en benzer geçmiş önerilerin çoğunluk kararını verir.

    Metin yazmaz; yalnızca kararın ne kadar isabetli olabileceğini ölçmek için kullanılır.
    """

    def __init__(self, hafiza: Hafiza, adet: int):
        self._hafiza = hafiza
        self._adet = adet

    def degerlendir(self, oneri: Oneri, haric_satir: int | None = None) -> Taslak:
        komsular = self._hafiza.benzerler(oneri, self._adet, haric_satir=haric_satir)
        onay, oy = Counter(k.oneri.onay_durumu for k in komsular).most_common(1)[0]
        return Taslak(onay, BASLANGIC_DURUMU[onay], "", f"Benzer {len(komsular)} önerinin {oy}'i {onay}")


# Değerlendirmede kullanılmayacak ifadeler ve yerine kullanılacaklar.
# "sakat" bilerek yok: İSG metinlerinde "sakatlanma riski" doğru bir ifadedir.
UYGUNSUZ_IFADELER = {"özürlü": "engelli"}


def uygunsuz_ifadeler(metin: str) -> list[str]:
    """Metinde geçen uygunsuz ifadeleri (ekleriyle birlikte, örn. "özürlüler") döndürür."""
    bulunan = []
    for ifade in UYGUNSUZ_IFADELER:
        bulunan += re.findall(rf"\b{ifade}\w*", metin, flags=re.IGNORECASE)
    return bulunan


def _duzeltme_istegi(uygunsuz: list[str]) -> str:
    yerine = "; ".join(
        f"'{ifade}' yerine '{UYGUNSUZ_IFADELER[kok]}'"
        for kok in UYGUNSUZ_IFADELER
        for ifade in uygunsuz
        if ifade.casefold().startswith(kok)
    )
    return (
        f"Değerlendirmede uygun olmayan bir ifade kullandın: {yerine} kullanılmalı. "
        "Gerekçeyi değiştirmeden metni yeniden yaz ve cevabı aynı JSON biçiminde ver."
    )
