# Notification
from datetime import datetime
from app import db


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(150))
    message = db.Column(db.Text)
    type = db.Column(db.String(50))  # order_update, payment, shipment
    related_id = db.Column(db.Integer)  # order_id etc.
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
