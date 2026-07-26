# Saved delivery addresses (one User -> many Addresses)
from datetime import datetime
from app import db


class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    label = db.Column(db.String(40))            # Home, Office, ...
    full_name = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    line1 = db.Column(db.String(255), nullable=False)  # street / house / area
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('addresses', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'label': self.label,
            'full_name': self.full_name,
            'phone': self.phone,
            'line1': self.line1,
            'city': self.city,
            'postal_code': self.postal_code,
            'is_default': bool(self.is_default),
            # Single-line form used by the checkout shipping field.
            'one_line': ', '.join(
                p for p in [self.full_name, self.phone, self.line1, self.city, self.postal_code] if p
            ),
        }
