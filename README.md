# 🌟 小任务大冒险 — 儿童任务打卡积分系统

一个面向 3-12 岁儿童的家庭任务打卡与积分奖励系统。家长创建任务，孩子打卡完成，家长审核确认后获得积分，积分可在奖励商店兑换商品。

## ✨ 功能特性

### 👨‍👩‍👧 家长端
- **任务管理** — 创建奖励/减分任务，设置每日/每周/每月/固定日期重复
- **打卡审核** — 审核孩子提交的打卡记录，确认或拒绝
- **商品管理** — 创建奖励商品，设置价格、库存、分类
- **积分调整** — 手动为孩子加减积分
- **数据统计** — 查看打卡趋势、积分统计、孩子排名
- **多孩支持** — 一个家庭支持多个孩子，可独立查看各孩子视角

### 🧒 儿童端
- **今日任务** — 查看当天任务列表，一键打卡提交
- **积分查看** — 查看当前积分、累计获得/扣除/消费
- **奖励商店** — 浏览商品，用积分兑换心仪奖励
- **兑换记录** — 查看历史兑换记录

### 🎨 界面特色
- 卡通风格 UI，色彩鲜明，适合儿童使用
- 支持自定义 emoji 头像
- 积分变动动画效果
- 响应式设计，适配手机和平板

## 🛠️ 技术栈

- **后端** — Python 3.11 + Flask + Gunicorn
- **数据库** — MySQL 8.0（支持 SQLite 本地开发）
- **前端** — Alpine.js + Tailwind CSS（CDN）
- **图片处理** — Pillow（上传图片自动压缩）
- **部署** — Docker + Docker Compose

## 📦 快速开始

### 1. 克隆仓库
```bash
git clone https://github.com/YanXudd/kids-tasks.git
cd kids-tasks
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入数据库连接信息
```

### 3. Docker 部署（推荐）
```bash
docker compose up -d --build
```

访问 `http://localhost:8088` 即可使用。

### 4. 本地开发
```bash
pip install -r requirements.txt
python app.py
```

## ⚙️ 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | 数据库连接串 | `mysql+pymysql://user:pass@host:3306/dbname` |
| `JWT_SECRET` | JWT 签名密钥 | `your-random-secret-key` |

## 📁 项目结构

```
kids-tasks/
├── app.py              # Flask 应用主文件
├── auth.py             # 认证和授权模块
├── models.py           # 数据库模型
├── init_db.py          # 数据库初始化脚本
├── templates/
│   └── index.html      # 前端单页应用
├── static/
│   ├── app.js          # 前端 JavaScript
│   └── uploads/        # 用户上传的图片（已 gitignore）
├── wheelhouse/         # Python 依赖包（离线安装）
├── Dockerfile          # Docker 镜像构建文件
├── docker-compose.yml  # Docker Compose 配置
├── backup.sh           # 备份脚本
└── .env.example        # 环境变量模板
```

## 🔐 安全说明

- 密码使用 bcrypt 加密存储
- JWT Token 用于身份认证
- 敏感配置通过环境变量注入，不硬编码
- 上传图片限制 8MB，自动压缩
- 家长和孩子角色权限分离

## 📱 使用流程

### 首次使用
1. 家长注册账号，系统自动创建家庭并生成邀请码
2. 将邀请码告诉孩子
3. 孩子使用邀请码注册，自动加入家庭
4. 家长创建任务和商品
5. 孩子打卡完成任务
6. 家长审核确认，积分自动累加
7. 孩子用积分兑换商品

### 日常使用
- 每天查看任务列表，完成打卡
- 积分攒够后兑换心仪奖励
- 家长定期审核打卡、补充商品

## 📊 数据库设计

### 主要数据表
- `families` — 家庭信息
- `users` — 用户信息（家长/孩子）
- `tasks` — 任务定义
- `checkins` — 打卡记录
- `products` — 商品信息
- `orders` — 兑换订单
- `transactions` — 积分流水

## 🔧 自定义配置

### 修改端口
编辑 `docker-compose.yml`，修改端口映射：
```yaml
ports:
  - "8088:8088"
```

### 配置 HTTPS
建议使用 Nginx 反向代理，配置 SSL 证书。

### 数据备份
```bash
# 手动备份
./backup.sh

# 定时备份（每天 8:00）
0 8 * * * /path/to/kids-tasks/backup.sh
```

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 联系方式

如有问题，请在 GitHub Issues 中反馈。
