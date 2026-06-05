import os
import uuid
from io import BytesIO
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from PIL import Image
from sqlalchemy import func

from models import (
    db, Family, User, Task, Checkin, PointBalance,
    PointTransaction, Product, Order,
)
from auth import (
    hash_password, verify_password, generate_invite_code,
    generate_token, login_required, parent_required,
)

def get_today():
    """北京时间早6点为日切点"""
    from datetime import timezone
    bj = timezone(timedelta(hours=8))
    now = datetime.now(bj)
    if now.hour < 6:
        return (now - timedelta(days=1)).date()
    return now.date()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_DIR, exist_ok=True)

# 图片压缩配置：最大宽度480px，WebP质量80
IMAGE_MAX_WIDTH = 480
IMAGE_WEBP_QUALITY = 80


def save_compressed_image(file_storage):
    """读取上传文件 → 等比缩放到 IMAGE_MAX_WIDTH → 转 WebP → 保存，返回文件名"""
    img = Image.open(file_storage)
    img = img.convert('RGB')  # 统一为 RGB，去掉 alpha 通道

    w, h = img.size
    if w > IMAGE_MAX_WIDTH:
        ratio = IMAGE_MAX_WIDTH / w
        img = img.resize((IMAGE_MAX_WIDTH, int(h * ratio)), Image.LANCZOS)

    fname = f'{uuid.uuid4().hex}.webp'
    save_path = os.path.join(UPLOAD_DIR, secure_filename(fname))
    img.save(save_path, 'WEBP', quality=IMAGE_WEBP_QUALITY)
    return fname


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    db_path = os.path.join(BASE_DIR, 'kids_tasks.db')
    database_url = os.getenv('DATABASE_URL') or f'sqlite:///{db_path}'
    if database_url.startswith('mysql://'):
        database_url = database_url.replace('mysql://', 'mysql+pymysql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'kids-tasks-super-secret-key-please-change-2026')
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8MB
    db.init_app(app)

    # ===================== 前端入口 =====================
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/static/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(UPLOAD_DIR, filename)

    # ===================== 认证 =====================
    @app.post('/api/auth/register')
    def register():
        data = request.get_json(force=True, silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        role = data.get('role')
        avatar = data.get('avatar_emoji') or '😊'
        invite_code = (data.get('invite_code') or '').strip().upper()

        if not username or not password or role not in ('child', 'parent'):
            return jsonify({'error': '请填写完整信息'}), 400

        if role == 'child':
            # 小朋友必须提供邀请码加入已有家庭
            if not invite_code:
                return jsonify({'error': '小朋友注册需要输入家长提供的家庭邀请码'}), 400
            family = Family.query.filter_by(invite_code=invite_code).first()
            if not family:
                return jsonify({'error': '邀请码无效，请找家长确认'}), 400
        else:
            # 家长自动创建新家庭
            code = generate_invite_code()
            while Family.query.filter_by(invite_code=code).first():
                code = generate_invite_code()
            family = Family(invite_code=code)
            db.session.add(family)
            db.session.flush()

        if User.query.filter_by(family_id=family.id, username=username).first():
            return jsonify({'error': '该家庭已存在同名用户'}), 400

        user = User(
            family_id=family.id,
            username=username,
            password_hash=hash_password(password),
            role=role,
            avatar_emoji=avatar,
        )
        db.session.add(user)
        db.session.flush()

        if role == 'child':
            db.session.add(PointBalance(family_id=family.id, child_id=user.id))

        db.session.commit()

        token = generate_token(user.id, family.id, role)
        return jsonify({
            'token': token,
            'user': user.to_dict(),
            'family': {'id': family.id, 'invite_code': family.invite_code},
        })

    @app.post('/api/auth/login')
    def login():
        data = request.get_json(force=True, silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return jsonify({'error': '请填写完整'}), 400

        users = User.query.filter_by(username=username).all()
        user = next((u for u in users if verify_password(password, u.password_hash)), None)
        if not user:
            return jsonify({'error': '用户名或密码错误'}), 401

        family = Family.query.get(user.family_id)
        token = generate_token(user.id, user.family_id, user.role)
        return jsonify({
            'token': token,
            'user': user.to_dict(),
            'family': {'id': family.id, 'invite_code': family.invite_code},
        })

    @app.get('/api/auth/me')
    @login_required
    def me():
        u = request.current_user
        family = Family.query.get(u.family_id)
        return jsonify({
            'user': u.to_dict(),
            'family': {'id': family.id, 'invite_code': family.invite_code},
        })

    @app.post('/api/auth/change-password')
    @login_required
    def change_password():
        data = request.get_json() or {}
        old_pwd = data.get('old_password', '').strip()
        new_pwd = data.get('new_password', '').strip()
        if not old_pwd or not new_pwd:
            return jsonify({'error': '请填写完整'}), 400
        if len(new_pwd) < 4:
            return jsonify({'error': '新密码至少4位'}), 400
        u = request.current_user
        if not verify_password(old_pwd, u.password_hash):
            return jsonify({'error': '原密码错误'}), 400
        u.password_hash = hash_password(new_pwd)
        db.session.commit()
        return jsonify({'message': '密码修改成功 ✓'})

    # ===================== 家庭 =====================
    @app.post('/api/family/create')
    @login_required
    def family_create():
        # 已通过注册创建，这里保留接口
        u = request.current_user
        family = Family.query.get(u.family_id)
        return jsonify({'invite_code': family.invite_code})

    @app.post('/api/family/join')
    @login_required
    def family_join():
        data = request.get_json(force=True, silent=True) or {}
        code = (data.get('invite_code') or '').strip().upper()
        family = Family.query.filter_by(invite_code=code).first()
        if not family:
            return jsonify({'error': '邀请码无效'}), 400
        u = request.current_user
        u.family_id = family.id
        db.session.commit()
        return jsonify({'ok': True, 'invite_code': family.invite_code})

    # ===================== 任务 =====================
    @app.get('/api/tasks')
    @login_required
    def tasks_list():
        u = request.current_user
        items = Task.query.filter_by(family_id=u.family_id, is_active=True).order_by(
            Task.sort_order.asc(), Task.id.asc()
        ).all()
        return jsonify([t.to_dict() for t in items])

    @app.post('/api/tasks')
    @parent_required
    def task_create():
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '请输入任务名'}), 400
        try:
            points = int(data.get('points', 0))
        except (TypeError, ValueError):
            return jsonify({'error': '积分必须是数字'}), 400
        if points == 0:
            return jsonify({'error': '积分不能为 0'}), 400
        if abs(points) > 9999:
            return jsonify({'error': '积分绝对值太大'}), 400

        import json as _json
        repeat_type = data.get('repeat_type', 'daily')
        if repeat_type not in ('daily', 'weekly', 'monthly', 'fixed'):
            repeat_type = 'daily'
        repeat_config = _json.dumps(data.get('repeat_config', []))
        assigned_to = _json.dumps(data.get('assigned_to', []))
        t = Task(
            family_id=u.family_id,
            name=name,
            emoji=data.get('emoji') or '⭐',
            points=points,
            is_daily=(repeat_type == 'daily'),
            repeat_type=repeat_type,
            repeat_config=repeat_config,
            assigned_to=assigned_to,
            sort_order=int(data.get('sort_order', 0) or 0),
            category=(data.get('category') or '').strip(),
        )
        db.session.add(t)
        db.session.commit()
        return jsonify(t.to_dict())

    @app.put('/api/tasks/<int:tid>')
    @parent_required
    def task_update(tid):
        u = request.current_user
        t = Task.query.filter_by(id=tid, family_id=u.family_id).first()
        if not t:
            return jsonify({'error': '任务不存在'}), 404
        data = request.get_json(force=True, silent=True) or {}
        if 'name' in data and data['name']:
            t.name = data['name'].strip()
        if 'emoji' in data:
            t.emoji = data['emoji'] or '⭐'
        if 'points' in data:
            try:
                pts = int(data['points'])
                if pts != 0:
                    t.points = pts
            except (TypeError, ValueError):
                pass
        if 'points_mode' in data and 'points' in data:
            try:
                pts = int(data['points'])
                if data['points_mode'] == 'penalty' and pts > 0:
                    t.points = -pts
                elif data['points_mode'] == 'reward' and pts < 0:
                    t.points = abs(pts)
            except (TypeError, ValueError):
                pass
        if 'is_daily' in data:
            t.is_daily = bool(data['is_daily'])
        import json as _json
        if 'repeat_type' in data:
            rt = data['repeat_type']
            if rt in ('daily', 'weekly', 'monthly', 'fixed'):
                t.repeat_type = rt
                t.is_daily = (rt == 'daily')
        if 'repeat_config' in data:
            t.repeat_config = _json.dumps(data['repeat_config'])
        if 'assigned_to' in data:
            t.assigned_to = _json.dumps(data['assigned_to'])
        if 'is_active' in data:
            t.is_active = bool(data['is_active'])
        if 'sort_order' in data:
            try:
                t.sort_order = int(data['sort_order'])
            except (TypeError, ValueError):
                pass
        if 'category' in data:
            t.category = (data['category'] or '').strip()
        db.session.commit()
        return jsonify(t.to_dict())

    @app.delete('/api/tasks/<int:tid>')
    @parent_required
    def task_delete(tid):
        u = request.current_user
        t = Task.query.filter_by(id=tid, family_id=u.family_id).first()
        if not t:
            return jsonify({'error': '任务不存在'}), 404
        t.is_active = False
        db.session.commit()
        return jsonify({'ok': True})

    @app.put('/api/tasks/sort')
    @parent_required
    def tasks_sort():
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        task_ids = data.get('task_ids', [])
        if not task_ids:
            return jsonify({'error': '缺少任务ID列表'}), 400
        for idx, tid in enumerate(task_ids):
            t = Task.query.filter_by(id=tid, family_id=u.family_id).first()
            if t:
                t.sort_order = idx
        db.session.commit()
        return jsonify({'ok': True})

    # ===================== 打卡 =====================
    @app.get('/api/checkins/today')
    @login_required
    def checkins_today():
        u = request.current_user
        today = get_today()

        if u.role == 'child':
            child_id = u.id
        else:
            # 家长查看家庭某孩子今日打卡（可选 child_id 参数，默认第一个孩子）
            child_id = request.args.get('child_id', type=int)
            if not child_id:
                child = User.query.filter_by(family_id=u.family_id, role='child').first()
                if not child:
                    return jsonify({'tasks': [], 'child_id': None})
                child_id = child.id

        tasks = Task.query.filter_by(family_id=u.family_id, is_active=True).order_by(
            Task.sort_order.asc(), Task.id.asc()
        ).all()

        # 按 repeat_type 过滤当天该显示的任务
        import json as _json
        def task_is_today(task):
            rt = task.repeat_type or 'daily'
            if rt == 'daily':
                return True
            try:
                rc = _json.loads(task.repeat_config) if task.repeat_config else []
            except (ValueError, TypeError):
                rc = []
            if rt == 'weekly':
                # rc = [0,1,2,...] 0=周一 6=周日
                return today.weekday() in rc
            if rt == 'monthly':
                # rc = [1,5,15,...] 每月几号
                return today.day in rc
            if rt == 'fixed':
                # rc = ['2026-06-01','2026-06-15'] 具体日期列表
                today_str = today.isoformat()
                return today_str in rc
            return True

        tasks = [t for t in tasks if task_is_today(t)]

        # 按 assigned_to 过滤：空=所有小朋友可见，否则只有指定小朋友可见
        def task_assigned_to_child(task):
            at = task._get_assigned_to()
            if not at:
                return True  # 分配给所有
            return child_id in at
        tasks = [t for t in tasks if task_assigned_to_child(t)]

        checkins = Checkin.query.filter_by(
            family_id=u.family_id,
            child_id=child_id,
            check_date=today,
        ).all()
        check_map = {c.task_id: c for c in checkins}

        result = []
        for t in tasks:
            c = check_map.get(t.id)
            result.append({
                **t.to_dict(),
                'checkin_status': c.status if c else None,
                'checkin_id': c.id if c else None,
            })
        return jsonify({'tasks': result, 'child_id': child_id})

    @app.post('/api/checkins/submit')
    @login_required
    def checkins_submit():
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        task_ids = data.get('task_ids') or []
        if not isinstance(task_ids, list) or not task_ids:
            return jsonify({'error': '请选择要打卡的任务'}), 400

        # 确定打卡的儿童
        if u.role == 'parent':
            child_id = data.get('child_id')
            if not child_id:
                return jsonify({'error': '请指定儿童'}), 400
            child = User.query.filter_by(id=child_id, family_id=u.family_id, role='child').first()
            if not child:
                return jsonify({'error': '儿童不存在'}), 404
        elif u.role == 'child':
            child = u
        else:
            return jsonify({'error': '无权限'}), 403

        today = get_today()
        created = []
        for tid in task_ids:
            try:
                tid = int(tid)
            except (TypeError, ValueError):
                continue
            t = Task.query.filter_by(id=tid, family_id=u.family_id, is_active=True).first()
            if not t:
                continue
            exists = Checkin.query.filter_by(
                family_id=u.family_id,
                child_id=child.id,
                task_id=t.id,
                check_date=today,
            ).first()
            if exists:
                # 如果是被拒绝的任务，允许重新申请
                if exists.status == 'rejected':
                    exists.status = 'pending'
                    exists.confirmed_by = None
                    exists.confirmed_at = None
                    created.append(t.id)
                continue
            c = Checkin(
                family_id=u.family_id,
                child_id=child.id,
                task_id=t.id,
                check_date=today,
                points=t.points,
                status='pending',
            )
            db.session.add(c)
            created.append(t.id)
        db.session.commit()
        return jsonify({'ok': True, 'created_count': len(created)})

    @app.get('/api/checkins/pending')
    @parent_required
    def checkins_pending():
        u = request.current_user
        rows = (db.session.query(Checkin, Task, User)
                .join(Task, Checkin.task_id == Task.id)
                .join(User, Checkin.child_id == User.id)
                .filter(Checkin.family_id == u.family_id, Checkin.status == 'pending')
                .order_by(Checkin.created_at.desc())
                .all())
        return jsonify([{
            'id': c.id,
            'task_id': t.id,
            'task_name': t.name,
            'task_emoji': t.emoji,
            'points': c.points,
            'check_date': c.check_date.isoformat(),
            'child_id': u2.id,
            'child_name': u2.username,
            'child_avatar': u2.avatar_emoji,
            'created_at': c.created_at.isoformat() if c.created_at else None,
        } for c, t, u2 in rows])

    @app.post('/api/checkins/reset-today')
    @parent_required
    def checkins_reset_today():
        u = request.current_user
        today = get_today()
        rows = (Checkin.query
                .filter(Checkin.family_id == u.family_id, Checkin.check_date == today)
                .order_by(Checkin.id.asc())
                .all())
        removed = 0
        reversed_confirmed = 0
        reversed_points = 0
        for c in rows:
            if c.status == 'confirmed':
                balance = PointBalance.query.filter_by(child_id=c.child_id).first()
                if balance:
                    balance.balance = max(0, balance.balance - c.points)
                    if c.points >= 0:
                        balance.total_earned = max(0, balance.total_earned - c.points)
                        tx = PointTransaction.query.filter_by(reference_id=c.id, type='earn').first()
                    else:
                        balance.total_deducted = max(0, balance.total_deducted - abs(c.points))
                        tx = PointTransaction.query.filter_by(reference_id=c.id, type='deduct').first()
                    if tx:
                        db.session.delete(tx)
                reversed_confirmed += 1
                reversed_points += int(c.points or 0)
            db.session.delete(c)
            removed += 1
        db.session.commit()
        return jsonify({
            'ok': True,
            'message': f'已重置今日任务：删除 {removed} 条记录，回滚 {reversed_confirmed} 条已确认打卡，共 {reversed_points} 分',
            'removed_count': removed,
            'reversed_confirmed_count': reversed_confirmed,
            'reversed_points': reversed_points,
        })

    @app.post('/api/checkins/<int:cid>/confirm')
    @parent_required
    def checkin_confirm(cid):
        u = request.current_user

        c = Checkin.query.filter_by(id=cid, family_id=u.family_id).first()
        if not c:
            return jsonify({'error': '打卡记录不存在'}), 404
        if c.status != 'pending':
            return jsonify({'error': '该打卡已处理'}), 400

        c.status = 'confirmed'
        c.confirmed_by = u.id
        c.confirmed_at = datetime.utcnow()

        balance = PointBalance.query.filter_by(child_id=c.child_id).first()
        if not balance:
            balance = PointBalance(family_id=u.family_id, child_id=c.child_id)
            db.session.add(balance)
            db.session.flush()
        balance.balance += c.points
        if c.points >= 0:
            balance.total_earned += c.points
            tx_type = 'earn'
        else:
            balance.total_deducted += abs(c.points)
            tx_type = 'deduct'

        t = Task.query.get(c.task_id)
        tx = PointTransaction(
            family_id=u.family_id,
            child_id=c.child_id,
            amount=c.points,
            balance_after=balance.balance,
            type=tx_type,
            reference_id=c.id,
            description=f'完成任务：{t.name if t else "任务"}',
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'ok': True, 'balance': balance.balance})

    @app.post('/api/checkins/<int:cid>/reject')
    @parent_required
    def checkin_reject(cid):
        u = request.current_user
        c = Checkin.query.filter_by(id=cid, family_id=u.family_id).first()
        if not c:
            return jsonify({'error': '打卡记录不存在'}), 404
        if c.status != 'pending':
            return jsonify({'error': '该打卡已处理'}), 400
        c.status = 'rejected'
        c.confirmed_by = u.id
        c.confirmed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'ok': True})

    @app.post('/api/checkins/apply-penalty')
    @parent_required
    def checkin_apply_penalty():
        """家长主动对某孩子执行减分任务（不需要孩子先提交）"""
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        task_id = data.get('task_id')
        child_id = data.get('child_id')
        if not task_id or not child_id:
            return jsonify({'error': '请选择任务和孩子'}), 400

        t = Task.query.filter_by(id=task_id, family_id=u.family_id, is_active=True).first()
        if not t:
            return jsonify({'error': '任务不存在'}), 404
        if t.points >= 0:
            return jsonify({'error': '该任务不是减分任务'}), 400

        child = User.query.filter_by(id=child_id, family_id=u.family_id, role='child').first()
        if not child:
            return jsonify({'error': '孩子不存在'}), 404

        today = get_today()
        # 检查今天是否已对该孩子执行过此任务
        exists = Checkin.query.filter_by(
            family_id=u.family_id, child_id=child_id,
            task_id=t.id, check_date=today,
        ).first()
        if exists:
            return jsonify({'error': '今天已对该孩子执行过此减分任务'}), 400

        # 创建打卡记录并直接确认
        c = Checkin(
            family_id=u.family_id,
            child_id=child_id,
            task_id=t.id,
            check_date=today,
            points=t.points,
            status='confirmed',
            confirmed_by=u.id,
            confirmed_at=datetime.utcnow(),
        )
        db.session.add(c)
        db.session.flush()

        # 扣减积分
        balance = PointBalance.query.filter_by(child_id=child_id).first()
        if not balance:
            balance = PointBalance(family_id=u.family_id, child_id=child_id)
            db.session.add(balance)
            db.session.flush()
        balance.balance += t.points  # t.points 是负数
        balance.total_deducted += abs(t.points)

        tx = PointTransaction(
            family_id=u.family_id,
            child_id=child_id,
            amount=t.points,
            balance_after=balance.balance,
            type='deduct',
            reference_id=c.id,
            description=f'减分任务：{t.name}',
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'ok': True, 'balance': balance.balance, 'child_name': child.username})

    # ===================== 商品 =====================
    @app.get('/api/products')
    @login_required
    def products_list():
        u = request.current_user
        items = Product.query.filter_by(family_id=u.family_id, is_active=True).order_by(
            Product.sort_order.asc(), Product.id.asc()
        ).all()
        return jsonify([p.to_dict() for p in items])

    @app.post('/api/products')
    @parent_required
    def product_create():
        u = request.current_user
        # 支持 JSON 或表单（带图片上传）
        if request.content_type and 'multipart/form-data' in request.content_type:
            name = (request.form.get('name') or '').strip()
            price = request.form.get('price', type=int) or 0
            stock = request.form.get('stock', type=int)
            stock = stock if stock is not None else -1
            quantity = request.form.get('quantity', type=int) or 1
            unit = (request.form.get('unit') or '').strip()
            category = (request.form.get('category') or '').strip()
            image_url = None
            file = request.files.get('image')
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext not in ALLOWED_EXT:
                    return jsonify({'error': '图片格式不支持'}), 400
                fname = save_compressed_image(file)
                image_url = f'/static/uploads/{fname}'
        else:
            data = request.get_json(force=True, silent=True) or {}
            name = (data.get('name') or '').strip()
            price = int(data.get('price') or 0)
            stock = int(data.get('stock', -1))
            quantity = int(data.get('quantity', 1))
            unit = (data.get('unit') or '').strip()
            category = (data.get('category') or '').strip()
            image_url = data.get('image_url')

        if not name or price <= 0:
            return jsonify({'error': '名称和价格不能为空'}), 400

        # 新商品置顶：获取当前最小 sort_order，新商品设为更小值
        min_order = db.session.query(db.func.min(Product.sort_order)).filter_by(
            family_id=u.family_id, is_active=True
        ).scalar()
        top_order = (min_order or 0) - 1

        p = Product(
            family_id=u.family_id,
            name=name,
            image_url=image_url,
            price=price,
            stock=stock,
            quantity=quantity,
            unit=unit,
            category=category,
            sort_order=top_order,
        )
        db.session.add(p)
        db.session.commit()
        return jsonify(p.to_dict())

    @app.put('/api/products/<int:pid>')
    @parent_required
    def product_update(pid):
        u = request.current_user
        p = Product.query.filter_by(id=pid, family_id=u.family_id).first()
        if not p:
            return jsonify({'error': '商品不存在'}), 404

        if request.content_type and 'multipart/form-data' in request.content_type:
            if request.form.get('name'):
                p.name = request.form['name'].strip()
            price = request.form.get('price', type=int)
            if price and price > 0:
                p.price = price
            stock = request.form.get('stock', type=int)
            if stock is not None:
                p.stock = stock
            quantity = request.form.get('quantity', type=int)
            if quantity is not None:
                p.quantity = quantity
            unit = request.form.get('unit')
            if unit is not None:
                p.unit = unit.strip()
            category = request.form.get('category')
            if category is not None:
                p.category = category.strip()
            file = request.files.get('image')
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext in ALLOWED_EXT:
                    fname = save_compressed_image(file)
                    p.image_url = f'/static/uploads/{fname}'
        else:
            data = request.get_json(force=True, silent=True) or {}
            if data.get('name'):
                p.name = data['name'].strip()
            if data.get('price'):
                try:
                    if int(data['price']) > 0:
                        p.price = int(data['price'])
                except (TypeError, ValueError):
                    pass
            if 'stock' in data:
                try:
                    p.stock = int(data['stock'])
                except (TypeError, ValueError):
                    pass
            if 'quantity' in data:
                try:
                    p.quantity = int(data['quantity'])
                except (TypeError, ValueError):
                    pass
            if 'unit' in data:
                p.unit = (data['unit'] or '').strip()
            if 'category' in data:
                p.category = (data['category'] or '').strip()
            if 'is_active' in data:
                p.is_active = bool(data['is_active'])
            if 'image_url' in data:
                p.image_url = data['image_url']
        db.session.commit()
        return jsonify(p.to_dict())

    @app.delete('/api/products/<int:pid>')
    @parent_required
    def product_delete(pid):
        u = request.current_user
        p = Product.query.filter_by(id=pid, family_id=u.family_id).first()
        if not p:
            return jsonify({'error': '商品不存在'}), 404
        p.is_active = False
        db.session.commit()
        return jsonify({'ok': True})

    @app.post('/api/products/clear-soldout')
    @parent_required
    def clear_soldout():
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        password = (data.get('password') or '').strip()
        if not password:
            return jsonify({'error': '请输入密码'}), 400
        if not verify_password(password, u.password_hash):
            return jsonify({'error': '密码不正确'}), 403
        count = Product.query.filter_by(
            family_id=u.family_id, stock=0, is_active=True
        ).update({'is_active': False})
        db.session.commit()
        return jsonify({'ok': True, 'count': count})

    # ===================== 订单/购买 =====================
    @app.post('/api/orders/create')
    @login_required
    def order_create():
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        pid = data.get('product_id')
        if not pid:
            return jsonify({'error': '请选择商品'}), 400
        p = Product.query.filter_by(id=pid, family_id=u.family_id, is_active=True).first()
        if not p:
            return jsonify({'error': '商品不存在'}), 404
        if p.stock == 0:
            return jsonify({'error': '商品已售罄'}), 400

        # 家长代买时指定 child_id，否则用当前用户
        if u.role == 'parent':
            child_id = data.get('child_id')
            if not child_id:
                return jsonify({'error': '请指定儿童'}), 400
            child = User.query.filter_by(id=child_id, family_id=u.family_id, role='child').first()
            if not child:
                return jsonify({'error': '儿童不存在'}), 404
        else:
            child = u

        balance = PointBalance.query.filter_by(child_id=child.id).first()
        if not balance or balance.balance < p.price:
            return jsonify({'error': '积分不足'}), 400

        # 检查是否已有同商品 pending 订单
        # 这里不做严格限制，允许重复发起
        o = Order(
            family_id=u.family_id,
            child_id=child.id,
            product_id=p.id,
            points_cost=p.price,
            status='confirmed',
            confirmed_by=u.id,
            confirmed_at=datetime.utcnow(),
        )
        db.session.add(o)

        # 自动扣减积分和库存
        if p.stock > 0:
            p.stock -= 1
        balance.balance -= p.price
        balance.total_spent += p.price

        tx = PointTransaction(
            family_id=u.family_id,
            child_id=child.id,
            amount=-p.price,
            balance_after=balance.balance,
            type='spend',
            reference_id=o.id,
            description=f'兑换商品：{p.name}',
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'ok': True, 'order_id': o.id, 'balance': balance.balance})

    @app.get('/api/orders/pending')
    @parent_required
    def orders_pending():
        u = request.current_user
        rows = (db.session.query(Order, Product, User)
                .join(Product, Order.product_id == Product.id)
                .join(User, Order.child_id == User.id)
                .filter(Order.family_id == u.family_id, Order.status == 'pending')
                .order_by(Order.created_at.desc()).all())
        return jsonify([{
            'id': o.id,
            'product_id': p.id,
            'product_name': p.name,
            'product_image': p.image_url,
            'points_cost': o.points_cost,
            'child_id': cu.id,
            'child_name': cu.username,
            'child_avatar': cu.avatar_emoji,
            'created_at': o.created_at.isoformat() if o.created_at else None,
        } for o, p, cu in rows])

    @app.get('/api/orders/history')
    @login_required
    def orders_history():
        u = request.current_user
        q = (db.session.query(Order, Product)
             .join(Product, Order.product_id == Product.id)
             .filter(Order.family_id == u.family_id))
        if u.role == 'child':
            q = q.filter(Order.child_id == u.id)
        else:
            # 家长可按 child_id 过滤
            child_id = request.args.get('child_id', type=int)
            if child_id:
                q = q.filter(Order.child_id == child_id)
        rows = q.order_by(Order.created_at.desc()).limit(100).all()
        return jsonify([{
            'id': o.id,
            'product_name': p.name,
            'product_image': p.image_url,
            'points_cost': o.points_cost,
            'status': o.status,
            'created_at': o.created_at.isoformat() if o.created_at else None,
            'confirmed_at': o.confirmed_at.isoformat() if o.confirmed_at else None,
            'purchased': o.purchased,
        } for o, p in rows])

    @app.get('/api/orders/confirmed')
    @parent_required
    def orders_confirmed():
        u = request.current_user
        rows = (db.session.query(Order, Product, User)
                .join(Product, Order.product_id == Product.id)
                .join(User, Order.child_id == User.id)
                .filter(Order.family_id == u.family_id, Order.status == 'confirmed')
                .order_by(Order.confirmed_at.desc()).all())
        return jsonify([{
            'id': o.id,
            'product_id': p.id,
            'product_name': p.name,
            'product_image': p.image_url,
            'points_cost': o.points_cost,
            'child_id': cu.id,
            'child_name': cu.username,
            'child_avatar': cu.avatar_emoji,
            'purchased': o.purchased,
            'created_at': o.created_at.isoformat() if o.created_at else None,
            'confirmed_at': o.confirmed_at.isoformat() if o.confirmed_at else None,
        } for o, p, cu in rows])

    @app.post('/api/orders/<int:oid>/purchased')
    @parent_required
    def order_purchased(oid):
        u = request.current_user
        o = Order.query.filter_by(id=oid, family_id=u.family_id).first()
        if not o:
            return jsonify({'error': '订单不存在'}), 404
        if o.status != 'confirmed':
            return jsonify({'error': '订单未确认'}), 400
        o.purchased = True
        db.session.commit()
        return jsonify({'ok': True})
    @app.post("/api/orders/<int:oid>/cancel")
    @login_required
    def order_cancel(oid):
        u = request.current_user
        o = Order.query.filter_by(id=oid, family_id=u.family_id).first()
        if not o:
            return jsonify({"error": "订单不存在"}), 404
        if o.status != "confirmed" or o.purchased:
            return jsonify({"error": "该订单无法撤回"}), 400
        # 儿童只能撤回自己的订单，家长可以撤回任意订单
        if u.role == "child" and o.child_id != u.id:
            return jsonify({"error": "无权操作"}), 403
        # 退还积分
        balance = PointBalance.query.filter_by(child_id=o.child_id).first()
        if balance:
            balance.balance += o.points_cost
            balance.total_spent -= o.points_cost
        # 恢复库存
        product = Product.query.get(o.product_id)
        if product and product.stock >= 0:
            product.stock += 1
        # 记录退还流水
        tx = PointTransaction(
            family_id=u.family_id,
            child_id=o.child_id,
            amount=o.points_cost,
            balance_after=balance.balance if balance else 0,
            type="refund",
            reference_id=o.id,
            description=f'撤回兑换：{product.name if product else "商品"}',
        )
        db.session.add(tx)
        # 标记订单为已撤回
        o.status = "cancelled"
        db.session.commit()
        return jsonify({"ok": True, "balance": balance.balance if balance else 0})

    @app.post('/api/orders/<int:oid>/confirm')
    @parent_required
    def order_confirm(oid):
        u = request.current_user

        o = Order.query.filter_by(id=oid, family_id=u.family_id).first()
        if not o:
            return jsonify({'error': '订单不存在'}), 404
        if o.status != 'pending':
            return jsonify({'error': '该订单已处理'}), 400

        balance = PointBalance.query.filter_by(child_id=o.child_id).first()
        if not balance or balance.balance < o.points_cost:
            return jsonify({'error': '余额不足，无法兑换'}), 400

        p = Product.query.get(o.product_id)
        if p and p.stock > 0:
            p.stock -= 1

        balance.balance -= o.points_cost
        balance.total_spent += o.points_cost

        o.status = 'confirmed'
        o.confirmed_by = u.id
        o.confirmed_at = datetime.utcnow()

        tx = PointTransaction(
            family_id=u.family_id,
            child_id=o.child_id,
            amount=-o.points_cost,
            balance_after=balance.balance,
            type='spend',
            reference_id=o.id,
            description=f'兑换商品：{p.name if p else "商品"}',
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'ok': True, 'balance': balance.balance})

    @app.post('/api/orders/<int:oid>/reject')
    @parent_required
    def order_reject(oid):
        u = request.current_user
        o = Order.query.filter_by(id=oid, family_id=u.family_id).first()
        if not o:
            return jsonify({'error': '订单不存在'}), 404
        if o.status != 'pending':
            return jsonify({'error': '该订单已处理'}), 400
        o.status = 'rejected'
        o.confirmed_by = u.id
        o.confirmed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'ok': True})

    # ===================== 积分 =====================
    @app.get('/api/points/balance')
    @login_required
    def points_balance():
        u = request.current_user
        if u.role == 'child':
            balance = PointBalance.query.filter_by(child_id=u.id).first()
            if not balance:
                balance = PointBalance(family_id=u.family_id, child_id=u.id)
                db.session.add(balance)
                db.session.commit()
            return jsonify({
                'balance': balance.balance,
                'total_earned': balance.total_earned,
                'total_spent': balance.total_spent,
                'total_deducted': balance.total_deducted,
            })
        else:
            # 家长查看所有孩子余额
            children = User.query.filter_by(family_id=u.family_id, role='child').all()
            result = []
            for c in children:
                b = PointBalance.query.filter_by(child_id=c.id).first()
                result.append({
                    'child_id': c.id,
                    'child_name': c.username,
                    'child_avatar': c.avatar_emoji,
                    'balance': b.balance if b else 0,
                    'total_earned': b.total_earned if b else 0,
                    'total_spent': b.total_spent if b else 0,
                    'total_deducted': b.total_deducted if b else 0,
                })
            return jsonify({'children': result})

    @app.get('/api/points/transactions')
    @login_required
    def points_transactions():
        u = request.current_user
        q = PointTransaction.query.filter_by(family_id=u.family_id)
        if u.role == 'child':
            q = q.filter_by(child_id=u.id)
        else:
            child_id = request.args.get('child_id', type=int)
            if child_id:
                q = q.filter_by(child_id=child_id)
        rows = q.order_by(PointTransaction.created_at.desc()).limit(100).all()
        return jsonify([r.to_dict() for r in rows])

    @app.post('/api/points/adjust')
    @parent_required
    def points_adjust():
        u = request.current_user
        data = request.get_json(force=True, silent=True) or {}
        child_id = data.get('child_id')
        amount = data.get('amount', 0)
        reason = (data.get('reason') or '').strip()
        if not child_id:
            return jsonify({'error': '请选择小朋友'}), 400
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return jsonify({'error': '分值必须是数字'}), 400
        if amount == 0:
            return jsonify({'error': '分值不能为0'}), 400
        if not reason:
            return jsonify({'error': '请填写原因'}), 400
        # 确认是自家孩子
        child = User.query.filter_by(id=child_id, family_id=u.family_id, role='child').first()
        if not child:
            return jsonify({'error': '小朋友不存在'}), 404
        balance = PointBalance.query.filter_by(child_id=child_id).first()
        if not balance:
            balance = PointBalance(family_id=u.family_id, child_id=child_id)
            db.session.add(balance)
            db.session.flush()
        balance.balance += amount
        if amount > 0:
            balance.total_earned += amount
            tx_type = 'earn'
        else:
            balance.total_deducted += abs(amount)
            tx_type = 'deduct'
        tx = PointTransaction(
            family_id=u.family_id,
            child_id=child_id,
            amount=amount,
            balance_after=balance.balance,
            type=tx_type,
            reference_id=0,
            description=reason,
        )
        db.session.add(tx)
        db.session.commit()
        return jsonify({'message': f'已{"加" if amount > 0 else "减"}{abs(amount)}分 ✓', 'balance': balance.balance})

    # ===================== 统计 =====================
    @app.get('/api/stats/overview')
    @parent_required
    def stats_overview():
        u = request.current_user
        today = get_today()
        rng = request.args.get('range', 'week')

        today_confirmed = Checkin.query.filter_by(
            family_id=u.family_id, status='confirmed', check_date=today
        ).count()
        pending_orders = Order.query.filter_by(
            family_id=u.family_id, status='pending'
        ).count()

        # 趋势数据：按 range 参数决定粒度
        if rng == 'year':
            # 最近12个月，按月汇总
            series_start = today.replace(day=1) - timedelta(days=330)
            series_start = series_start.replace(day=1)
            earn_rows = (db.session.query(
                func.date_format(Checkin.check_date, '%Y-%m'), func.sum(Checkin.points)
            ).filter(
                Checkin.family_id == u.family_id, Checkin.status == 'confirmed',
                Checkin.points >= 0, Checkin.check_date >= series_start,
            ).group_by(func.date_format(Checkin.check_date, '%Y-%m')).all())
            deduct_rows = (db.session.query(
                func.date_format(Checkin.check_date, '%Y-%m'), func.sum(Checkin.points)
            ).filter(
                Checkin.family_id == u.family_id, Checkin.status == 'confirmed',
                Checkin.points < 0, Checkin.check_date >= series_start,
            ).group_by(func.date_format(Checkin.check_date, '%Y-%m')).all())
            earn_map = {str(k): int(v) for k, v in earn_rows}
            deduct_map = {str(k): int(v) for k, v in deduct_rows}
            trend_series = []
            for i in range(12):
                m = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
                key = m.strftime('%Y-%m')
                net = earn_map.get(key, 0) + deduct_map.get(key, 0)
                trend_series.append({'date': key, 'count': net, 'label': str(m.month)})
            trend_series.reverse()
        elif rng == 'month':
            # 最近30天
            series_start = today - timedelta(days=29)
            earn_rows = (db.session.query(
                Checkin.check_date, func.sum(Checkin.points)
            ).filter(
                Checkin.family_id == u.family_id, Checkin.status == 'confirmed',
                Checkin.points >= 0, Checkin.check_date >= series_start, Checkin.check_date <= today,
            ).group_by(Checkin.check_date).all())
            deduct_rows = (db.session.query(
                Checkin.check_date, func.sum(Checkin.points)
            ).filter(
                Checkin.family_id == u.family_id, Checkin.status == 'confirmed',
                Checkin.points < 0, Checkin.check_date >= series_start, Checkin.check_date <= today,
            ).group_by(Checkin.check_date).all())
            earn_map = {d.isoformat(): int(s) for d, s in earn_rows}
            deduct_map = {d.isoformat(): int(s) for d, s in deduct_rows}
            trend_series = []
            for i in range(30):
                d = series_start + timedelta(days=i)
                key = d.isoformat()
                net = earn_map.get(key, 0) + deduct_map.get(key, 0)
                trend_series.append({'date': key, 'count': net, 'label': str(d.day)})
        else:
            # 默认本周7天
            series_start = today - timedelta(days=6)
            earn_rows = (db.session.query(
                Checkin.check_date, func.sum(Checkin.points)
            ).filter(
                Checkin.family_id == u.family_id, Checkin.status == 'confirmed',
                Checkin.points >= 0, Checkin.check_date >= series_start, Checkin.check_date <= today,
            ).group_by(Checkin.check_date).all())
            deduct_rows = (db.session.query(
                Checkin.check_date, func.sum(Checkin.points)
            ).filter(
                Checkin.family_id == u.family_id, Checkin.status == 'confirmed',
                Checkin.points < 0, Checkin.check_date >= series_start, Checkin.check_date <= today,
            ).group_by(Checkin.check_date).all())
            earn_map = {d.isoformat(): int(s) for d, s in earn_rows}
            deduct_map = {d.isoformat(): int(s) for d, s in deduct_rows}
            trend_series = []
            for i in range(7):
                d = series_start + timedelta(days=i)
                key = d.isoformat()
                net = earn_map.get(key, 0) + deduct_map.get(key, 0)
                trend_series.append({'date': key, 'count': net, 'label': ['一','二','三','四','五','六','日'][d.weekday()]})

        # 总积分收支
        earn_sum = db.session.query(func.coalesce(func.sum(PointTransaction.amount), 0)).filter(
            PointTransaction.family_id == u.family_id,
            PointTransaction.type == 'earn',
        ).scalar() or 0
        spend_sum = db.session.query(func.coalesce(func.sum(PointTransaction.amount), 0)).filter(
            PointTransaction.family_id == u.family_id,
            PointTransaction.type == 'spend',
        ).scalar() or 0
        deduct_sum = db.session.query(func.coalesce(func.sum(PointTransaction.amount), 0)).filter(
            PointTransaction.family_id == u.family_id,
            PointTransaction.type == 'deduct',
        ).scalar() or 0

        # 孩子余额
        children = User.query.filter_by(family_id=u.family_id, role='child').all()
        children_data = []
        for c in children:
            b = PointBalance.query.filter_by(child_id=c.id).first()
            children_data.append({
                'child_id': c.id,
                'child_name': c.username,
                'child_avatar': c.avatar_emoji,
                'balance': b.balance if b else 0,
            })

        return jsonify({
            'today_confirmed': today_confirmed,
            'pending_orders': pending_orders,
            'trend_series': trend_series,
            'total_earned': int(earn_sum),
            'total_spent': int(-spend_sum),
            'total_deducted': int(-deduct_sum),
            'children': children_data,
        })

    # ===================== 家庭成员 =====================
    @app.get('/api/family/members')
    @login_required
    def family_members():
        u = request.current_user
        members = User.query.filter_by(family_id=u.family_id).all()
        return jsonify([m.to_dict() for m in members])

    return app


app = create_app()

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
