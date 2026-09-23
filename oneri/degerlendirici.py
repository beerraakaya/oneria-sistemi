"""Bir öneri için Onay Durumu, Durum ve Değerlendirme taslağı üretir."""

import json
import re
from collections import Counter
from dataclasses import dataclass

from .ayarlar import Ayarlar
from .excel import BASLANGIC_DURUMU, ONERI, ONERI_DEGIL, Oneri
from .hafiza import Hafiza
from .istem import GEREKCELER, cevap_semasi, kullanici_mesaji, sistem_mesaji
from .ollama import GecersizCevap, Ollama


@dataclass(frozen=True)
class Taslak:
    onay_durumu: str
    durum: str
    degerlendirme: str
    gerekce: str = ""  # modelin seçtiği kural, örn. "Rutin iş"
    onerilen_sey: str = ""  # modelin önerilen durumu nasıl anladığı


class Degerlendirici:
    def __init__(self, hafiza: Hafiza, ollama: Ollama, ayarlar: Ayarlar, kurallar: str):
        self._hafiza = hafiza
        self._ollama = ollama
        self._ayarlar = ayarlar
        self._sistem = sistem_mesaji(kurallar)

    def degerlendir(
        self, oneri: Oneri, haric_satir: int | None = None, sabit_onay: str | None = None
    ) -> Taslak:
        """`haric_satir` verilirse o satır örnek olarak gösterilmez (kör test için).

        `sabit_onay` verilirse karar değişmez; model yalnızca gerekçeyi ve metni yazar.
        """
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
            {"role": "user", "content": kullanici_mesaji(oneri, karar, tarz, sabit_onay)},
        ]
        sema = cevap_semasi(sabit_onay)
        cevap = self._sor(mesajlar, sema)
        onay = GEREKCELER[cevap["gerekce"]]
        uygunsuz = uygunsuz_ifadeler(cevap["degerlendirme"])
        celiski = karar_celiskileri(onay, cevap["degerlendirme"])
        if uygunsuz or celiski:
            # Bir kez düzelttirilir; yine olursa taslak hiç kabul edilmez.
            mesajlar += [
                {"role": "assistant", "content": json.dumps(cevap, ensure_ascii=False)},
                {"role": "user", "content": _duzeltme_istegi(uygunsuz, celiski, onay)},
            ]
            cevap = self._sor(mesajlar, sema)
            onay = GEREKCELER[cevap["gerekce"]]
            uygunsuz = uygunsuz_ifadeler(cevap["degerlendirme"])
            if uygunsuz:
                raise GecersizCevap(
                    f"Model uygunsuz ifade kullanmayı sürdürdü: {', '.join(uygunsuz)}"
                )
            celiski = karar_celiskileri(onay, cevap["degerlendirme"])
        gerekce = cevap["gerekce"]
        if celiski:
            # Taslak atılmaz, ekip kontrolünde dikkat çeksin diye işaretlenir.
            gerekce += f" (uyarı: metin kararla çelişebilir: {', '.join(celiski)})"
        return Taslak(onay, BASLANGIC_DURUMU[onay], cevap["degerlendirme"], gerekce, cevap["onerilen_sey"])

    def _sor(self, mesajlar: list[dict], sema: dict) -> dict:
        cevap = self._ollama.json_sohbet(
            self._ayarlar.dil_modeli,
            mesajlar,
            sema,
            {
                "temperature": self._ayarlar.sicaklik,
                "seed": self._ayarlar.tohum,
                "num_ctx": self._ayarlar.baglam_uzunlugu,
            },
        )
        gerekce = cevap.get("gerekce")
        metin = str(cevap.get("degerlendirme") or "").strip()
        if gerekce not in sema["properties"]["gerekce"]["enum"] or not metin:
            raise GecersizCevap(f"Modelin cevabı beklenen biçimde değil: {cevap}")
        return {
            "onerilen_sey": str(cevap.get("onerilen_sey") or "").strip(),
            "gerekce": gerekce,
            "degerlendirme": metin,
        }


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


