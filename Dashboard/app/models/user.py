# Authentication & Role Management
from datetime import datetime
from app import db, bcrypt
from flask_login import UserMixin


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # admin, vendor, customer, rider
    users = db.relationship('User', backref='role_ref', lazy='dynamic')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, blocked
    must_change_password = db.Column(db.Boolean, default=False)  # True when admin adds user – first login = change password
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('Vendor', backref='user', uselist=False)
    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role_ref and self.role_ref.name == 'admin'

    @property
    def is_vendor(self):
        return self.role_ref and self.role_ref.name == 'vendor'

    @property
    def is_customer(self):
        return self.role_ref and self.role_ref.name == 'customer'

    @property
    def is_rider(self):
        return self.role_ref and self.role_ref.name == 'rider'

    def __repr__(self):
        return f'<User {self.email}>'
