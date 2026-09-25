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
    # Modelin bir cevapta yazabileceği en fazla token. Sınır yoksa model döngüye girip
    # dakikalarca aynı şeyi yazabiliyor; normal bir cevap 300 tokeni geçmiyor.
    en_fazla_token: int = 800

    # Model "Rutin iş" ya da "Politika/sosyal hak talebi" seçince kısa bir kontrol sorusuyla
    # doğrulanır; doğrulanmazsa karar "Öneri" olur. false yapılırsa kontrol atlanır.
    red_kontrolu: bool = True

    # Modele gösterilen, ekibin kendi yazdığı en benzer değerlendirme sayısı.
    ornek_sayisi: int = 8
    # 'kor-test --yontem komsu' için oylamaya katılan benzer öneri sayısı (tek sayı olmalı).
    komsu_sayisi: int = 7
    # Karma yöntemde: benzer önerilerden en az bu kadarı aynı kararı gösteriyorsa karar onlardan alınır.
    karma_esigi: int = 5
    # Bundan kısa değerlendirmeler ("deneme" gibi test kayıtları) örnek alınmaz.
    en_kisa_degerlendirme: int = 40
    # İlk cümlesi bu kadar kayıtta aynen geçen metin eski kalıp metin sayılır.
    kalip_tekrar_esigi: int = 3

    # --- Canlı kullanım ---
    # SharePoint'teki öneri Excel'inin adresi. Boşsa excel_yolu'ndaki dosya kullanılır
    # (denemek için: bilgisayardaki bir kopyaya yazar).
    sharepoint_dosya_adresi: str = ""
    # SharePoint'e nasıl yazılacağı:
    #   'graph': IT'nin Microsoft Entra'da verdiği uygulama izniyle (aşağıdaki graph_ ayarları).
    #   'excel': bilgisayardaki Excel uygulamasıyla, Excel'de oturum açmış hesabın yetkisiyle.
    yazma_yontemi: str = "graph"
    # IT'nin Microsoft Entra'da (Azure AD) açtığı uygulamanın bilgileri.
    graph_kiraci: str = ""  # Directory (tenant) ID
    graph_uygulama: str = ""  # Application (client) ID
    # Uygulamanın gizli anahtarı. Dosyaya yazmak yerine ONERI_GRAPH_SIRRI ortam
    # değişkeninde tutulması önerilir.
    graph_sirri: str = ""
    # Yapay zekânın yazdığı ve bu kadar gün değiştirilmeyen taslak onaylanmış sayılır.
    onay_gun_sayisi: int = 7
    # Bir çalışmada en fazla bu kadar öneri doldurulur; kalanlar sonraki çalışmaya kalır.
    en_fazla_oneri: int = 20
    # Kontrol bekleyen taslak hücrelerinin dolgu rengi; ekip onaylayınca ya da
    # düzeltince renk kaldırılır. Boş bırakılırsa hücreler boyanmaz.
    taslak_rengi: str = "#FFF2CC"

    @property
    def hafiza_yolu(self) -> Path:
        return self.veri_klasoru / "hafiza.db"

    @property
    def taslak_yolu(self) -> Path:
        return self.veri_klasoru / "taslaklar.db"


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