class KarmaDegerlendirici:
    """Benzer öneriler güçlü şekilde aynı kararı gösteriyorsa kararı onlar verir, model metni yazar.

    Benzer öneriler bölünmüşse kararı model kurallara bakarak verir.
    """

    def __init__(self, hafiza: Hafiza, degerlendirici: Degerlendirici, adet: int, esik: int):
        self._hafiza = hafiza
        self._degerlendirici = degerlendirici
        self._adet = adet
        self._esik = esik

    def degerlendir(self, oneri: Oneri, haric_satir: int | None = None) -> Taslak:
        komsular = self._hafiza.benzerler(oneri, self._adet, haric_satir=haric_satir)
        onay, oy = Counter(k.oneri.onay_durumu for k in komsular).most_common(1)[0]
        if oy >= self._esik:
            taslak = self._degerlendirici.degerlendir(oneri, haric_satir, sabit_onay=onay)
            kaynak = f"benzer öneriler {oy}/{len(komsular)}"
        else:
            taslak = self._degerlendirici.degerlendir(oneri, haric_satir)
            kaynak = f"model (benzer öneriler bölünmüş: {oy}/{len(komsular)})"
        gerekce = f"{taslak.gerekce} - karar: {kaynak}"
        return Taslak(taslak.onay_durumu, taslak.durum, taslak.degerlendirme, gerekce, taslak.onerilen_sey)


# Değerlendirmede kullanılmayacak ifadeler ve yerine kullanılacaklar.
# "sakat" bilerek yok: İSG metinlerinde "sakatlanma riski" doğru bir ifadedir.
UYGUNSUZ_IFADELER = {"özürlü": "engelli"}


def uygunsuz_ifadeler(metin: str) -> list[str]:
    """Metinde geçen uygunsuz ifadeleri (ekleriyle birlikte, örn. "özürlüler") döndürür."""
    bulunan = []
    for ifade in UYGUNSUZ_IFADELER:
        bulunan += re.findall(rf"\b{ifade}\w*", metin, flags=re.IGNORECASE)
    return bulunan


# Karar ile metnin çeliştiğini gösteren ifadeler: karar "Öneri Değil" iken metin öneri
# olduğunu söylüyorsa ya da tersi.
KARARLA_CELISEN_IFADELER = {
    ONERI_DEGIL: [
        r"öneri niteliğindedir",
        r"geçerli bir öneri(?:dir)?(?! değil)",
        r"değerlendirmeye devam edilebilir",
    ],
    ONERI: [
        r"öneri olarak (?:değerlendirilmemiş|kabul edilmemiş|ilerletilmemiş)\w*",
        r"öneri sayılmaz",
        r"öneri niteliği taşımamaktadır",
        r"öneri değildir",
    ],
}


def karar_celiskileri(onay: str, metin: str) -> list[str]:
    """Metinde, verilen kararla çelişen ifadeleri döndürür."""
    return [
        eslesme.group(0)
        for kalip in KARARLA_CELISEN_IFADELER[onay]
        for eslesme in re.finditer(kalip, metin, flags=re.IGNORECASE)
    ]


def _duzeltme_istegi(uygunsuz: list[str], celiski: list[str], onay: str) -> str:
    parcalar = []
    if uygunsuz:
        yerine = "; ".join(
            f"'{ifade}' yerine '{UYGUNSUZ_IFADELER[kok]}'"
            for kok in UYGUNSUZ_IFADELER
            for ifade in uygunsuz
            if ifade.casefold().startswith(kok)
        )
        parcalar.append(f"Değerlendirmede uygun olmayan bir ifade kullandın: {yerine} kullanılmalı.")
    if celiski:
        parcalar.append(
            f'Seçtiğin gerekçeye göre karar "{onay}", ama metinde '
            f"{', '.join(repr(c) for c in celiski)} yazıyor; metin kararla çelişiyor."
        )
    parcalar.append(
        "Gerekçeyi değiştirmeden metni kararla tutarlı olacak şekilde yeniden yaz"
        " ve cevabı aynı JSON biçiminde ver."
    )
    return " ".join(parcalar)
