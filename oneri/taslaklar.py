"""Yapay zekânın Excel'e yazdığı taslakların kaydı ve 7 gün kuralının sonuçları.

Bu kayıt sayesinde:
- Ekibin henüz kontrol etmediği taslaklar yapay zekâya örnek olarak gösterilmez.
- Taslağın değiştirilmeden mi onaylandığı, yoksa ekibin düzelttiği mi ölçülür.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .degerlendirici import Taslak
from .excel import Oneri, sade_metin

ONAYLANDI = "onaylandi"  # onay_gun_sayisi boyunca değiştirilmedi
DUZELTILDI = "duzeltildi"  # ekip Değerlendirme'yi ya da Onay Durumu'nu değiştirdi
SILINDI = "silindi"  # satır Excel'de artık bulunamıyor


@dataclass(frozen=True)
class KayitliTaslak:
    anahtar: str
    satir: int
    konu: str
    degerlendirme: str
    onay_durumu: str
    durum: str
    gerekce: str
    yazilma: datetime
    sonuc: str | None = None  # None: ekip henüz kontrol etmedi
    sonuc_tarihi: datetime | None = None
    ekip_degerlendirme: str = ""
    ekip_onay_durumu: str = ""


_ALANLAR = [
    "anahtar", "satir", "konu", "degerlendirme", "onay_durumu", "durum", "gerekce", "yazilma",
    "sonuc", "sonuc_tarihi", "ekip_degerlendirme", "ekip_onay_durumu",
]


class TaslakDeposu:
    def __init__(self, yol: Path):
        yol.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(yol)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS taslaklar ("
            " anahtar TEXT PRIMARY KEY, satir INTEGER NOT NULL, konu TEXT NOT NULL,"
            " degerlendirme TEXT NOT NULL, onay_durumu TEXT NOT NULL, durum TEXT NOT NULL,"
            " gerekce TEXT NOT NULL, yazilma TEXT NOT NULL, sonuc TEXT, sonuc_tarihi TEXT,"
            " ekip_degerlendirme TEXT NOT NULL DEFAULT '', ekip_onay_durumu TEXT NOT NULL DEFAULT '')"
        )

    def kaydet(self, oneri: Oneri, taslak: Taslak, zaman: datetime) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO taslaklar (anahtar, satir, konu, degerlendirme, onay_durumu,"
            " durum, gerekce, yazilma) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                oneri.anahtar,
                oneri.satir,
                oneri.konu,
                sade_metin(taslak.degerlendirme),
                taslak.onay_durumu,
                taslak.durum,
                taslak.gerekce,
                zaman.isoformat(timespec="seconds"),
            ),
        )
        self._db.commit()

    def sonuclandir(
        self, anahtar: str, sonuc: str, zaman: datetime, guncel: Oneri | None = None
    ) -> None:
        self._db.execute(
            "UPDATE taslaklar SET sonuc = ?, sonuc_tarihi = ?, ekip_degerlendirme = ?,"
            " ekip_onay_durumu = ? WHERE anahtar = ?",
            (
                sonuc,
                zaman.isoformat(timespec="seconds"),
                guncel.degerlendirme if guncel else "",
                guncel.onay_durumu if guncel else "",
                anahtar,
            ),
        )
        self._db.commit()

    def hepsi(self) -> list[KayitliTaslak]:
        kayitlar = self._db.execute(
            f"SELECT {', '.join(_ALANLAR)} FROM taslaklar ORDER BY yazilma, satir"
        ).fetchall()
        return [_taslak(kayit) for kayit in kayitlar]

    def bekleyenler(self) -> list[KayitliTaslak]:
        """Ekibin henüz kontrol etmediği (sonucu belli olmayan) taslaklar."""
        return [t for t in self.hepsi() if t.sonuc is None]

    def anahtarlar(self) -> set[str]:
        return {kayit[0] for kayit in self._db.execute("SELECT anahtar FROM taslaklar")}

    def kapat(self) -> None:
        self._db.close()


def _taslak(kayit: tuple) -> KayitliTaslak:
    degerler = dict(zip(_ALANLAR, kayit, strict=True))
    degerler["yazilma"] = datetime.fromisoformat(degerler["yazilma"])
    if degerler["sonuc_tarihi"]:
        degerler["sonuc_tarihi"] = datetime.fromisoformat(degerler["sonuc_tarihi"])
    return KayitliTaslak(**degerler)
