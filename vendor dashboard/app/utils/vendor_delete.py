"""Permanently remove a vendor and clear FK references (admin / maintenance)."""
from app import db
from app.models import (
    Vendor,
    VendorComponent,
    VendorDocument,
    VendorRating,
    VendorOrder,
    Order,
    OrderItem,
    CartItem,
    Transaction,
)


def permanently_delete_vendor(vendor_id):
    """
    Delete vendor row after removing dependent rows / nulling references.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    vendor = Vendor.query.get(vendor_id)
    if not vendor:
        return False, 'Vendor not found'

    try:
        Transaction.query.filter_by(vendor_id=vendor_id).delete(synchronize_session=False)

        for vo in VendorOrder.query.filter_by(vendor_id=vendor_id).all():
            db.session.delete(vo)

        VendorComponent.query.filter_by(vendor_id=vendor_id).delete(synchronize_session=False)
        VendorDocument.query.filter_by(vendor_id=vendor_id).delete(synchronize_session=False)
        VendorRating.query.filter_by(vendor_id=vendor_id).delete(synchronize_session=False)

        OrderItem.query.filter_by(vendor_id=vendor_id).update(
            {OrderItem.vendor_id: None}, synchronize_session=False
        )
        Order.query.filter_by(vendor_id=vendor_id).update(
            {Order.vendor_id: None}, synchronize_session=False
        )
        CartItem.query.filter_by(vendor_id=vendor_id).update(
            {CartItem.vendor_id: None}, synchronize_session=False
        )

        db.session.delete(vendor)
        db.session.commit()
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, str(e)
