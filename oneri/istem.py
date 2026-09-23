"""Yapay zekâya gönderilen talimat ve örnek metinlerini hazırlar."""

from .excel import ONERI, ONERI_DEGIL, Oneri
from .hafiza import Ornek

# Model önce hangi kurala uyduğunu seçer; Onay Durumu bu seçimden çıkarılır.
# Adlar kurallar.md'deki başlıklarla aynı olmalı.
GEREKCELER = {
    "Geçerli öneri": ONERI,
    "Somut çözüm yok": ONERI_DEGIL,
    "Rutin iş": ONERI_DEGIL,
    "Yasal/İSG yükümlülüğü": ONERI_DEGIL,
    "Mükerrer": ONERI_DEGIL,
    "Politika/sosyal hak talebi": ONERI_DEGIL,
}


def cevap_semasi(sabit_onay: str | None = None) -> dict:
    """Karar önceden verildiyse model yalnızca o karara uyan gerekçelerden seçebilir.

    Alan sırası önemli: model önce gerekçeyi seçer, sonra metni yazar.
    """
    gerekceler = [g for g, onay in GEREKCELER.items() if sabit_onay in (None, onay)]
    return {
        "type": "object",
        "properties": {
            "gerekce": {"type": "string", "enum": gerekceler},
            "degerlendirme": {"type": "string"},
        },
        "required": ["gerekce", "degerlendirme"],
    }


_SISTEM = f"""Sen bir fabrikanın öneri sistemi ekibine yardım eden bir asistansın. Çalışanların gönderdiği iyileştirme önerileri için taslak değerlendirme yazarsın; son kararı ekip verir.

Görevin:
1. Önce öneriyi aşağıdaki kurallarla karşılaştır ve hangi gerekçeye uyduğunu seç: {", ".join(f'"{g}"' for g in GEREKCELER)}. "Geçerli öneri" dışındaki her gerekçe "{ONERI_DEGIL}" demektir. Ekibin benzer önerilerde verdiği kararlara da bak.
2. Sonra ekibin yazım örneklerindeki tarzda, bu öneriye özgü iki cümlelik bir değerlendirme yaz. Önerinin kendi içeriğinden (makine, malzeme, süreç adı) somut olarak bahset. Kalıp cümle kullanma; "Öneri niteliğindedir" gibi genel bir girişle başlama.

Cevabı yalnızca JSON olarak ver: {{"gerekce": "...", "degerlendirme": "..."}}

KURALLAR

"""

# Uzun öneri metinleri talimatı şişirmesin diye kısaltılır.
_EN_UZUN_ALAN = 400


def sistem_mesaji(kurallar: str) -> str:
    return _SISTEM + kurallar.strip()


def kullanici_mesaji(
    yeni: Oneri,
    karar_ornekleri: list[Ornek],
    tarz_ornekleri: list[Ornek],
    sabit_onay: str | None = None,
) -> str:
    """Örnekler en benzerden başlayarak verilmeli; en benzer olan yeni önerinin hemen üstüne gelir."""
    parcalar = ["BENZER GEÇMİŞ ÖNERİLER VE EKİBİN KARARLARI", ""]
    parcalar += _ornek_bloklari(karar_ornekleri)
    parcalar += ["YAZIM ÖRNEKLERİ (değerlendirme metnini bu tarzda yaz)", ""]
    parcalar += _ornek_bloklari(tarz_ornekleri)
    parcalar += [
        "YENİ ÖNERİ",
        _oneri_blogu(yeni),
        "",
    ]
    if sabit_onay:
        parcalar.append(
            f'Ekibin benzer önerilerdeki kararlarına göre bu önerinin kararı "{sabit_onay}" olarak '
            "belirlendi. Bu karara uyan gerekçeyi seç ve metni buna göre yaz."
        )
    parcalar.append("Bu öneri için gerekçeni ve değerlendirme metnini JSON olarak ver.")
    return "\n".join(parcalar)


def _ornek_bloklari(ornekler: list[Ornek]) -> list[str]:
    satirlar = []
    # Küçük modeller en son okuduklarına daha çok ağırlık verir; en benzer örnek en sona.
    for ornek in reversed(ornekler):
        satirlar += [_oneri_blogu(ornek.oneri), f"Karar: {ornek.oneri.onay_durumu}"]
        # Eski kalıp metinler gösterilmez; model onları kopyalıyor.
        if ornek.ozgun:
            satirlar.append(f"Değerlendirme: {ornek.oneri.degerlendirme}")
        satirlar.append("")
    return satirlar


def _oneri_blogu(oneri: Oneri) -> str:
    return "\n".join(
        (
            f"Konu: {oneri.konu or '-'}",
            f"Bölüm: {oneri.bolum or '-'}",
            f"Mevcut durum: {_kisalt(oneri.mevcut_durum) or '-'}",
            f"Önerilen durum: {_kisalt(oneri.onerilen_durum) or '-'}",
        )
    )


def _kisalt(metin: str) -> str:
    if len(metin) <= _EN_UZUN_ALAN:
        return metin
    return metin[:_EN_UZUN_ALAN].rsplit(" ", 1)[0] + " …"
