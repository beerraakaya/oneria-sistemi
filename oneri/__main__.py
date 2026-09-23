"""Komut satırı: python -m oneri <komut>"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .ayarlar import Ayarlar, ayarlari_yukle
from .excel import ExcelHatasi
from .hafiza import ornek_alinabilir_mi, ozgun_satirlar
from .kor_test import kor_test_calistir, ozetle, rapor_yaz
from .ollama import Ollama, OllamaHatasi, model_yuklu_mu
from .uygulama import asistani_kur, fabrika_onerileri


def kontrol(ayarlar: Ayarlar, _args) -> int:
    """Excel'i, kurallar dosyasını ve Ollama modellerini kontrol eder."""
    print(f"Excel: {ayarlar.excel_yolu} ({ayarlar.sayfa_adi} sayfası)")
    oneriler = fabrika_onerileri(ayarlar)
    ornekler = [o for o in oneriler if ornek_alinabilir_mi(o, ayarlar.en_kisa_degerlendirme)]
    ozgun = ozgun_satirlar(ornekler, ayarlar.kalip_tekrar_esigi)
    bekleyen = [o.satir for o in oneriler if o.bekliyor]
    print(f"  {ayarlar.fabrika} önerisi: {len(oneriler)}")
    print(
        f"  Örnek alınabilecek değerlendirme: {len(ornekler)}"
        f" (yeni tarzda: {len(ozgun)}, eski kalıp: {len(ornekler) - len(ozgun)})"
    )
    print(
        f"  Değerlendirme bekleyen: {len(bekleyen)}"
        + (f" (satır {', '.join(map(str, bekleyen))})" if bekleyen else "")
    )

    sorun = False
    if ayarlar.kurallar_yolu.exists():
        print(f"Kurallar: {ayarlar.kurallar_yolu}")
    else:
        print(f"Kurallar: {ayarlar.kurallar_yolu} BULUNAMADI")
        sorun = True

    print(f"Ollama: {ayarlar.ollama_adresi}")
    yuklu = Ollama(ayarlar.ollama_adresi).yuklu_modeller()
    for model in (ayarlar.dil_modeli, ayarlar.gomme_modeli):
        if model_yuklu_mu(model, yuklu):
            print(f"  {model}: yüklü")
        else:
            print(f"  {model}: YÜKLÜ DEĞİL -> ollama pull {model}")
            sorun = True

    print("\nHer şey hazır." if not sorun else "\nYukarıdaki eksikleri giderin.")
    return 1 if sorun else 0


def kor_test(ayarlar: Ayarlar, args) -> int:
    """Yeni tarzda değerlendirilmiş önerileri cevapları gizleyerek yeniden değerlendirir."""
    print("Hafıza hazırlanıyor (ilk çalıştırmada birkaç dakika sürebilir)...")
    asistan = asistani_kur(ayarlar, Ollama(ayarlar.ollama_adresi))
    try:
        test = sorted((o.oneri for o in asistan.hafiza.ornekler if o.ozgun), key=lambda o: o.satir)
        if args.adet:
            test = test[-args.adet :]
        print(f"{len(test)} öneri değerlendirilecek. Model: {ayarlar.dil_modeli}\n")
        sonuclar = kor_test_calistir(asistan.degerlendirici, test)
    finally:
        asistan.kapat()

    yol = ayarlar.veri_klasoru / f"kor_test_{datetime.now():%Y%m%d_%H%M}.xlsx"
    rapor_yaz(sonuclar, yol, ayarlar)
    ozet = ozetle(sonuclar)
    print(f"\nEkiple aynı karar: {ozet.ayni_karar} / {ozet.cevaplanan} (%{ozet.oran:.0f})")
    print(f"Rapor: {yol}")
    if len(sonuclar) < len(test):
        print(f"Dikkat: {len(test)} önerinin sadece {len(sonuclar)} tanesi test edildi.")
        return 1
    return 0


def degerlendir(ayarlar: Ayarlar, args) -> int:
    """Tek bir satır için taslak üretir ve ekrana yazar; Excel'e dokunmaz."""
    asistan = asistani_kur(ayarlar, Ollama(ayarlar.ollama_adresi))
    try:
        oneri = next((o for o in asistan.oneriler if o.satir == args.satir), None)
        if oneri is None:
            raise ExcelHatasi(f"{args.satir}. satırda {ayarlar.fabrika} önerisi yok.")
        # Satır zaten değerlendirilmişse kendi cevabını örnek olarak görmesin.
        taslak = asistan.degerlendirici.degerlendir(oneri, haric_satir=oneri.satir)
    finally:
        asistan.kapat()

    print(f"Satır {oneri.satir} - {oneri.konu}\n")
    print("Yapay zekânın taslağı")
    print(f"  Onay Durumu  : {taslak.onay_durumu}")
    print(f"  Durum        : {taslak.durum}")
    print(f"  Değerlendirme: {taslak.degerlendirme}")
    if not oneri.bekliyor:
        print("\nEkibin yazdığı")
        print(f"  Onay Durumu  : {oneri.onay_durumu}")
        print(f"  Durum        : {oneri.durum}")
        print(f"  Değerlendirme: {oneri.degerlendirme}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(
        prog="python -m oneri", description="Öneri sistemi yapay zekâ asistanı"
    )
    ayristirici.add_argument(
        "--ayarlar", type=Path, default=Path("ayarlar.toml"), help="ayar dosyası (varsayılan: ayarlar.toml)"
    )
    komutlar = ayristirici.add_subparsers(dest="komut", required=True)
    komutlar.add_parser("kontrol", help="Excel'i, kuralları ve Ollama modellerini kontrol eder")
    kor = komutlar.add_parser("kor-test", help="cevabı bilinen önerilerle kör test yapıp rapor üretir")
    kor.add_argument("--adet", type=int, help="sadece en yeni N öneriyle dene")
    tek = komutlar.add_parser("degerlendir", help="tek bir Excel satırı için taslak üretir")
    tek.add_argument("satir", type=int, help="Excel'deki satır numarası")
    args = ayristirici.parse_args(argv)

    calistir = {"kontrol": kontrol, "kor-test": kor_test, "degerlendir": degerlendir}[args.komut]
    try:
        return calistir(ayarlari_yukle(args.ayarlar), args)
    except (ExcelHatasi, OllamaHatasi, OSError, ValueError) as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
