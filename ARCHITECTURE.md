# Tara Gold — Mimari Notlar

## `catalog` ↔ `pricing` Çekirdek Bağımlılığı {#catalog-pricing-coupling}

`apps/catalog` ve `apps/pricing` modülleri arasında bilinçli fakat sıkı bir çift yönlü domain bağımlılığı bulunur: `pricing` katmanındaki `PricingRecipe` ve `PriceQuote` modelleri `catalog.ProductModel` / `ProductVariant` kayıtlarına doğrudan `ForeignKey` ile bağlıdır (`pricing/models.py`, `pricing/services.py`, `pricing/strategies.py`), `catalog/services.py` ise bir ürünün yayına alınıp alınamayacağını (`validate_publishable`) doğrulamak için `pricing.models.PricingRecipe` üzerinden yayınlanmış reçete varlığını sorgular. Bu yapı, Django'nun `INSTALLED_APPS` sırasıyla tüm modelleri önceden yüklemesi sayesinde sorunsuz çalışsa da iki domain'in birbirinden bağımsız deploy edilmesini veya izole test edilmesini engeller; saf hesaplama motoru olan `pricing/engine.py` ise `catalog`'dan tamamen bağımsız tutulmuştur. İleride bu iki bounded context'i ayrıştırmak için `ProductModel` üzerinde `has_published_recipe` benzeri bir durum bayrağı/projeksiyonu tutulup `pricing` tarafında reçete yayınlandığında veya arşivlendiğinde domain event (veya sinyal/outbox) ile güncellenebilir; böylece `catalog` → `pricing` yönündeki ters bağımlılık tamamen ortadan kalkar.

## Merkezi Tenant Scoping Kuralı {#centralized-tenant-scoping}

- **Kural:** `TenantContext` (`ctx.organization`, `ctx.branch`, `ctx.is_ops`) kullanan tüm view ve selector'larda queryset izolasyonu **her zaman** `apps.organizations.selectors.scope_queryset_to_organization` ve `scope_queryset_to_branch` üzerinden uygulanır.
- Asla view içinde elle `.filter(organization=ctx.organization)` veya `.filter(branch=ctx.branch)` yazılmaz.
- Statik doğrulama için: `python scripts/check_tenant_scoping.py` çalıştırılır.

