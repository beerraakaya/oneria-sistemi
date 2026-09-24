# Öneri Sistemi Yapay Zekâ Asistanı

Öneri Excel'ine düşen önerilerin **Değerlendirme**, **Onay Durumu** ve **Durum** sütunlarını, ekibin geçmiş değerlendirmelerinden öğrenerek taslak olarak dolduran asistan. Son karar her zaman ekibindir.

Yapay zekâ modeli (Ollama ile Qwen) şirket bilgisayarında çalışır; öneri metinleri hiçbir dış yapay zekâ servisine gönderilmez.

## Aşamalar

1. **Kör test (tamamlandı):** ekibin değerlendirdiği öneriler, cevapları gizlenerek yapay zekâya yeniden değerlendirildi. Son testte ekiple aynı karar oranı %74 (hedef %70).
2. **Canlı kullanım:** program tek bir şirket bilgisayarında çalışır, SharePoint'teki Excel'de bekleyen Denizli önerilerini doldurur. Ekip Excel'i her zamanki gibi açıp taslakları kontrol eder. Aşağıdaki "Canlı kullanım" bölümüne bakın.

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
python -m oneri calistir --deneme    # canlı kullanım: yazılacakları göster, yazma
python -m oneri calistir             # canlı kullanım: bekleyen önerileri Excel'e yaz
python -m oneri rapor                # taslakların onaylanma oranı
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

## Canlı kullanım

### Program ne yapar?

`python -m oneri calistir` her çalıştığında:

1. SharePoint'teki Excel'in güncel hâlini indirir.
2. **Önceki taslaklara bakar:**
   - Ekip Değerlendirme'yi ya da Onay Durumu'nu değiştirdiyse taslak **düzeltildi** sayılır. Ekibin yazdığı metin bundan sonra yapay zekâya örnek olur.
   - 7 gün boyunca değiştirilmediyse **onaylandı** sayılır.
   - Durum'un sonradan Tamamlandı ya da Uygulanamaz yapılması düzeltme sayılmaz; bu, sürecin ilerlemesidir.
   - Her iki durumda da hücrelerin sarı rengi kaldırılır.
3. **Değerlendirme, Onay Durumu ve Durum hücrelerinin üçü de boş olan Denizli satırlarını doldurur.** Yazdığı hücreleri açık sarıya boyar; ekip sarı hücrelerin henüz kontrol edilmemiş yapay zekâ taslakları olduğunu anlar.

Güvenlik kuralları:

- Yalnızca bu üç hücreye yazar. Satır eklemez, silmez, sıralamaz; Tuzla satırlarına ve dolu hücrelere dokunmaz.
- Yazmadan hemen önce satırı yeniden okur. Öneri değişmişse ya da o arada biri bir şey yazmışsa o satırı atlar.
- Ekibin henüz kontrol etmediği taslakları yapay zekâya örnek göstermez; yapay zekâ kendi yazdıklarından değil, ekibin yazdıklarından ve onayladıklarından öğrenir.
- Bilgisayar kapalıyken gelen öneriler kaybolmaz. Öneriler Excel'e Jotform üzerinden gelmeye devam eder; program açıldığında boş olan bütün satırları doldurur.
- Bir çalışmada en fazla 20 öneri doldurur (`en_fazla_oneri`); kalanlar bir sonraki çalışmaya kalır.

### 1. IT'nin yapması gerekenler

Programın SharePoint'e yazabilmesi için Microsoft Entra ID'de (Azure AD) bir uygulama kaydı gerekir:

1. **App registration** oluşturulur (örn. "Öneri Asistanı").
2. Microsoft Graph için **application permission** verilir ve **admin consent** yapılır:
   - Önerilen: `Sites.Selected`, ardından yalnızca öneri Excel'inin bulunduğu site için **write** izni verilir.
   - Alternatif: `Files.ReadWrite.All` (daha geniş yetkidir).
3. Bir **client secret** oluşturulur.

IT'den şu üç bilgi alınır: **Directory (tenant) ID**, **Application (client) ID** ve **client secret**.

### 2. Programın kurulacağı bilgisayarda ayarlar

`ayarlar.toml` dosyasına şunları yazın:

