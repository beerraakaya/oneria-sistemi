"""Komut satırı: python -m oneri <komut>"""

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from .ayarlar import Ayarlar, ayarlari_yukle
from .canli import CalismaSuruyor, calistir, tek_calisma
from .degerlendirici import KarmaDegerlendirici, KomsuDegerlendirici
from .excel import ExcelHatasi
from .hafiza import ornek_alinabilir_mi, ozgun_satirlar
from .kaynak import GraphHatasi
from .kor_test import kor_test_calistir, ozetle, rapor_yaz
from .ollama import Ollama, OllamaHatasi, model_yuklu_mu
from .taslaklar import DUZELTILDI, ONAYLANDI, SILINDI, TaslakDeposu
from .uygulama import asistani_kur, fabrika_onerileri, kaynagi_hazirla


def kontrol(ayarlar: Ayarlar, _args) -> int:
    """Excel'i, kurallar dosyasını ve Ollama modellerini kontrol eder."""
    kaynak, ayarlar = kaynagi_hazirla(ayarlar)
    kaynak.kapat()
    if ayarlar.sharepoint_dosya_adresi:
        yol = "Excel uygulaması" if ayarlar.yazma_yontemi == "excel" else "Microsoft Graph"
        print(f"SharePoint ({yol}): bağlandı, dosya okundu ({kaynak.ad})")
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
    kaynak, ayarlar = kaynagi_hazirla(ayarlar)
    kaynak.kapat()
    print("Hafıza hazırlanıyor (ilk çalıştırmada birkaç dakika sürebilir)...")
    oneriler = fabrika_onerileri(ayarlar)
    # Yapay zekânın yazıp ekibin düzeltmediği taslaklar test edilmez (kendi cevabını bulurdu);
    # henüz kontrol edilmemiş olanlar örnek de alınmaz.
    kendi, kontrolsuz = _yapay_zeka_satirlari(ayarlar, oneriler)
    asistan = asistani_kur(ayarlar, Ollama(ayarlar.ollama_adresi), oneriler, kontrolsuz)
    try:
        test = sorted(
            (o.oneri for o in asistan.hafiza.ornekler if o.ozgun and o.oneri.satir not in kendi),
            key=lambda o: o.satir,
        )
        if args.adet:
            test = test[-args.adet :]
        if args.yontem == "komsu":
            degerlendirici = KomsuDegerlendirici(asistan.hafiza, ayarlar.komsu_sayisi)
            print(
                f"{len(test)} öneri, benzer {ayarlar.komsu_sayisi} önerinin"
                " çoğunluk kararıyla değerlendirilecek.\n"
            )
        elif args.yontem == "karma":
            degerlendirici = KarmaDegerlendirici(
                asistan.hafiza, asistan.degerlendirici, ayarlar.komsu_sayisi, ayarlar.karma_esigi
            )
            print(f"{len(test)} öneri karma yöntemle değerlendirilecek. Model: {ayarlar.dil_modeli}\n")
        else:
            degerlendirici = asistan.degerlendirici
            print(f"{len(test)} öneri değerlendirilecek. Model: {ayarlar.dil_modeli}\n")
        sonuclar = kor_test_calistir(degerlendirici, test)
    finally:
        asistan.kapat()

    yol = ayarlar.veri_klasoru / f"kor_test_{args.yontem}_{datetime.now():%Y%m%d_%H%M}.xlsx"
    rapor_yaz(sonuclar, yol, ayarlar, args.yontem)
    ozet = ozetle(sonuclar)
    print(f"\nEkiple aynı karar: {ozet.ayni_karar} / {ozet.cevaplanan} (%{ozet.oran:.0f})")
    print(f"Rapor: {yol}")
    if len(sonuclar) < len(test):
        print(f"Dikkat: {len(test)} önerinin sadece {len(sonuclar)} tanesi test edildi.")
        return 1
    return 0


def degerlendir(ayarlar: Ayarlar, args) -> int:
    """Tek bir satır için taslak üretir ve ekrana yazar; Excel'e dokunmaz."""
    kaynak, ayarlar = kaynagi_hazirla(ayarlar)
    kaynak.kapat()
    oneriler = fabrika_onerileri(ayarlar)
    _, kontrolsuz = _yapay_zeka_satirlari(ayarlar, oneriler)
    asistan = asistani_kur(ayarlar, Ollama(ayarlar.ollama_adresi), oneriler, kontrolsuz)
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
    print(f"  Gerekçe      : {taslak.gerekce}")
    print(f"  Onay Durumu  : {taslak.onay_durumu}")
    print(f"  Durum        : {taslak.durum}")
    print(f"  Değerlendirme: {taslak.degerlendirme}")
    if not oneri.bekliyor:
        print("\nEkibin yazdığı")
        print(f"  Onay Durumu  : {oneri.onay_durumu}")
        print(f"  Durum        : {oneri.durum}")
        print(f"  Değerlendirme: {oneri.degerlendirme}")
    return 0


