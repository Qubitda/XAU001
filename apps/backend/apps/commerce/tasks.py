from celery import shared_task


@shared_task(name="commerce.release_expired_stone_locks")
def release_expired_stone_locks_task() -> dict:
    from apps.commerce.dyo import release_expired_stone_locks

    count = release_expired_stone_locks()
    return {"released": count}


@shared_task(name="commerce.scan_abandoned_carts")
def scan_abandoned_carts_task() -> dict:
    from apps.commerce.recovery import scan_abandoned_carts

    return scan_abandoned_carts()