```toml
dil_modeli = 'qwen2.5:14b'
sharepoint_dosya_adresi = 'https://sirket.sharepoint.com/sites/SiteAdi/Shared Documents/Klasor/Oneri.xlsx'
graph_kiraci = '00000000-0000-0000-0000-000000000000'
graph_uygulama = '00000000-0000-0000-0000-000000000000'
```

`graph_kiraci` yerine IT'nin verdiği tenant ID'yi, `graph_uygulama` yerine client ID'yi yazın.

**Dosya adresini almak için:** SharePoint'te Excel dosyasının yanındaki "..." menüsünden **Ayrıntılar**'ı açın, **Yol** satırındaki kopyala düğmesine basın. "Bağlantıyı kopyala" ile alınan paylaşım bağlantısı da çalışır; ancak IT `Sites.Selected` izni verdiyse Yol kullanılmalıdır.

**Gizli anahtar (client secret) dosyaya yazılmaz.** Komut satırında bir kez şunu çalıştırın, sonra komut satırını kapatıp yeniden açın:

```
setx ONERI_GRAPH_SIRRI "IT'nin verdiği client secret"
```

Kontrol edin:

```
python -m oneri kontrol
```

"SharePoint: bağlandı" ve "Her şey hazır." görünmelidir.

### 3. Önce deneyin

```
python -m oneri calistir --deneme
```

Bu komut Excel'e **hiçbir şey yazmaz**; hangi satıra ne yazılacağını ekranda gösterir. Sonuçlar uygunsa gerçek çalıştırma:

```
python -m oneri calistir
```

İsterseniz SharePoint'e geçmeden önce bilgisayardaki bir kopyada da deneyebilirsiniz. `sharepoint_dosya_adresi` boş bırakılırsa program `excel_yolu`'ndaki dosyaya yazar. Bu dosya bir **kopya** olmalı ve Excel'de açık olmamalıdır.

### 4. Otomatik çalıştırma (Görev Zamanlayıcı)

Program `calistir.bat` ile çalışır ve çıktılarını `veri\gunluk.log` dosyasına yazar. Bilgisayarın sürekli açık kalması gerekmez; mesai saatinde açık olması yeterlidir.

**Mesai boyunca her 30 dakikada bir** (proje klasörünün yolunu kendi bilgisayarınıza göre değiştirin):

```
schtasks /Create /TN "Oneri Asistani" /TR "\"C:\oneri-sistemi\calistir.bat\"" /SC DAILY /ST 08:00 /RI 30 /DU 10:00 /F
```

**Bilgisayar açılınca bir kez:** `Win + R` > `shell:startup` yazın. Açılan klasöre `calistir.bat` dosyasının kısayolunu koyun.

Notlar:

- Önceki çalışma bitmeden yenisi başlarsa yenisi kendiliğinden atlanır.
- Ollama henüz açılmadıysa o çalışma hata verir; bir sonraki çalışma işi yapar.
- Görevi "Görev Zamanlayıcı" uygulamasından görebilir, durdurabilir ya da silebilirsiniz.

### Ölçüm

```
python -m oneri rapor
```

Bu komut her ay için şunları gösterir: kaç taslak yazıldı, kaçı değiştirilmeden onaylandı, kaçı düzeltildi (kaçında kararın kendisi değişti) ve **onay oranı**. Projenin başarısı bu oranla izlenir.

Yapay zekânın yazdığı taslakların kaydı ve gerekçeleri `veri\taslaklar.db` dosyasındadır; bu dosya silinmemelidir.

## Veri güvenliği

- Excel dosyaları, `veri` klasörü (hafıza, taslak kaydı, SharePoint kopyası, günlük ve raporlar) ve `ayarlar.toml` git'e gönderilmez.
- Gizli anahtar dosyada değil, `ONERI_GRAPH_SIRRI` ortam değişkeninde tutulur.
- Testler gerçek veri değil, uydurma örnekler kullanır.
- Yapay zekâya yalnızca öneri bilgileri (konu, bölüm, mevcut durum, önerilen durum) gider. Kişi adları okunmaz. Yapay zekâ bilgisayarın kendisinde çalışır; öneriler dış bir yapay zekâ servisine gönderilmez.

## Geliştirme

```
python -m pip install -r requirements-dev.txt
python -m pytest
```
