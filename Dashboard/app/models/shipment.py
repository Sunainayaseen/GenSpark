# Shipment
from datetime import datetime
from app import db


class Shipment(db.Model):
    __tablename__ = 'shipments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    courier_name = db.Column(db.String(100))
    tracking_number = db.Column(db.String(100))
    status = db.Column(db.String(50))  # dispatched, in_transit, delivered
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
