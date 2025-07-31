import logging
from celery import shared_task
from models import db
from models.item import Item
from app.utils import transactional
from flask import current_app

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_bulk_items_task(self, shop_id: int, dataframe_dict: dict) -> int:
    """Create items from uploaded DataFrame."""
    try:
        import pandas as pd  # Imported lazily to avoid dependency issues during CLI operations
        df = pd.DataFrame.from_dict(dataframe_dict)
    except Exception as exc:
        logger.error("Bulk upload dataframe error: %s", exc)
        raise self.retry(exc=exc)

    from app import create_app
    app = current_app._get_current_object() if current_app else create_app()
    with app.app_context():
        created = 0
        for _, row in df.iterrows():
            try:
                item = Item(
                    shop_id=shop_id,
                    title=row["title"],
                    brand=row.get("brand"),
                    price=row["price"],
                    mrp=row.get("mrp"),
                    discount=row.get("discount"),
                    quantity_in_stock=row.get("quantity_in_stock", 0),
                    unit=row.get("unit"),
                    pack_size=row.get("pack_size"),
                    category=row.get("category"),
                    tags=row.get("tags"),
                    sku=row.get("sku"),
                    expiry_date=row.get("expiry_date"),
                    image_url=row.get("image_url"),
                    description=row.get("description", ""),
                    is_available=True,
                    is_active=True,
                )
                db.session.add(item)
                created += 1
            except Exception as exc:
                logger.error("Failed to add item row: %s", exc)
                continue
        with transactional("Failed to bulk upload items"):
            pass
        return created
