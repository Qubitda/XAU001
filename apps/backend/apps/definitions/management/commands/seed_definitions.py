from django.core.management.base import BaseCommand

from apps.definitions.services import seed_definition_tables


class Command(BaseCommand):
    help = "Seed / refresh Tanım_Tablosu lookup data from Kuyum_Çalışma.xlsx canonical seed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-system-items",
            action="store_true",
            help="Delete existing system items before re-seeding each table.",
        )

    def handle(self, *args, **options):
        result = seed_definition_tables(reset_system_items=options["reset_system_items"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Tanım tabloları yüklendi: {result['tables']} tablo, "
                f"{result['items']} kalem, {result.get('links', 0)} üst bağlantı."
            )
        )
