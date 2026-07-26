# Predefined PC Build & Custom Build
from datetime import datetime
from app import db


class PcBuild(db.Model):
    __tablename__ = 'pc_builds'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    build_type = db.Column(db.String(50))  # gaming, office, budget
    description = db.Column(db.Text)
    total_price = db.Column(db.Numeric(12, 2), default=0)
    image_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    # Simple stock model for cart quantity enforcement.
    # In this app, we treat each build as a purchasable unit with limited quantity.
    stock = db.Column(db.Integer, nullable=False, default=25)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    build_components = db.relationship('BuildComponent', backref='pc_build', lazy='dynamic', cascade='all, delete-orphan')


class BuildComponent(db.Model):
    __tablename__ = 'build_components'
    id = db.Column(db.Integer, primary_key=True)
    pc_build_id = db.Column(db.Integer, db.ForeignKey('pc_builds.id', ondelete='CASCADE'), nullable=False)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CustomBuild(db.Model):
    __tablename__ = 'custom_builds'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(150))
    total_price = db.Column(db.Numeric(12, 2), default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    custom_components = db.relationship('CustomBuildComponent', backref='custom_build', lazy='dynamic', cascade='all, delete-orphan')


class CustomBuildComponent(db.Model):
    __tablename__ = 'custom_build_components'
    id = db.Column(db.Integer, primary_key=True)
    custom_build_id = db.Column(db.Integer, db.ForeignKey('custom_builds.id', ondelete='CASCADE'), nullable=False)
    component_id = db.Column(db.Integer, db.ForeignKey('components.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
