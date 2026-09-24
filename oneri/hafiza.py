"""Kurumsal hafıza: ekibin geçmiş değerlendirmeleri ve benzer öneri araması."""

import hashlib
import math
import re
import sqlite3
from array import array
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .excel import BASLANGIC_DURUMU, Oneri

# Metin listesi alıp her metin için bir anlam vektörü döndüren fonksiyon.
Gomucu = Callable[[list[str]], list[list[float]]]


def ornek_alinabilir_mi(oneri: Oneri, en_kisa_degerlendirme: int) -> bool:
    """Kararı ve yeterince uzun bir değerlendirme metni olan öneriler örnek alınır.

    Uzunluk sınırı "deneme" gibi test kayıtlarını dışarıda bırakır.
    """
    return (
        oneri.onay_durumu in BASLANGIC_DURUMU
        and len(oneri.degerlendirme) >= en_kisa_degerlendirme
    )


def ilk_cumle(metin: str) -> str:
    eslesme = re.match(r"(.+?[.;!?])(?:\s|$)", metin)
    return (eslesme.group(1) if eslesme else metin).strip()


def ozgun_satirlar(oneriler: Sequence[Oneri], kalip_tekrar_esigi: int) -> set[int]:
    """Değerlendirmesi eski kalıp cümlelerden biri olmayan önerilerin satır numaraları.

    İlk cümlesi en az `kalip_tekrar_esigi` kayıtta aynen geçen metin kalıp sayılır.
    """
    tekrar = Counter(ilk_cumle(o.degerlendirme) for o in oneriler)
    return {o.satir for o in oneriler if tekrar[ilk_cumle(o.degerlendirme)] < kalip_tekrar_esigi}


class VektorOnbellegi:
    """Her metnin vektörünü bir kez hesaplatır ve SQLite dosyasında saklar."""

    def __init__(self, yol: Path, model: str, gomucu: Gomucu, parca_boyu: int = 32):
        yol.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(yol)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS vektorler ("
            " model TEXT NOT NULL, ozet TEXT NOT NULL, vektor BLOB NOT NULL,"
            " PRIMARY KEY (model, ozet))"
        )
        self._model = model
        self._gomucu = gomucu
        self._parca_boyu = parca_boyu

    def vektorler(self, metinler: Sequence[str]) -> list[tuple[float, ...]]:
        ozetler = [hashlib.sha256(metin.encode("utf-8")).hexdigest() for metin in metinler]
        bilinen = {}
        for ozet in set(ozetler):
            kayit = self._db.execute(
                "SELECT vektor FROM vektorler WHERE model = ? AND ozet = ?", (self._model, ozet)
            ).fetchone()
            if kayit:
                bilinen[ozet] = tuple(array("f", kayit[0]))

        eksik = list({o: m for o, m in zip(ozetler, metinler) if o not in bilinen}.items())
        for bas in range(0, len(eksik), self._parca_boyu):
            parca = eksik[bas : bas + self._parca_boyu]
            yeni = self._gomucu([metin for _, metin in parca])
            for (ozet, _), vektor in zip(parca, yeni, strict=True):
                bilinen[ozet] = tuple(vektor)
                self._db.execute(
                    "INSERT OR REPLACE INTO vektorler VALUES (?, ?, ?)",
                    (self._model, ozet, array("f", vektor).tobytes()),
                )
            self._db.commit()
        return [bilinen[ozet] for ozet in ozetler]

    def kapat(self) -> None:
        self._db.close()


@dataclass(frozen=True)
class Ornek:
    oneri: Oneri
    ozgun: bool  # False ise değerlendirme eski kalıp cümlelerle yazılmış
    vektor: tuple[float, ...]


class Hafiza:
    def __init__(self, ornekler: list[Ornek], onbellek: VektorOnbellegi):
        self.ornekler = ornekler
        self._onbellek = onbellek

    @classmethod
    def olustur(
        cls, oneriler: Sequence[Oneri], onbellek: VektorOnbellegi, kalip_tekrar_esigi: int
    ) -> "Hafiza":
        """`oneriler` örnek alınabilir önerilerdir."""
        ozgun = ozgun_satirlar(oneriler, kalip_tekrar_esigi)
        vektorler = onbellek.vektorler([o.arama_metni() for o in oneriler])
        ornekler = [
            Ornek(oneri, oneri.satir in ozgun, _birim(vektor))
            for oneri, vektor in zip(oneriler, vektorler, strict=True)
        ]
        return cls(ornekler, onbellek)

    def benzerler(
        self,
        oneri: Oneri,
        adet: int,
        *,
        sadece_ozgun: bool = False,
        haric_satir: int | None = None,
    ) -> list[Ornek]:
        """En benzerden başlayarak en fazla `adet` örnek döndürür."""
        sorgu = _birim(self._onbellek.vektorler([oneri.arama_metni()])[0])
        adaylar = [
            ornek
            for ornek in self.ornekler
            if (ornek.ozgun or not sadece_ozgun) and ornek.oneri.satir != haric_satir
        ]
        adaylar.sort(key=lambda ornek: _ic_carpim(sorgu, ornek.vektor), reverse=True)
        return adaylar[:adet]


def _birim(vektor: Sequence[float]) -> tuple[float, ...]:
    uzunluk = math.sqrt(sum(x * x for x in vektor)) or 1.0
    return tuple(x / uzunluk for x in vektor)


def _ic_carpim(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
