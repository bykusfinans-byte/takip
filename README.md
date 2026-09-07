# BIST 4 Saatlik Panel + Sanal Portföy

BIST hisseleri için 4 saatlik mumlarda **EMA9, EMA21, SMA50, MACD, ADX, RSI**
gösterip, koşulu (`fiyat > EMA9 > EMA21 > SMA50`, `ADX > 25`, `MACD > 0`)
sağlayan hisseleri yeşil vurgulayan; ayrıca gerçek para kullanmadan
al-sat denemesi yapabileceğin bir "sanal portföy" içeren, tamamen
**GitHub Pages üzerinde çalışan** (sunucu gerektirmeyen) bir panel.

## Nasıl çalışıyor

- `scripts/fetch_data.py`: Yahoo Finance'ten 1 saatlik veri çekip 4 saatlik
  mumlara indirger, göstergeleri hesaplar, `docs/data.json` dosyasına yazar.
- `.github/workflows/update-data.yml`: Bu betiği hafta içi günde birkaç kez
  otomatik çalıştırıp `data.json`'ı repoya commit'ler (GitHub Actions ücretsiz
  hesaplarda da yeterli).
- `docs/index.html`: Statik sayfa; `data.json`'ı okuyup tabloyu ve sanal
  portföy arayüzünü çizer. Portföy verisi tarayıcının `localStorage`'ında
  saklanır — yani her kullanıcının portföyü kendi tarayıcısına özeldir,
  paylaşılmaz.

Bu mimari sayesinde tarayıcıdan doğrudan borsa API'sine istek atılmıyor
(CORS sorunu yaşanmıyor); veri periyodik olarak GitHub sunucularında
hazırlanıp statik dosya olarak sunuluyor.

## Kurulum

1. Bu klasörü kendi GitHub hesabında yeni bir repoya yükle (repo adı
   dilediğin gibi olabilir, örn. `bist-4h-panel`).
2. Repo **Settings → Pages** kısmından:
   - Source: `Deploy from a branch`
   - Branch: `main` / klasör: `/docs`
   seç ve kaydet.
3. Repo **Settings → Actions → General** kısmında "Workflow permissions"
   ayarını **Read and write permissions** yap (workflow'un `data.json`'ı
   commit'leyebilmesi için gerekli).
4. **Actions** sekmesine gidip "BIST 4H veri güncelle" workflow'unu seç ve
   **Run workflow** ile ilk çalıştırmayı elle tetikle. Birkaç dakika içinde
   `docs/data.json` gerçek verilerle güncellenecek.
5. Pages ayarlarında verilen adrese (örn.
   `https://kullanici-adin.github.io/bist-4h-panel/`) gidip paneli gör.

Sonrasında workflow otomatik olarak hafta içi günde birkaç kez (cron ayarı
`update-data.yml` içinde) çalışıp veriyi tazeler; istersen `cron` satırını
değiştirerek sıklığı ayarlayabilirsin.

## Takip edilen hisseleri değiştirmek

`scripts/fetch_data.py` dosyasının başındaki `SYMBOLS` listesini
düzenle (Yahoo Finance formatı: `KOD.IS`, örn. `THYAO.IS`). Değişikliği
push ettikten sonra workflow'u elle bir kez tetikle.

## Sınırlamalar / notlar

- Veri Yahoo Finance'ten geliyor; gecikmeli/gerçek zamanlı olmayabilir ve
  bazı günlerde eksik/hatalı olabilir (`data.json` içindeki `errors`
  alanından kontrol edebilirsin).
- 4 saatlik mumlar, 1 saatlik veriden BIST seansına (10:00 başlangıç)
  göre yaklaşık olarak türetiliyor; resmi borsa mumlarıyla birebir aynı
  olmayabilir.
- ADX/RSI/MACD hesapları standart formüllerle (Wilder yumuşatması) yazıldı,
  farklı platformlarla ufak ondalık farkları olabilir.
- Bu araç **yatırım tavsiyesi değildir**, eğitim ve deneme amaçlıdır.
- Sanal portföy verisi yalnızca tarayıcı `localStorage`'ında tutulur;
  tarayıcı verilerini temizlersen ya da başka bir cihazdan girersen
  portföy sıfırdan başlar.
