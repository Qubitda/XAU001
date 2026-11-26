"""
Run the same jobs Celery beat owns — useful on Windows when Redis <5 blocks Celery workers.

Usage:
  python manage.py run_scheduled_jobs
  python manage.py run_scheduled_jobs --only price_locks,stone_locks
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Execute scheduled maintenance jobs synchronously (Celery beat parity)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            type=str,
            default="",
            help="Comma list: stone_locks,price_locks,abandoned_carts,market_rates,document_retention",
        )

    def handle(self, *args, **options):
        only = {p.strip() for p in (options.get("only") or "").split(",") if p.strip()}
        ran = []

        if not only or "stone_locks" in only:
            from apps.commerce.tasks import release_expired_stone_locks_task

            result = release_expired_stone_locks_task()
            self.stdout.write(self.style.SUCCESS(f"stone_locks={result}"))
            ran.append("stone_locks")

        if not only or "price_locks" in only:
            from apps.pricing.tasks import cleanup_expired_price_locks

            result = cleanup_expired_price_locks()
            self.stdout.write(self.style.SUCCESS(f"price_locks={result}"))
            ran.append("price_locks")

        if not only or "abandoned_carts" in only:
            from apps.commerce.tasks import scan_abandoned_carts_task

            result = scan_abandoned_carts_task()
            self.stdout.write(self.style.SUCCESS(f"abandoned_carts={result}"))
            ran.append("abandoned_carts")

        if not only or "market_rates" in only:
            from apps.market.tasks import refresh_market_rates_snapshot

            result = refresh_market_rates_snapshot()
            self.stdout.write(self.style.SUCCESS(f"market_rates={result}"))
            ran.append("market_rates")

        if not only or "document_retention" in only:
            from apps.organizations.tasks import apply_document_retention_task

            result = apply_document_retention_task()
            self.stdout.write(self.style.SUCCESS(f"document_retention={result}"))
            ran.append("document_retention")

        self.stdout.write(self.style.NOTICE(f"Completed: {', '.join(ran)}"))
