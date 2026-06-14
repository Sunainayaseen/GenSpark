# Vendor Management
from datetime import datetime
from app import db


class Vendor(db.Model):
    __tablename__ = 'vendors'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    shop_name = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    approval_status = db.Column(db.String(20), default='pending')  # pending, approved, blocked
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    documents = db.relationship('VendorDocument', backref='vendor', lazy='dynamic')
    ratings = db.relationship('VendorRating', backref='vendor', lazy='dynamic')
    components = db.relationship('VendorComponent', backref='vendor', lazy='dynamic')
    orders = db.relationship('Order', backref='vendor', lazy='dynamic')


class VendorDocument(db.Model):
    __tablename__ = 'vendor_documents'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    doc_type = db.Column(db.String(50))  # gstin, pan, etc.
    doc_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VendorRating(db.Model):
    __tablename__ = 'vendor_ratings'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    rating = db.Column(db.Integer)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
