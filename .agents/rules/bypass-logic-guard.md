# RULE: Bypass Logic Guard (A→B kısayolu, C/D/E kalıntısı)

## Ne zaman tetiklenir
Aşağıdaki durumlardan BİRİ geçerliyse bu kural zorunlu olarak uygulanır:
- Mevcut bir fonksiyon/metod/endpoint'in çağrı zincirini değiştiriyorsan
  (örn. A artık doğrudan B'yi çağırıyor, önceden A→C→D→E→B şeklindeydi)
- Bir "yeni yol" (yeni parametre, yeni servis, yeni tablo/alan) eklerken eski yolu
  yanında bırakıyorsan (dual-write / dual-read senaryosu)
- Bir feature flag, config değeri veya koşulu sabitliyorsan (örn. her zaman True/False
  dönecek şekilde değiştiriyorsan)
- Bir refactor/migration görevi tamamlıyorsan ("legacy", "deprecated", "TODO: remove"
  etiketli kod etrafında çalışıyorsan)

## Zorunlu kontrol listesi (görevi "tamamlandı" demeden önce)

1. **Eski yolu bul.** Değiştirdiğin fonksiyonun ÖNCEKİ halinde A'dan B'ye giden
   ara adımlar (C, D, E) var mıydı? Varsa bunları isim/dosya/satır olarak listele.

2. **Her ara adım için 3 soru sor:**
   - Bu adımı artık çağıran var mı? (call graph / grep ile referans ara)
   - Çağrılıyor olsa bile, ÜRETTİĞİ değer yeni akışta (A→B) kullanılıyor mu?
     Kullanılmıyorsa bu bir "dead store" — kod çalışır ama sonucu anlamsızdır.
   - Bu adım, eski bir mimari/tablo/field'a mı yazıyor/okuyor? Yeni mimari onu
     artık okumuyorsa bu "legacy residue" — silinmeyi bekleyen kalıntıdır.

3. **Üç kategoriden birine ata ve raporla, SESSİZCE GEÇME:**
   - 🔴 **Artık hiç kullanılmıyor** → silinmeli, PR/commit mesajında açıkça belirt.
   - 🟡 **Hâlâ çalışıyor ama amacı belirsiz** → silme, ama görev sonunda kullanıcıya
     "şu kod hâlâ var ama yeni akışta rolü yok, kontrol eder misin?" diye sor.
   - 🟢 **Gerçekten hâlâ gerekli** (örn. feature flag ile koşullu kullanılıyor,
     geriye dönük uyumluluk için bilinçli bırakılmış) → neden gerekli olduğunu
     bir yorum satırıyla (`# kept for: ...`) belgeleyerek bırak.

4. **Asla "bypass + bırak" yapma.** Yeni bir kısayol (A→B) eklerken eski yolu
   (A→C→D→E→B) hiçbir açıklama yapmadan erişilemez bırakmak YASAK. Ya temizle,
   ya da neden bırakıldığını açıkça yaz.

5. **Testi kanıt olarak kullan.** Eğer test suite ve coverage mevcutsa, şüpheli
   C/D/E bloğunun coverage'da tetiklenip tetiklenmediğini kontrol et. %0 coverage,
   "artık kullanılmıyor" iddiasını güçlendiren somut kanıttır — ama tek başına
   yeterli değildir (dynamic dispatch/reflection kaçırabilir).

6. **Dual-write/dual-read özel durumu.** Eğer değişiklik bir geçiş (migration)
   sürecinin parçasıysa (eski alan + yeni alan birlikte var), şunu açıkça belirt:
   - Hangi taraf artık SSOT (source of truth)?
   - Eski taraf ne zaman / hangi koşulda temizlenecek?
   - Bu bilgi yoksa, görev raporunda bunu bir eksik olarak işaretle, sessizce
     geçme.

## Çıktı formatı
Her görev sonunda, eğer bu kural tetiklendiyse, cevabına şu bloğu ekle:

**Bypass Logic Guard sonucu:**
- [dosya:satır] — [kategori: 🔴/🟡/🟢] — [tek cümlelik gerekçe]

Hiçbir şey tetiklenmediyse (mevcut akışta ara adım yoktu, temiz bir ekleme yapıldı)
bu bloğu hiç yazma — gereksiz gürültü üretme.

## Sınırlar
- Bu kural kodu OTOMATİK SİLMENİ gerektirmez. 🔴 kategorisindeki bulgular için
  bile, kullanıcı onayı olmadan silme işlemi yapma; sadece net bir öneriyle raporla.
- Dynamic dispatch, plugin sistemleri, reflection, veya string ile çağrılan
  fonksiyonlar (örn. `getattr(obj, name)`) için düşük güven ("belki kullanılıyor
  olabilir") ile işaretle, kesin "ölü" deme.
