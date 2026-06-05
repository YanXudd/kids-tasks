from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Family(db.Model):
    __tablename__ = 'families'
    id = db.Column(db.Integer, primary_key=True)
    invite_code = db.Column(db.String(16), unique=True, nullable=False)
    redeem_multiplier = db.Column(db.Float, default=1.0)  # 商品兑换积分倍率
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    username = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    avatar_emoji = db.Column(db.String(8), default='😊')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('family_id', 'username'),)

    def to_dict(self):
        return {
            'id': self.id,
            'family_id': self.family_id,
            'username': self.username,
            'role': self.role,
            'avatar_emoji': self.avatar_emoji,
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    emoji = db.Column(db.String(8), default='⭐')
    points = db.Column(db.Integer, nullable=False)
    is_daily = db.Column(db.Boolean, default=True)  # 保留兼容
    repeat_type = db.Column(db.String(16), default='daily')  # daily/weekly/monthly/fixed
    repeat_config = db.Column(db.Text, default='')  # JSON: weekly:[1,3,5] monthly:[1,15] fixed:['2026-06-01']
    assigned_to = db.Column(db.Text, default='')  # JSON: []=所有小朋友, [1,3]=指定小朋友
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    category = db.Column(db.String(32), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def _get_assigned_to(self):
        import json
        at = self.assigned_to or ''
        try:
            return json.loads(at) if at else []
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self):
        import json
        rc = self.repeat_config or ''
        try:
            rc = json.loads(rc) if rc else []
        except (json.JSONDecodeError, TypeError):
            rc = []
        return {
            'id': self.id,
            'name': self.name,
            'emoji': self.emoji,
            'points': self.points,
            'is_daily': bool(self.is_daily),
            'repeat_type': self.repeat_type or 'daily',
            'repeat_config': rc,
            'assigned_to': self._get_assigned_to(),
            'is_active': bool(self.is_active),
            'sort_order': self.sort_order,
            'category': self.category or '',
        }


class Checkin(db.Model):
    __tablename__ = 'checkins'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    check_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), default='pending')
    points = db.Column(db.Integer, nullable=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PointBalance(db.Model):
    __tablename__ = 'point_balances'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    balance = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Integer, default=0)
    total_deducted = db.Column(db.Integer, default=0)


class PointTransaction(db.Model):
    __tablename__ = 'point_transactions'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(16), nullable=False)
    reference_id = db.Column(db.Integer)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'balance_after': self.balance_after,
            'type': self.type,
            'reference_id': self.reference_id,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    image_url = db.Column(db.String(255))
    price = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    stock = db.Column(db.Integer, default=-1)
    quantity = db.Column(db.Integer, default=1)
    unit = db.Column(db.String(16), default='')
    category = db.Column(db.String(32), default='')
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_url': self.image_url,
            'price': self.price,
            'is_active': bool(self.is_active),
            'stock': self.stock,
            'quantity': self.quantity,
            'unit': self.unit or '',
            'category': self.category or '',
            'sort_order': self.sort_order,
        }


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('families.id'), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    points_cost = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), default='pending')
    purchased = db.Column(db.Boolean, default=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
