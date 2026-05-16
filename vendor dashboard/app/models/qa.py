# Quality Assurance
from datetime import datetime
from app import db


class QaCheck(db.Model):
    __tablename__ = 'qa_checks'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    result = db.Column(db.String(20))  # pass, fail
    image_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    checked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
