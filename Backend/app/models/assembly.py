# Assembly Tracking
from datetime import datetime
from app import db

ASSEMBLY_STAGES = ['in_assembly', 'testing', 'completed']


class AssemblyTracking(db.Model):
    __tablename__ = 'assembly_tracking'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    stage = db.Column(db.String(30), default='in_assembly')
    progress_notes = db.Column(db.Text)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
