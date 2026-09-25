"""Parçaları bir araya getirir: Excel -> hafıza -> değerlendirici."""

import os
from collections.abc import Collection
from dataclasses import dataclass, replace

from .ayarlar import Ayarlar
from .degerlendirici import Degerlendirici
from .excel import Oneri, onerileri_oku
from .hafiza import Hafiza, VektorOnbellegi, ornek_alinabilir_mi
from .kaynak import ExcelKaynagi, ExcelUygulamasi, SharePointExcel, YerelExcel
from .ollama import Ollama


def kaynagi_hazirla(ayarlar: Ayarlar) -> tuple[ExcelKaynagi, Ayarlar]:
    """Excel'e erişimi kurar. SharePoint ayarlıysa dosyanın güncel hâli veri klasörüne
    indirilir ve döndürülen ayarlardaki excel_yolu o kopyayı gösterir.

    İş bitince kaynak.kapat() çağrılmalıdır (Excel yönteminde Excel'i kapatır)."""
    if not ayarlar.sharepoint_dosya_adresi:
        return YerelExcel(ayarlar.excel_yolu), ayarlar
    if ayarlar.yazma_yontemi == "excel":
        kaynak = ExcelUygulamasi(ayarlar.sharepoint_dosya_adresi)
    elif ayarlar.yazma_yontemi == "graph":
        kaynak = _graph_kaynagi(ayarlar)
    else:
        raise ValueError(
            f"yazma_yontemi '{ayarlar.yazma_yontemi}' olamaz; 'graph' ya da 'excel' yazın."
        )
    try:
        yol = kaynak.indir(ayarlar.veri_klasoru / "sharepoint_kopya.xlsx")
    except BaseException:
        kaynak.kapat()
        raise
    return kaynak, replace(ayarlar, excel_yolu=yol)


def _graph_kaynagi(ayarlar: Ayarlar) -> SharePointExcel:
    sir = os.environ.get("ONERI_GRAPH_SIRRI") or ayarlar.graph_sirri
    eksik = [
        ad
        for ad, deger in (
            ("graph_kiraci", ayarlar.graph_kiraci),
            ("graph_uygulama", ayarlar.graph_uygulama),
            ("ONERI_GRAPH_SIRRI (gizli anahtar)", sir),
        )
        if not deger
    ]
    if eksik:
        raise ValueError(f"SharePoint için eksik ayar: {', '.join(eksik)}")
    return SharePointExcel(
        ayarlar.sharepoint_dosya_adresi, ayarlar.graph_kiraci, ayarlar.graph_uygulama, sir
    )


def fabrika_onerileri(ayarlar: Ayarlar) -> list[Oneri]:
    """Excel'deki önerilerden yalnızca ayarlardaki fabrikaya ait olanlar."""
    return [
        oneri
        for oneri in onerileri_oku(ayarlar.excel_yolu, ayarlar.sayfa_adi)
        if oneri.fabrika.casefold() == ayarlar.fabrika.casefold()
    ]


@dataclass
class Asistan:
    oneriler: list[Oneri]
    hafiza: Hafiza
    degerlendirici: Degerlendirici
    _onbellek: VektorOnbellegi

    def kapat(self) -> None:
        self._onbellek.kapat()


def asistani_kur(
    ayarlar: Ayarlar,
    ollama: Ollama,
    oneriler: list[Oneri] | None = None,
    haric_satirlar: Collection[int] = (),
) -> Asistan:
    """`haric_satirlar`: örnek alınmayacak satırlar (ekibin henüz kontrol etmediği taslaklar)."""
    if oneriler is None:
        oneriler = fabrika_onerileri(ayarlar)
    kurallar = ayarlar.kurallar_yolu.read_text(encoding="utf-8")
    onbellek = VektorOnbellegi(
        ayarlar.hafiza_yolu,
        ayarlar.gomme_modeli,
        lambda metinler: ollama.gom(ayarlar.gomme_modeli, metinler),
    )
    try:
        hafiza = Hafiza.olustur(
            [
                o
                for o in oneriler
                if ornek_alinabilir_mi(o, ayarlar.en_kisa_degerlendirme)
                and o.satir not in haric_satirlar
            ],
            onbellek,
            ayarlar.kalip_tekrar_esigi,
        )
    except BaseException:
        onbellek.kapat()
        raise
    return Asistan(oneriler, hafiza, Degerlendirici(hafiza, ollama, ayarlar, kurallar), onbellek)
