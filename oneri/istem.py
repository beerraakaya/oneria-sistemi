"""Yapay zekâya gönderilen talimat ve örnek metinlerini hazırlar.

Değerlendirme iki adımda yapılır: önce karar (gerekçe seçimi), sonra karar belliyken metin.
Karar belli olunca model eksik aramak yerine ekip gibi önce faydayı görüp metni yazıyor.
"""

from .excel import ONERI, ONERI_DEGIL, Oneri
from .hafiza import Ornek

# Model önce hangi kurala uyduğunu seçer; Onay Durumu bu seçimden çıkarılır.
# Adlar kurallar.md'deki başlıklarla aynı olmalı. "Mükerrer" bilerek yok: bir uygulamanın
# fabrikada zaten olup olmadığını model bilemez, benzer örnek gördüğü için yanlış seçiyordu.
GEREKCELER = {
    "Geçerli öneri": ONERI,
    "Somut çözüm yok": ONERI_DEGIL,
    "Rutin iş": ONERI_DEGIL,
    "Yasal/İSG yükümlülüğü": ONERI_DEGIL,
    "Politika/sosyal hak talebi": ONERI_DEGIL,
}


def karar_semasi() -> dict:
    """1. adım. Alan sırası önemli: model önce önerilen şeyi özetler, sonra gerekçeyi seçer."""
    return {
        "type": "object",
        "properties": {
            "onerilen_sey": {"type": "string"},
            "gerekce": {"type": "string", "enum": list(GEREKCELER)},
        },
        "required": ["onerilen_sey", "gerekce"],
    }


def metin_semasi(onay: str) -> dict:
    """2. adım. Karar belli; model yalnızca o karara uyan gerekçelerden seçebilir."""
    return {
        "type": "object",
        "properties": {
            "gerekce": {"type": "string", "enum": [g for g, o in GEREKCELER.items() if o == onay]},
            "degerlendirme": {"type": "string"},
        },
        "required": ["gerekce", "degerlendirme"],
    }


# KARAR adımında model bu gerekçeleri, önerilen şey mevcut yöntemi iyileştirse bile sık
# seçiyor. Bu gerekçeler seçilince, örnek ve kural göstermeden tek bir soru sorulur;
# cevap "Hayır" ise karar "Öneri"ye çevrilir.
KONTROL_SORULARI = {
    "Rutin iş": (
        "Önerilen şey yalnızca bozulan, aşınan, kirlenen ya da eksilen bir şeyi eski hâline "
        "getirmekten mi ibaret (tamir, temizlik, aynısıyla yenileme, periyodik kontrol veya "
        "kalibrasyon, zaten var olan bir kurala uyulması)? Mevcut yöntemi, parametreyi, "
        "malzemeyi, ekipmanı ya da tasarımı değiştirerek daha iyi hâle getiriyor ya da yeni bir "
        "şey yapıyorsa cevap Hayır'dır."
    ),
    "Politika/sosyal hak talebi": (
        "Önerinin asıl faydası çalışanların kişisel yararına olan bir hak, imkân, ikram ya da "
        "hediye mi (ödül, prim, izin, yemek, içecek, servis, sosyal etkinlik, kişisel eşya)? "
        "Asıl faydası işe, sürece, maliyete, çevreye, kaliteye ya da güvenliğe ise cevap Hayır'dır."
    ),
}

# Önerilen durum bundan kısaysa (boş, "-" gibi) kontrol yapılmaz: yazılı bir çözüm yokken
# karar "Öneri"ye çevrilmez.
KONTROL_EN_KISA_ONERILEN = 10


def kontrol_semasi() -> dict:
    """Kontrol sorusu. Model önce kısa gerekçesini yazar, sonra Evet/Hayır der."""
    return {
        "type": "object",
        "properties": {
            "aciklama": {"type": "string"},
            "cevap": {"type": "string", "enum": ["Evet", "Hayır"]},
        },
        "required": ["aciklama", "cevap"],
    }


KONTROL_SISTEMI = (
    "Sen bir fabrikanın öneri sistemi ekibine yardım eden bir asistansın. Bir çalışan önerisi "
    "hakkındaki soruyu yalnızca önerilen duruma bakarak cevapla. Önce tek cümleyle açıkla, "
    'sonra "Evet" ya da "Hayır" de. Cevabı yalnızca istenen JSON biçiminde ver.'
)