def _yapay_zeka_satirlari(ayarlar: Ayarlar, oneriler) -> tuple[set[int], set[int]]:
    """(ekibin düzeltmediği yapay zekâ taslakları, henüz kontrol edilmemiş taslaklar) satırları."""
    if not ayarlar.taslak_yolu.exists():
        return set(), set()
    depo = TaslakDeposu(ayarlar.taslak_yolu)
    try:
        taslaklar = {t.anahtar: t for t in depo.hepsi()}
    finally:
        depo.kapat()
    kendi, kontrolsuz = set(), set()
    for oneri in oneriler:
        taslak = taslaklar.get(oneri.anahtar)
        if taslak and taslak.sonuc != DUZELTILDI:
            kendi.add(oneri.satir)
            if taslak.sonuc is None:
                kontrolsuz.add(oneri.satir)
    return kendi, kontrolsuz


def calistir_komutu(ayarlar: Ayarlar, args) -> int:
    """Bekleyen önerileri doldurur, önceki taslaklara 7 gün kuralını uygular."""
    print(f"--- {datetime.now():%d.%m.%Y %H:%M} ---")
    try:
        with tek_calisma(ayarlar.veri_klasoru):
            kaynak, ayarlar = kaynagi_hazirla(ayarlar)
            try:
                depo = TaslakDeposu(ayarlar.taslak_yolu)
                try:
                    ozet = calistir(
                        ayarlar,
                        kaynak,
                        Ollama(ayarlar.ollama_adresi),
                        depo,
                        datetime.now(),
                        deneme=args.deneme,
                    )
                finally:
                    depo.kapat()
            finally:
                kaynak.kapat()  # Excel yönteminde Excel'i kapatır
    except CalismaSuruyor as hata:
        print(f"{hata} Bu çalışma atlandı.")
        return 0

    if args.deneme:
        print("\nDeneme: Excel'e ve kayda hiçbir şey yazılmadı.")
    print(
        f"\nYazılan: {ozet.yazilan}, atlanan: {ozet.atlanan}, üretilemeyen: {ozet.hatali}"
        f" | onaylanan: {ozet.onaylanan}, düzeltilen: {ozet.duzeltilen}, silinen: {ozet.silinen}"
    )
    if ozet.kalan:
        print(f"{ozet.kalan} öneri sonraki çalışmaya kaldı.")
    return 1 if ozet.hatali else 0


def rapor(ayarlar: Ayarlar, _args) -> int:
    """Yapay zekâ taslaklarının ne kadarının değiştirilmeden onaylandığını gösterir."""
    if not ayarlar.taslak_yolu.exists():
        print("Henüz yapay zekânın yazdığı taslak yok.")
        return 0
    depo = TaslakDeposu(ayarlar.taslak_yolu)
    try:
        taslaklar = depo.hepsi()
    finally:
        depo.kapat()

    def satir(baslik: str, grup: list) -> str:
        sayi = Counter(t.sonuc for t in grup)
        karar = sum(1 for t in grup if t.sonuc == DUZELTILDI and t.ekip_onay_durumu != t.onay_durumu)
        biten = sayi[ONAYLANDI] + sayi[DUZELTILDI]
        oran = f"%{100 * sayi[ONAYLANDI] / biten:.0f}" if biten else "-"
        return (
            f"{baslik:<8} yazılan {len(grup):>4} | kontrol bekleyen {sayi[None]:>3} | "
            f"değiştirilmeden onaylanan {sayi[ONAYLANDI]:>3} | düzeltilen {sayi[DUZELTILDI]:>3}"
            f" (kararı değişen {karar}) | silinen {sayi[SILINDI]:>2} | onay oranı {oran}"
        )

    print(f"Onay süresi: {ayarlar.onay_gun_sayisi} gün. Onay oranı = onaylanan / (onaylanan + düzeltilen)\n")
    aylar: dict[str, list] = {}
    for taslak in taslaklar:
        aylar.setdefault(f"{taslak.yazilma:%Y-%m}", []).append(taslak)
    for ay, grup in sorted(aylar.items()):
        print(satir(ay, grup))
    print(satir("Toplam", taslaklar))
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
    kor.add_argument(
        "--yontem",
        choices=["model", "komsu", "karma"],
        default="model",
        help=(
            "model: dil modeli karar verir; komsu: benzer önerilerin çoğunluk kararı;"
            " karma: benzer öneriler güçlü şekilde aynıysa onların kararı, değilse model"
        ),
    )
    canli = komutlar.add_parser(
        "calistir", help="bekleyen önerileri Excel'e yazar, önceki taslaklara 7 gün kuralını uygular"
    )
    canli.add_argument(
        "--deneme", action="store_true", help="Excel'e yazmadan, yazılacakları ekranda göster"
    )
    komutlar.add_parser("rapor", help="taslakların ne kadarının değiştirilmeden onaylandığını gösterir")
    tek = komutlar.add_parser("degerlendir", help="tek bir Excel satırı için taslak üretir")
    tek.add_argument("satir", type=int, help="Excel'deki satır numarası")
    args = ayristirici.parse_args(argv)

    komut = {
        "kontrol": kontrol,
        "kor-test": kor_test,
        "degerlendir": degerlendir,
        "calistir": calistir_komutu,
        "rapor": rapor,
    }[args.komut]
    try:
        return komut(ayarlari_yukle(args.ayarlar), args)
    except (ExcelHatasi, OllamaHatasi, GraphHatasi, OSError, ValueError) as hata:
        print(f"HATA: {hata}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
