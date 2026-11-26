from django.db import migrations
from django.utils import timezone


def seed_docs(apps, schema_editor):
    LegalDocument = apps.get_model("contracts", "LegalDocument")
    now = timezone.now()
    seeds = [
        ("KVKK", "1.0", "KVKK Aydınlatma Metni", "<p>Kişisel verilerinizin işlenmesi hakkında aydınlatma metni.</p>"),
        ("PRIVACY", "1.0", "Gizlilik İlkeleri", "<p>Gizlilik ilkelerimiz.</p>"),
        ("COOKIE", "1.0", "Çerez Politikası", "<p>Çerez kullanım politikası.</p>"),
        ("DISTANCE_SALES", "1.0", "Mesafeli Satış Sözleşmesi", "<p>Mesafeli satış sözleşmesi metni.</p>"),
        ("PRE_INFO", "1.0", "Ön Bilgilendirme Formu", "<p>Ön bilgilendirme formu.</p>"),
        ("MEMBERSHIP", "1.0", "Üyelik Sözleşmesi", "<p>Üyelik sözleşmesi metni.</p>"),
    ]
    for code, version, title, body in seeds:
        LegalDocument.objects.get_or_create(
            code=code,
            version=version,
            defaults={
                "title": title,
                "body_html": body,
                "body_md": "",
                "content_hash": "",
                "effective_from": now,
                "is_published": True,
                "audience": "ALL",
            },
        )


def unseed(apps, schema_editor):
    LegalDocument = apps.get_model("contracts", "LegalDocument")
    LegalDocument.objects.filter(version="1.0").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0001_customer_360_faz_a"),
    ]

    operations = [
        migrations.RunPython(seed_docs, unseed),
    ]
