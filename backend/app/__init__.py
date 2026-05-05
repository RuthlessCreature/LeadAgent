"""
Flask 应用工厂
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from flask import Flask, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    # 创建 Flask
    app = Flask(__name__, 
                template_folder='../../frontend',
                static_folder='../../frontend',
                static_url_path='')
    
    # 确保数据目录存在
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # 配置
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'leadagent-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(data_dir, "leads.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 启用 CORS
    CORS(app)
    
    # 首页路由
    @app.route('/')
    def index():
        return render_template('index.html')
    
    # 初始化数据库
    db.init_app(app)
    
    # 注册蓝图
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # 创建数据库
    with app.app_context():
        db.create_all()
    
    return app
