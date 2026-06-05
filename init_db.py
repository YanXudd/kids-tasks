"""数据库初始化。

启动时被 app.py 调用，只建表，不填充演示数据。
"""
from models import db


def init_database(app):
    with app.app_context():
        db.create_all()
        print('[init_db] 数据库表已就绪')


if __name__ == '__main__':
    from app import app
    init_database(app)
