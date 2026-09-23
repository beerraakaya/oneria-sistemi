"""Testlerde kullanılan uydurma veriler; gerçek şirket verisi değildir."""

import hashlib
import re
from datetime import datetime

BASLIKLAR = [
    "Tarih",
    "Önerinin Uygulanacağı Yeri Seçiniz",
    "Öneri Yapacak Kişi Sayısını Seçiniz",
    "Adı Soyadı",
    "Bölüm",
    "Adı Soyadı2",
    "Bölüm3",
    "Öneri Konusu",
    "Mevcut Durum (Problem), (Ne, Nerede, Neden, Etkisi Nedir?)",
    "Önerilen Durum (Açıklama,Bu kısımda mevcut durumu çözmek için önerinizi detaylı bir şekilde yazınız)",
    "Değerlendirme",
    "Onay Durumu",
    "Durum",
    "Öneri Sorumlusu",
]


def _kalip(ek: str) -> str:
    return f"Kayıt öneri niteliği taşımaktadır ve incelemeye devam edilecektir. İlerlemesi için {ek} netleştirilmelidir."


YENI_TARZ_OLUMLU = (
    "Yaya ve forklift trafiğini ayırmaya yönelik uygulanabilir bir güvenlik iyileştirmesidir. "
    "Uygulama öncesinde trafik akışı İSG birimiyle değerlendirilmeli ve işaretleme standardı belirlenmelidir."
)
YENI_TARZ_OLUMSUZ = (
    "Mevcut atık ayrıştırma uygulamasının parçası olan standart bir faaliyettir. "
    "Öneriye dönüşmesi için geri dönüşüm oranını ölçülebilir biçimde artıran yeni bir yöntem geliştirilmelidir."
)

# (satır no, değerler); isimler bilerek "Test Kişi" yazıldı, hiçbir çıktıda görünmemeli.
SATIRLAR = [
    (2, [datetime(2025, 3, 1), "Denizli", 1, "Test Kişi", "Üretim", None, None, "Enerji Verimliliği",
         "Kompresör hatlarında hava kaçağı var, sürekli basınç kaybı oluyor.",
         "Kaçak tespit cihazıyla aylık kontrol ve bağlantı elemanlarının değişimi.",
         _kalip("kaçak miktarı ve tasarruf"), "Öneri ", "Devam Ediyor", "Sorumlu Kişi"]),
    (3, ["2025-04-02T00:00:00+00:27", "Denizli", 2, "Test Kişi", "Bakım", "Test Kişi2", "Bakım",
         "Makine ve Süreç Verimlilik İyileştirme",
         "Bobin değişiminde makine uzun süre duruyor.",
         "Hızlı bağlantı aparatı kullanılması.",
         _kalip("duruş süresi ve aparat maliyeti"), "Öneri", "Tamamlandı", "Sorumlu Kişi"]),
    (4, ["2025-05-10T00:00:00+00:00", "Denizli", 1, "Test Kişi", "Lojistik", None, None,
         "Taşıma/Elleçleme İyileştirme",
         "Paletler depo içinde elle taşınıyor.",
         "Akülü transpalet kullanılması.",
         _kalip("taşıma süresi ve ekipman maliyeti"), "Öneri", "Devam Ediyor", "Sorumlu Kişi"]),
    (5, [datetime(2025, 6, 1), "Tuzla", 1, "Test Kişi", "Üretim", None, None, "Ambalaj İyileştirme",
         "Makaralar ambalajsız bekliyor.", "Streç film ile sarılması.",
         "İncelenecek, benzer bir çalışma var.", "Öneri Değil", "Red Edildi", "Sorumlu Kişi"]),
    (6, [datetime(2026, 7, 24), "Denizli", 1, "Test Kişi", "Üretim", None, None,
         "İş Güvenliği Risk Azaltma",
         "Forklift yolunda yaya geçidi işaretli değil.",
         "Zemine yaya geçidi çizgisi ve uyarı levhası konulması.",
         YENI_TARZ_OLUMLU, "Öneri", "Devam Ediyor", "Sorumlu Kişi"]),
    (7, [datetime(2026, 8, 5), "Denizli", 1, "Test Kişi", "Üretim", None, None,
         "Atık Yönetimi ve Geri Dönüşüm",
         "Atık kartonlar karışık toplanıyor.",
         "Kartonların ayrı toplanması.",
         YENI_TARZ_OLUMSUZ, "Öneri Değil", "Red Edildi", "Sorumlu Kişi"]),
    (8, ["2026-09-21T00:00:00+00:00", "Denizli", 1, "Test Kişi", "Ar-Ge", None, None,
         "Ambalaj İyileştirme", "deneme", "deneme", "denene", "Öneri Değil", "Red Edildi", "Sorumlu Kişi"]),
    (9, [datetime(2026, 9, 16), "Denizli", 4, "Test Kişi", "Üretim", "Test Kişi2", "Üretim",
         "İş Güvenliği Risk Azaltma",
         "Depo merdiveninin basamaklarındaki kaymaz bantlar eskimiş.",
         "Basamaklara yeni kaymaz bant yapıştırılması.",
         None, None, None, None]),
    (10, [None] * len(BASLIKLAR)),
]


def sahte_gomucu(metinler: list[str]) -> list[list[float]]:
    """Ortak kelimesi çok olan metinlere yakın vektörler üretir."""
    vektorler = []
    for metin in metinler:
        vektor = [0.0] * 64
        for kelime in re.findall(r"\w+", metin.casefold()):
            vektor[int(hashlib.md5(kelime.encode()).hexdigest(), 16) % 64] += 1.0
        vektorler.append(vektor)
    return vektorler
