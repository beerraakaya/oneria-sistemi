"""Canlı kullanım: bekleyen önerileri doldurur ve önceki taslaklara 7 gün kuralını uygular.

Her çalışmada:
1. Daha önce yazılan taslaklara bakılır: ekip Değerlendirme'yi ya da Onay Durumu'nu
   değiştirdiyse "düzeltildi", onay_gun_sayisi boyunca değiştirmediyse "onaylandı" sayılır.
   Durum'un sonradan Tamamlandı/Uygulanamaz yapılması düzeltme sayılmaz; süreç ilerlemesidir.
2. Değerlendirme, Onay Durumu ve Durum hücrelerinin üçü de boş olan satırlar doldurulur.
   Yazmadan hemen önce satır yeniden okunur; öneri değişmişse ya da biri o arada bir şey
   yazmışsa satıra dokunulmaz.

Bilgisayar kapalıyken gelen öneriler kaybolmaz: program "hangi satır boş" diye baktığı için
açıldığında biriken hepsini doldurur.
"""

import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl.utils import column_index_from_string

from .ayarlar import Ayarlar
from .excel import Oneri, sade_metin, sutun_harfleri
from .kaynak import ExcelKaynagi
from .ollama import GecersizCevap, Ollama
from .taslaklar import DUZELTILDI, ONAYLANDI, SILINDI, TaslakDeposu
from .uygulama import asistani_kur, fabrika_onerileri

# Yazılan hücreler ve karşılaştırmada kullanılan öneri alanları.
YAZILAN_ALANLAR = ("degerlendirme", "onay_durumu", "durum")
KIMLIK_ALANLARI = ("konu", "mevcut_durum", "onerilen_durum")


@dataclass
class CalismaOzeti:
    yazilan: int = 0
    atlanan: int = 0
    hatali: int = 0
    onaylanan: int = 0
    duzeltilen: int = 0
    silinen: int = 0
    kalan: int = 0  # en_fazla_oneri sınırı yüzünden sonraki çalışmaya kalan


class CalismaSuruyor(RuntimeError):
    """Önceki çalışma henüz bitmedi."""