def kontrol_mesaji(yeni: Oneri, gerekce: str) -> str:
    return "\n".join(
        (
            "ÖNERİ",
            _oneri_blogu(yeni),
            "",
            f"SORU: {KONTROL_SORULARI[gerekce]}",
            "",
            'Cevabı JSON olarak ver: {"aciklama": "...", "cevap": "Evet" ya da "Hayır"}',
        )
    )


_SISTEM = f"""Sen bir fabrikanın öneri sistemi ekibine yardım eden bir asistansın. Çalışanların gönderdiği iyileştirme önerileri için taslak değerlendirme yazarsın; son kararı ekip verir.

Ekip gibi bak: önce önerinin sağlayabileceği faydayı ve amacını gör, sonra kararını ver. Öneri sahibini eleştiren ya da eksik arayan bir dil kullanma. Ekibin benzer önerilerde yazdığı değerlendirmeler sana nasıl düşündüklerini gösterir; onlara göre davran.

Bir öneri iki adımda değerlendirilir:
- KARAR adımında "Önerilen durum"un ne yapmayı önerdiğini tek cümleyle yazarsın (onerilen_sey) ve aşağıdaki kurallara göre gerekçeyi seçersin: {", ".join(f'"{g}"' for g in GEREKCELER)}. Karar mevcut duruma değil, önerilen şeye göre verilir. "Geçerli öneri" dışındaki her gerekçe "{ONERI_DEGIL}" demektir.
- METİN adımında karar bellidir. Ekibin değerlendirmeleri gibi sade ve kısa, iki cümlelik bir değerlendirme yazarsın. "{ONERI}" ise önce önerinin sağlayabileceği faydayı, sonra ilerlemesi için gereken en fazla 2-3 şeyi yaz. "{ONERI_DEGIL}" ise nedenini ve öneriye dönüşmesi için ne gerektiğini ya da konuyu hangi birimin ele alması gerektiğini yaz. Önerinin kendi içeriğinden (makine, malzeme, süreç adı) somut olarak bahset. "Ayrıca" ile üçüncü bir cümle ekleme; "Öneri niteliğindedir" gibi genel bir girişle başlama.

Cevabı yalnızca istenen JSON biçiminde ver.

KURALLAR

"""

# Uzun öneri metinleri talimatı şişirmesin diye kısaltılır.
_EN_UZUN_ALAN = 400


def sistem_mesaji(kurallar: str) -> str:
    return _SISTEM + kurallar.strip()


def karar_mesaji(yeni: Oneri, ornekler: list[Ornek]) -> str:
    return _mesaj(
        yeni,
        ornekler,
        'KARAR adımı: bu öneri için önerilen şeyi ve gerekçeni JSON olarak ver: {"onerilen_sey": "...", "gerekce": "..."}',
    )


def metin_mesaji(yeni: Oneri, ornekler: list[Ornek], onay: str) -> str:
    return _mesaj(
        yeni,
        ornekler,
        f'METİN adımı: bu önerinin kararı "{onay}" olarak belirlendi. Bu karara uyan gerekçeyi seç ve '
        'değerlendirme metnini JSON olarak ver: {"gerekce": "...", "degerlendirme": "..."}',
    )


def _mesaj(yeni: Oneri, ornekler: list[Ornek], istek: str) -> str:
    """Örnekler en benzerden başlayarak verilmeli; en benzer olan yeni önerinin hemen üstüne gelir."""
    parcalar = ["EKİBİN BENZER ÖNERİLERDEKİ KARARLARI VE DEĞERLENDİRMELERİ", ""]
    # Küçük modeller en son okuduklarına daha çok ağırlık verir; en benzer örnek en sona.
    for ornek in reversed(ornekler):
        parcalar += [
            _oneri_blogu(ornek.oneri),
            f"Karar: {ornek.oneri.onay_durumu}",
            f"Değerlendirme: {ornek.oneri.degerlendirme}",
            "",
        ]
    parcalar += ["YENİ ÖNERİ", _oneri_blogu(yeni), "", istek]
    return "\n".join(parcalar)


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
