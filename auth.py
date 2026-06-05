import bcrypt
import jwt
import secrets
import string
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, current_app

from models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        return False


def generate_invite_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_token(user_id: int, family_id: int, role: str) -> str:
    payload = {
        'user_id': user_id,
        'family_id': family_id,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(days=30),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET'], algorithm='HS256')


def decode_token(token: str):
    try:
        return jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=['HS256'])
    except jwt.PyJWTError:
        return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': '未登录'}), 401
        token = auth[7:].strip()
        payload = decode_token(token)
        if not payload:
            return jsonify({'error': 'token 无效或已过期'}), 401
        user = User.query.get(payload['user_id'])
        if not user:
            return jsonify({'error': '用户不存在'}), 401
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def parent_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if request.current_user.role != 'parent':
            return jsonify({'error': '仅家长可操作'}), 403
        return fn(*args, **kwargs)
    return wrapper


def child_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if request.current_user.role != 'child':
            return jsonify({'error': '仅儿童可操作'}), 403
        return fn(*args, **kwargs)
    return wrapper