@contextmanager
def tek_calisma(klasor: Path, eskime_saniyesi: float = 3 * 3600) -> Iterator[None]:
    """Zamanlayıcı yeni çalışmayı başlattığında önceki hâlâ sürüyorsa ikisi aynı anda yazmasın."""
    klasor.mkdir(parents=True, exist_ok=True)
    kilit = klasor / "calisiyor.kilit"
    try:
        tanitici = os.open(kilit, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            sahibi = int(kilit.read_text().strip() or 0)
        except (OSError, ValueError):
            sahibi = 0
        yeni = time.time() - kilit.stat().st_mtime < eskime_saniyesi
        if yeni and _surec_calisiyor(sahibi):
            raise CalismaSuruyor(f"Önceki çalışma sürüyor ({kilit}).") from None
        # Kilidi bırakan program artık çalışmıyor: bilgisayar kapanmış, pencere kapatılmış
        # ya da program zorla sonlandırılmış. Kilit kalmıştır, temizlenir.
        kilit.unlink(missing_ok=True)
        tanitici = os.open(kilit, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(tanitici, str(os.getpid()).encode())
        os.close(tanitici)
        yield
    finally:
        kilit.unlink(missing_ok=True)


def _surec_calisiyor(pid: int) -> bool:
    """Bu numaralı program hâlâ çalışıyor mu?"""
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows'ta os.kill programı sonlandırır; bu yüzden yalnızca durumu sorulur.
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        tanitici = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not tanitici:
            return False
        try:
            kod = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(tanitici, ctypes.byref(kod)):
                return True
            return kod.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(tanitici)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except (OSError, OverflowError):
        return False
    return True


def calistir(
    ayarlar: Ayarlar,
    kaynak: ExcelKaynagi,
    ollama: Ollama,
    depo: TaslakDeposu,
    simdi: datetime,
    *,
    deneme: bool = False,
    yaz: Callable[[str], None] = print,
) -> CalismaOzeti:
    """`deneme` True ise Excel'e ve kayda hiçbir şey yazılmaz; taslaklar yalnızca ekrana yazılır."""
    ozet = CalismaOzeti()
    oneriler = fabrika_onerileri(ayarlar)
    harf = sutun_harfleri(ayarlar.excel_yolu, ayarlar.sayfa_adi)
    sayfa = ayarlar.sayfa_adi

    def hucreler(satir: int) -> list[str]:
        return [f"{harf[alan]}{satir}" for alan in YAZILAN_ALANLAR]

    def boya(satir: int, renk: str | None) -> None:
        if not ayarlar.taslak_rengi:
            return
        try:
            kaynak.boya(sayfa, hucreler(satir), renk)
        except Exception as hata:  # renk yalnızca görsel bir işaret; yazmayı engellemez
            yaz(f"  uyarı: satır {satir} renklendirilemedi: {hata}")

    # 1. Önceki taslaklar: ekip kontrol etti mi?
    satirlar: dict[str, Oneri] = {}
    for oneri in oneriler:
        satirlar.setdefault(oneri.anahtar, oneri)
    kontrol_bekleyen: set[str] = set()
    for taslak in depo.bekleyenler():
        guncel = satirlar.get(taslak.anahtar)
        if guncel is None:
            sonuc = SILINDI
        elif (guncel.degerlendirme, guncel.onay_durumu) != (taslak.degerlendirme, taslak.onay_durumu):
            sonuc = DUZELTILDI
        elif simdi - taslak.yazilma >= timedelta(days=ayarlar.onay_gun_sayisi):
            sonuc = ONAYLANDI
        else:
            kontrol_bekleyen.add(taslak.anahtar)
            continue

        if sonuc == ONAYLANDI:
            ozet.onaylanan += 1
            yaz(f"Satır {guncel.satir}: {ayarlar.onay_gun_sayisi} gündür değiştirilmedi, onaylandı sayıldı.")
        elif sonuc == DUZELTILDI:
            ozet.duzeltilen += 1
            yaz(f"Satır {guncel.satir}: ekip taslağı düzeltti; düzeltilmiş hâli örnek alınacak.")
        else:
            ozet.silinen += 1
            yaz(f"Satır {taslak.satir} ({taslak.konu}) Excel'de bulunamadı.")
        if not deneme:
            depo.sonuclandir(taslak.anahtar, sonuc, simdi, guncel)
            if guncel is not None:
                boya(guncel.satir, None)

    # 2. Boş satırları doldur.
    yazilmis = depo.anahtarlar()
    doldurulacak = [o for o in oneriler if o.bekliyor and o.anahtar not in yazilmis]
    ozet.kalan = max(0, len(doldurulacak) - ayarlar.en_fazla_oneri)
    doldurulacak = doldurulacak[: ayarlar.en_fazla_oneri]
    if not doldurulacak:
        yaz("Doldurulacak yeni öneri yok.")
        return ozet

    yaz(f"{len(doldurulacak)} öneri doldurulacak. Hafıza hazırlanıyor...")
    # Ekibin henüz kontrol etmediği taslaklar örnek alınmaz; yapay zekâ kendi
    # yazdıklarından değil, ekibin yazdıklarından öğrenir.
    haric = {o.satir for o in oneriler if o.anahtar in kontrol_bekleyen}
    asistan = asistani_kur(ayarlar, ollama, oneriler, haric)
    try:
        sutun_sayisi = max(column_index_from_string(h) for h in harf.values())
        for sira, oneri in enumerate(doldurulacak, start=1):
            yaz(f"[{sira}/{len(doldurulacak)}] Satır {oneri.satir} değerlendiriliyor...")
            baslangic = time.monotonic()
            try:
                taslak = asistan.degerlendirici.degerlendir(oneri)
            except GecersizCevap as hata:
                ozet.hatali += 1
                yaz(f"Satır {oneri.satir}: taslak üretilemedi, sonraki çalışmada tekrar denenecek. ({hata})")
                continue

            if deneme:
                yaz(
                    f"Satır {oneri.satir} ({oneri.konu}): {taslak.onay_durumu} / {taslak.durum}\n"
                    f"  {taslak.degerlendirme}\n  Gerekçe: {taslak.gerekce}"
                )
                continue

            guncel = kaynak.satir_oku(sayfa, oneri.satir, sutun_sayisi)
            if not _hala_bos_ve_ayni(guncel, oneri, harf):
                ozet.atlanan += 1
                yaz(f"Satır {oneri.satir}: bu arada değişmiş ya da doldurulmuş, dokunulmadı.")
                continue

            degerler = (taslak.degerlendirme, taslak.onay_durumu, taslak.durum)
            kaynak.yaz(sayfa, dict(zip(hucreler(oneri.satir), degerler, strict=True)))
            depo.kaydet(oneri, taslak, simdi)
            boya(oneri.satir, ayarlar.taslak_rengi)
            ozet.yazilan += 1
            yaz(
                f"Satır {oneri.satir} ({oneri.konu}): {taslak.onay_durumu} yazıldı."
                f" ({_sure(time.monotonic() - baslangic)})"
            )
    finally:
        asistan.kapat()
    return ozet


def _hala_bos_ve_ayni(hucreler: list, oneri: Oneri, harf: dict[str, str]) -> bool:
    def deger(alan: str) -> str:
        return sade_metin(hucreler[column_index_from_string(harf[alan]) - 1])

    ayni = all(deger(alan) == getattr(oneri, alan) for alan in KIMLIK_ALANLARI)
    return ayni and not any(deger(alan) for alan in YAZILAN_ALANLAR)


def _sure(saniye: float) -> str:
    dakika, saniye = divmod(round(saniye), 60)
    return f"{dakika} dk {saniye} sn" if dakika else f"{saniye} sn"
