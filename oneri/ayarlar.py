"""Program ayarları: koddaki varsayılanlar ve isteğe bağlı ayarlar.toml dosyası."""

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path


@dataclass(frozen=True)
class Ayarlar:
    excel_yolu: Path = Path("veri/oneri.xlsx")
    sayfa_adi: str = "Genel Tablo"
    # Sadece bu fabrikanın satırları okunur ve doldurulur.
    fabrika: str = "Denizli"
    kurallar_yolu: Path = Path("kurallar.md")
    # Hafıza dosyası ve raporlar buraya yazılır; git'e gönderilmez.
    veri_klasoru: Path = Path("veri")

    ollama_adresi: str = "http://localhost:11434"
    dil_modeli: str = "qwen2.5"
    gomme_modeli: str = "bge-m3"
    # Talimat + örnekler en fazla ~6-7 bin token tutuyor. Ollama sığmayan kısmı sessizce
    # kestiği için varsayılanı (2048-4096) yetmez.
    baglam_uzunlugu: int = 12288
    # 0: aynı talimata her seferinde aynı cevap; testler karşılaştırılabilir olur.
    sicaklik: float = 0.0
    tohum: int = 42

    # Karar için gösterilecek benzer geçmiş öneri sayısı.
    karar_ornegi_sayisi: int = 6
    # Yazım tarzı için gösterilecek yeni tarz örnek sayısı.
    tarz_ornegi_sayisi: int = 4
    # 'kor-test --yontem komsu' için oylamaya katılan benzer öneri sayısı (tek sayı olmalı).
    komsu_sayisi: int = 7
    # Bundan kısa değerlendirmeler ("deneme" gibi test kayıtları) örnek alınmaz.
    en_kisa_degerlendirme: int = 40
    # İlk cümlesi bu kadar kayıtta aynen geçen metin eski kalıp metin sayılır.
    kalip_tekrar_esigi: int = 3

    @property
    def hafiza_yolu(self) -> Path:
        return self.veri_klasoru / "hafiza.db"


def ayarlari_yukle(yol: Path) -> Ayarlar:
    """Dosya yoksa varsayılanları, varsa dosyadaki değerlerle güncellenmiş ayarları döndürür."""
    varsayilan = Ayarlar()
    if not yol.exists():
        return varsayilan
    with yol.open("rb") as dosya:
        degerler = tomllib.load(dosya)

    bilinen = {alan.name for alan in fields(Ayarlar)}
    bilinmeyen = sorted(set(degerler) - bilinen)
    if bilinmeyen:
        raise ValueError(f"{yol} içinde bilinmeyen ayar: {', '.join(bilinmeyen)}")

    for ad, deger in degerler.items():
        if isinstance(getattr(varsayilan, ad), Path):
            degerler[ad] = Path(deger)
    return replace(varsayilan, **degerler)
