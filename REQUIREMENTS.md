# 儿童任务打卡与积分奖励 Web 应用 - 完整需求

## 项目概述
面向 1-12 岁儿童的"任务打卡与积分奖励" Web 应用，通过"完成任务赚取积分"和"消耗积分兑换奖励"机制，帮助小朋友养成良好日常习惯。

## 技术栈
- 后端：Python Flask + SQLite
- 前端：单页面 HTML + Tailwind CSS + Alpine.js（轻量响应式）
- 认证：JWT token
- 文件上传：本地存储
- 端口：8080
- **所有代码写在一个项目里，Flask 同时 serve 前端静态文件**

## 核心功能

### 1. 多用户与权限
- 注册/登录，每个家庭独立账号
- 角色：child（儿童）和 parent（家长）
- 注册时选择角色，同一家庭通过"家庭邀请码"关联
- 数据严格隔离（按 family_id）

### 2. 任务与积分（赚取）
- 家长创建/编辑日常任务列表（如：按时起床+5分、整理玩具+10分、刷牙+3分）
- 每个任务有：名称、图标emoji、积分值、是否每日重复
- 儿童端：看到今日任务列表，勾选已完成的
- 提交后状态变为"待确认"
- 家长端：看到待确认列表，输入密码确认后积分到账
- 积分流水记录（时间、任务名、积分变动、余额）

### 3. 商店与兑换（消耗）
- 家长创建商品（名称、图片上传、积分价格）
- 儿童浏览商店，点击"想要"购买
- 系统冻结积分，状态"待确认"
- 家长输入密码确认后扣除积分，生成兑换记录
- 兑换历史（时间、商品名、花费积分）

### 4. 家长密码确认机制
- 所有涉及积分变动的操作（打卡确认、购买确认）都需要家长输入独立的操作密码
- 操作密码在注册时设置，与登录密码不同
- 前端弹窗输入密码，后端校验

## UI/UX 设计要求

### 视觉风格
- 卡通风格，圆角设计
- 主色调：明亮的橙色 #FF9500 + 天蓝色 #4FC3F7 + 草绿色 #66BB6A
- 背景：浅黄色渐变 #FFF8E1 → #FFECB3
- 大号 emoji 图标代替文字按钮
- 卡片式布局，每张卡片有阴影和圆角
- 字体：系统默认，大字号（标题 28px+，正文 18px+）

### 动画效果
- 打卡成功：金币掉落动画 + 积分数字跳动
- 购买成功：星星飞散效果
- 按钮：hover 时放大 1.1 倍 + 阴影增强
- 页面切换：淡入淡出

### 儿童端页面
1. **首页/今日任务** - 显示今日任务卡片列表，每个任务一个大卡片（emoji + 名称 + 积分数），点击勾选，底部"提交打卡"按钮
2. **我的积分** - 大号显示总积分，金币动画背景，下方积分流水列表
3. **商店** - 商品网格展示（图片 + 名称 + 积分价格），点击弹出购买确认
4. **我的兑换** - 兑换历史列表

### 家长端页面
1. **任务管理** - 任务列表 CRUD，设置名称/emoji/积分/每日重复
2. **打卡审核** - 待确认列表，一键确认（弹密码框）
3. **商品管理** - 商品 CRUD，上传图片，设置价格
4. **购买审核** - 待确认购买列表，输入密码确认
5. **数据统计** - 今日打卡数/本周打卡趋势/积分收支统计

### 通用组件
- 底部导航栏（儿童4个tab，家长5个tab）
- 密码确认弹窗（可爱的锁头图标，数字键盘输入）
- Toast 通知（成功/失败）
- 加载动画

## 数据库设计

