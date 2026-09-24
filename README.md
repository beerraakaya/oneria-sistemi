# Öneri Sistemi Yapay Zekâ Asistanı

Öneri Excel'ine düşen önerilerin **Değerlendirme**, **Onay Durumu** ve **Durum** sütunlarını, ekibin geçmiş değerlendirmelerinden öğrenerek taslak olarak dolduran asistan. Son karar her zaman ekibindir.

Yapay zekâ modeli (Ollama ile Qwen) şirket bilgisayarında çalışır; öneri metinleri hiçbir dış yapay zekâ servisine gönderilmez.

## Şu anki aşama: kör test

Asistan henüz Excel'e yazmıyor. Önce ne kadar isabetli olduğunu ölçüyoruz: ekibin yeni tarzda değerlendirdiği öneriler, cevapları gizlenerek yapay zekâya yeniden değerlendirtilir ve iki cevap bir Excel raporunda yan yana konur.

## Kurulum (Windows)

1. **Python 3.11 veya üstü:** python.org'dan kurun. Kurarken "Add Python to PATH" kutusunu işaretleyin.
2. **Ollama:** ollama.com'dan kurun, sonra komut satırında modelleri indirin:
   ```
   ollama pull qwen2.5
   ollama pull bge-m3
   ```
   `qwen2.5` 7B boyutundadır. Bilgisayarın belleği yetiyorsa `qwen2.5:14b` Türkçede daha iyi sonuç verir; o zaman ayarlarda `dil_modeli` olarak onu yazın.
3. **Kütüphaneler:** proje klasöründe:
   ```
   python -m pip install -r requirements.txt
   ```
4. **Excel kopyası:** öneri Excel'inin bir kopyasını proje klasöründe `veri\oneri.xlsx` olarak kaydedin. `veri` klasörü git'e gönderilmez.
5. **Ayarlar (isteğe bağlı):** model adı ya da Excel'in yeri farklıysa `ayarlar.ornek.toml` dosyasını `ayarlar.toml` adıyla kopyalayıp düzenleyin.

## Kullanım

Komutları proje klasöründe çalıştırın:

```
python -m oneri kontrol              # Excel, kurallar ve modeller hazır mı?
python -m oneri kor-test --adet 3    # önce en yeni 3 öneriyle hızlı deneme
python -m oneri kor-test             # yeni tarzdaki tüm önerilerle kör test
python -m oneri degerlendir 567      # tek bir satır için taslak; Excel'e yazmaz
```

Kör testte kararın nasıl verileceği `--yontem` ile seçilir:

- `model` (varsayılan): kararı dil modeli verir.
- `komsu`: modele sormadan, en benzer 7 geçmiş önerinin çoğunluk kararı. Birkaç saniyede biter; karşılaştırma ölçütüdür, metin yazmaz.
- `karma`: benzer 7 önerinin en az 5'i aynı kararı gösteriyorsa karar onlardan alınır ve model sadece gerekçeyi ve metni yazar; benzer öneriler bölünmüşse kararı model verir.

```
python -m oneri kor-test --yontem komsu
python -m oneri kor-test --yontem karma
```

Kör test raporu `veri\kor_test_<yöntem>_<tarih>.xlsx` dosyasına yazılır:

- **Özet** sayfası: yapay zekâ kaç öneride ekiple aynı kararı verdi.
- **Karşılaştırma** sayfası: her öneri için ekibin ve yapay zekânın cevabı yan yana. "Metin Puanı" sütununa 1–5 arası puan vererek metinlerin kalitesini de ölçebilirsiniz.

Ekran kartı olmayan bir bilgisayarda her öneri birkaç dakika sürebilir. Test Ctrl+C ile yarıda durdurulursa o ana kadarki sonuçlar yine rapora yazılır.

## Nasıl çalışır?

1. Excel'den yalnızca **Denizli** satırları okunur; Tuzla satırlarına dokunulmaz. Kişi adı sütunları hiç okunmaz.
2. Kararı ve değerlendirmesi olan öneriler **kurumsal hafızayı** oluşturur. "deneme" gibi 40 karakterden kısa değerlendirmeler test kaydı sayılıp dışarıda bırakılır.
3. Hafızadaki metinler ikiye ayrılır: ilk cümlesi en az 3 kayıtta aynen geçenler **eski kalıp** metinlerdir, diğerleri **yeni tarzdır**.
4. Yeni bir öneri geldiğinde `bge-m3` ile anlamca en benzer eski öneriler bulunur. Modele yalnızca **ekibin kendi yazdığı** (yeni tarz) en benzer 8 değerlendirme, kararıyla birlikte gösterilir; böylece model ekibin benzer önerilerde neye bakıp ne dediğini görür.
5. Değerlendirme adım adım yapılır:
   - **Karar:** model önerilen şeyi özetler ve `kurallar.md`'deki gerekçelerden birini seçer ("Geçerli öneri" ya da bir ret gerekçesi).
   - **Kontrol:** model "Rutin iş" ya da "Politika/sosyal hak talebi" seçtiyse, örnek göstermeden tek bir soru sorulur ("Bozulanı eski hâline mi getiriyor?", "Asıl faydası çalışanın kişisel yararına mı?"). Cevap "Hayır" ise karar "Öneri" olur. Model bu iki gerekçeyi, mevcut yöntemi iyileştiren önerilerde de yanlışlıkla seçiyordu. `ayarlar.toml` içinde `red_kontrolu = false` yazılarak kapatılabilir.
   - **Metin:** karar belliyken, ekip gibi önce faydayı görüp iki cümlelik değerlendirmeyi yazar.
6. Durum karara göre yazılır: "Öneri" için "Devam Ediyor", "Öneri Değil" için "Red Edildi". Tamamlandı ve Uygulanamaz'ı ekip sonradan girer.

`kurallar.md` yapay zekâya verilen talimattır; ekip olarak gözden geçirip düzenleyebilirsiniz.

## Veri güvenliği

- Excel dosyaları, `veri` klasörü (hafıza ve raporlar) ve `ayarlar.toml` git'e gönderilmez.
- Testler gerçek veri değil, uydurma örnekler kullanır.
- Yapay zekâya yalnızca öneri bilgileri (konu, bölüm, mevcut durum, önerilen durum) gider.

## Yol haritası

1. **Kör test** (şimdi): isabeti ölç, kuralları ve ayarları iyileştir.
2. **Canlı kullanım:** SharePoint'teki Excel'i okuyup yalnızca ilgili üç hücreye yazmak (IT izni gerekir), yapay zekânın yazdıklarını kaydetmek ve **7 gün kuralı**: 7 gün içinde değiştirilmeyen taslak onaylanmış sayılır, değiştirilen taslakta ekibin yazdığı örnek alınır.
3. **Ölçüm:** taslakların yüzde kaçının değiştirilmeden onaylandığını raporlamak.

## Geliştirme

```
python -m pip install -r requirements-dev.txt
python -m pytest
```
