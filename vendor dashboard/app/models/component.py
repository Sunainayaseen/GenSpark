# Component Inventory
from datetime import datetime
from app import db


class ComponentCategory(db.Model):
    __tablename__ = 'component_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Processor, RAM, GPU, etc.
    slug = db.Column(db.String(100), unique=True)
    components = db.relationship('Component', backref='category', lazy='dynamic')


class ComponentBrand(db.Model):
    """Maps to existing DB table: genspark_erp.brands (brand_id, brand_name)."""
    __tablename__ = 'brands'
    id = db.Column('brand_id', db.Integer, primary_key=True, autoincrement=True)
    name = db.Column('brand_name', db.String(50), nullable=False)
    components = db.relationship('Component', backref='brand', lazy='dynamic')


class Component(db.Model):
    __tablename__ = 'components'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('component_categories.id'), nullable=False)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.brand_id'), nullable=True)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(12, 2), default=0)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(255))
    specs = db.Column(db.JSON)  # optional JSON for specs
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    vendor_links = db.relationship('VendorComponent', backref='component', lazy='dynamic')
    build_components = db.relationship('BuildComponent', backref='component', lazy='dynamic')


class VendorComponent(db.Model):
    """Per-vendor stock & price for a component (FYP spec: vendor_inventory)."""
    __tablename__ = 'vendor_components'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Numeric(12, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