```sql
-- 家庭表
CREATE TABLE families (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invite_code TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    pin_hash TEXT NOT NULL,  -- 操作密码（4-6位数字）
    role TEXT NOT NULL CHECK(role IN ('child', 'parent')),
    avatar_emoji TEXT DEFAULT '😊',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id),
    UNIQUE(family_id, username)
);

-- 任务模板表
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    emoji TEXT DEFAULT '⭐',
    points INTEGER NOT NULL,
    is_daily BOOLEAN DEFAULT 1,
    is_active BOOLEAN DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id)
);

-- 打卡记录表
CREATE TABLE checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    child_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    check_date DATE NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'rejected')),
    points INTEGER NOT NULL,
    confirmed_by INTEGER,
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id),
    FOREIGN KEY (child_id) REFERENCES users(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (confirmed_by) REFERENCES users(id)
);

-- 积分余额表
CREATE TABLE point_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    child_id INTEGER NOT NULL UNIQUE,
    balance INTEGER DEFAULT 0,
    total_earned INTEGER DEFAULT 0,
    total_spent INTEGER DEFAULT 0,
    FOREIGN KEY (family_id) REFERENCES families(id),
    FOREIGN KEY (child_id) REFERENCES users(id)
);

-- 积分流水表
CREATE TABLE point_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    child_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,  -- 正数=收入，负数=支出
    balance_after INTEGER NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('earn', 'spend', 'refund')),
    reference_id INTEGER,  -- checkin_id 或 order_id
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id),
    FOREIGN KEY (child_id) REFERENCES users(id)
);

-- 商品表
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    image_url TEXT,
    price INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    stock INTEGER DEFAULT -1,  -- -1=无限
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id)
);

-- 订单表
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id INTEGER NOT NULL,
    child_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    points_cost INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'rejected', 'cancelled')),
    confirmed_by INTEGER,
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (family_id) REFERENCES families(id),
    FOREIGN KEY (child_id) REFERENCES users(id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (confirmed_by) REFERENCES users(id)
);
```

## API 设计

### 认证
- POST /api/auth/register - 注册（username, password, pin, role, avatar_emoji, invite_code?）
- POST /api/auth/login - 登录（username, password）→ JWT token

### 家庭
- POST /api/family/create - 创建家庭（返回 invite_code）
- POST /api/family/join - 加入家庭（invite_code）

### 任务（家长）
- GET /api/tasks - 获取家庭任务列表
- POST /api/tasks - 创建任务
- PUT /api/tasks/:id - 更新任务
- DELETE /api/tasks/:id - 删除任务

### 打卡
- GET /api/checkins/today - 获取今日打卡状态
- POST /api/checkins/submit - 提交打卡（task_ids[]）
- GET /api/checkins/pending - 获取待确认列表（家长）
- POST /api/checkins/:id/confirm - 确认打卡（pin）
- POST /api/checkins/:id/reject - 拒绝打卡（pin）

### 商店
- GET /api/products - 获取商品列表
- POST /api/products - 创建商品（家长，含图片上传）
- PUT /api/products/:id - 更新商品
- DELETE /api/products/:id - 删除商品

### 购买
- POST /api/orders/create - 发起购买（product_id）
- GET /api/orders/pending - 获取待确认购买（家长）
- POST /api/orders/:id/confirm - 确认购买（pin）
- POST /api/orders/:id/reject - 拒绝购买（pin）

### 积分
- GET /api/points/balance - 获取积分余额
- GET /api/points/transactions - 获取积分流水

### 统计（家长）
- GET /api/stats/overview - 今日/本周统计

### 安全
- 所有 API 需要 JWT token（Authorization: Bearer xxx）
- pin 校验在后端完成，比较 bcrypt hash
- 所有数据查询都带 family_id 过滤

## 文件结构
```
kids-tasks/
├── app.py              # Flask 主应用
├── models.py           # SQLAlchemy 模型
├── auth.py             # 认证逻辑
├── requirements.txt    # Python 依赖
├── static/
│   ├── uploads/        # 上传的图片
│   └── app.js          # 前端 JS（Alpine.js + 动画）
├── templates/
│   └── index.html      # 单页面主模板
└── init_db.py          # 数据库初始化脚本
```

## 重要注意
1. 所有前端代码写在 index.html 里（内嵌 CSS 和 JS），使用 CDN 引入 Tailwind CSS 和 Alpine.js
2. app.js 处理路由和业务逻辑
3. Flask 使用 jsonify 返回 JSON
4. 图片上传存到 static/uploads/，返回可访问的 URL
5. JWT secret key 写在配置里（简单项目不需要环境变量）
6. 监听 0.0.0.0:8080
7. 初始化时创建一个演示家庭（用户名 demo_child / demo_parent，密码 123456，操作密码 0000）
