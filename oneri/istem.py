"""Yapay zekâya gönderilen talimat ve örnek metinlerini hazırlar."""

from .excel import ONERI, ONERI_DEGIL, Oneri
from .hafiza import Ornek

# Modelin cevabı bu biçime zorlanır; Onay Durumu yalnızca iki değerden biri olabilir.
CEVAP_SEMASI = {
    "type": "object",
    "properties": {
        "onay_durumu": {"type": "string", "enum": [ONERI, ONERI_DEGIL]},
        "degerlendirme": {"type": "string"},
    },
    "required": ["onay_durumu", "degerlendirme"],
}

_SISTEM = f"""Sen bir fabrikanın öneri sistemi ekibine yardım eden bir asistansın. Çalışanların gönderdiği iyileştirme önerileri için taslak değerlendirme yazarsın; son kararı ekip verir.

Görevin:
1. Önerinin "{ONERI}" mi yoksa "{ONERI_DEGIL}" mi olduğuna karar ver. Kararını aşağıdaki kurallara ve ekibin benzer önerilerde verdiği geçmiş kararlara dayandır.
2. Ekibin yazım örneklerindeki tarzda kısa bir değerlendirme metni yaz.

Cevabı yalnızca JSON olarak ver: {{"onay_durumu": "...", "degerlendirme": "..."}}

KURALLAR

"""

# Uzun öneri metinleri talimatı şişirmesin diye kısaltılır.
_EN_UZUN_ALAN = 400


def sistem_mesaji(kurallar: str) -> str:
    return _SISTEM + kurallar.strip()


def kullanici_mesaji(yeni: Oneri, karar_ornekleri: list[Ornek], tarz_ornekleri: list[Ornek]) -> str:
    """Örnekler en benzerden başlayarak verilmeli; en benzer olan yeni önerinin hemen üstüne gelir."""
    parcalar = [
        "BENZER GEÇMİŞ ÖNERİLER VE EKİBİN KARARLARI",
        "(Bu metinlerin bir kısmı eski kalıp cümlelerle yazıldı. Bunları karar için kullan, "
        "yazım tarzı için örnek alma.)",
        "",
    ]
    parcalar += _ornek_bloklari(karar_ornekleri)
    parcalar += ["YAZIM ÖRNEKLERİ (değerlendirme metnini bu tarzda yaz)", ""]
    parcalar += _ornek_bloklari(tarz_ornekleri)
    parcalar += [
        "YENİ ÖNERİ",
        _oneri_blogu(yeni),
        "",
        "Bu öneri için kararını ve değerlendirme metnini JSON olarak ver.",
    ]
    return "\n".join(parcalar)


def _ornek_bloklari(ornekler: list[Ornek]) -> list[str]:
    satirlar = []
    # Küçük modeller en son okuduklarına daha çok ağırlık verir; en benzer örnek en sona.
    for ornek in reversed(ornekler):
        satirlar += [
            _oneri_blogu(ornek.oneri),
            f"Karar: {ornek.oneri.onay_durumu}",
            f"Değerlendirme: {ornek.oneri.degerlendirme}",
            "",
        ]
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
