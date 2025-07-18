"""
flask db init
flask db migrate -m "init"
flask db upgrade
"""


import os
from flask import (
    Flask, render_template_string, redirect,
    url_for, flash, request, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# -----------------------
# CONFIGURATION
# -----------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")

app = Flask(__name__)
app.config.update(
    SECRET_KEY="devsecret",
    SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(BASE_DIR, "app.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=UPLOAD_ROOT,
    MAX_CONTENT_LENGTH=200 * 1024 * 1024,  # 200MB
    ALLOWED_EXTENSIONS={"mp4", "mov", "avi", "mkv"}
)

# 确保上传目录存在
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# -----------------------
# DATABASE
# -----------------------
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# 用户模型，只存用户名和密码哈希
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)

# -----------------------
# LOGIN MANAGER
# -----------------------
login = LoginManager(app)
login.login_view = "login"

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -----------------------
# HELPERS
# -----------------------
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )

def user_folder(username):
    """返回某个用户的上传目录，不存在则创建"""
    folder = os.path.join(app.config["UPLOAD_FOLDER"], username)
    os.makedirs(folder, exist_ok=True)
    return folder

# -----------------------
# TEMPLATES
# -----------------------

base_html = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{% block title %}短视频平台{% endblock %}</title>
  <link
    href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
    rel="stylesheet"
  >
  <style>
    body {{ padding-top: 70px; }}
  </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
  <div class="container-fluid">
    <a class="navbar-brand" href="{{ url_for('index') }}">ShortVideo</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav"
      aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="navbarNav">
      <ul class="navbar-nav ms-auto">
        {% if current_user.is_authenticated %}
          <li class="nav-item">
            <a class="nav-link">你好, {{ current_user.username }}</a>
          </li>
          <li class="nav-item">
            <a class="nav-link" href="{{ url_for('logout') }}">登出</a>
          </li>
        {% else %}
          <li class="nav-item">
            <a class="nav-link" href="{{ url_for('login') }}">登录</a>
          </li>
          <li class="nav-item">
            <a class="nav-link" href="{{ url_for('register') }}">注册</a>
          </li>
        {% endif %}
      </ul>
    </div>
  </div>
</nav>

<div class="container">
  {% with msgs = get_flashed_messages(with_categories=true) %}
    {% if msgs %}
      {% for category, msg in msgs %}
        <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
          {{ msg }}
          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  {% block content %}{% endblock %}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

index_html = '''
{% extends "base.html" %}
{% block title %}首页 - 短视频平台{% endblock %}
{% block content %}

<div class="row mb-4">
  <div class="col-md-6">
    <form class="d-flex" action="{{ url_for('search') }}" method="post">
      <input
        class="form-control me-2"
        type="search"
        placeholder="搜索用户名"
        name="username"
        value="{{ keyword or '' }}"
      >
      <button class="btn btn-outline-success" type="submit">搜索</button>
    </form>
  </div>
</div>

{% if search_results is defined %}
  <div class="mb-4">
    <h5>搜索结果：</h5>
    <ul class="list-group">
      {% for u in search_results %}
        <li class="list-group-item">
          <a href="{{ url_for('user_videos', username=u.username) }}">
            {{ u.username }}
          </a>
        </li>
      {% endfor %}
    </ul>
  </div>
{% endif %}

{% if current_user.is_authenticated %}
  <div class="card mb-4">
    <div class="card-body">
      <h5 class="card-title">上传新视频</h5>
      <form action="{{ url_for('index') }}" method="post" enctype="multipart/form-data">
        <div class="mb-3">
          <input class="form-control" type="file" name="video_file" accept="video/*" required>
        </div>
        <button class="btn btn-primary">上传</button>
      </form>
    </div>
  </div>

  <h5>我的视频列表</h5>
  <div class="row">
    {% for vid in videos %}
      <div class="col-md-3 mb-3">
        <div class="card">
          <video class="card-img-top" controls style="max-height:200px;">
            <source src="{{ url_for('uploaded_file', username=current_user.username, filename=vid) }}">
          </video>
          <div class="card-body p-2 text-center">
            <form action="{{ url_for('delete_video', filename=vid) }}" method="post"
                  onsubmit="return confirm('确定删除该视频？');">
              <button class="btn btn-sm btn-danger">删除</button>
            </form>
          </div>
        </div>
      </div>
    {% endfor %}
  </div>
{% else %}
  <p>请先 <a href="{{ url_for('login') }}">登录</a> 以上传和查看视频。</p>
{% endif %}

{% endblock %}
'''

user_videos_html = '''
{% extends "base.html" %}
{% block title %}{{ user.username }} 的视频{% endblock %}
{% block content %}
<h4>{{ user.username }} 的视频</h4>
<div class="row">
  {% for vid in videos %}
    <div class="col-md-3 mb-3">
      <div class="card">
        <video class="card-img-top" controls style="max-height:200px;">
          <source src="{{ url_for('uploaded_file', username=user.username, filename=vid) }}">
        </video>
      </div>
    </div>
  {% endfor %}
  {% if videos|length == 0 %}
    <p>该用户还没有上传视频。</p>
  {% endif %}
</div>
{% endblock %}
'''

login_html = '''
{% extends "base.html" %}
{% block title %}登录{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-4">
    <h4 class="mb-3">用户登录</h4>
    <form method="post">
      <div class="mb-3">
        <input class="form-control" name="username" placeholder="用户名" required autofocus>
      </div>
      <div class="mb-3">
        <input class="form-control" name="password" type="password" placeholder="密码" required>
      </div>
      <button class="btn btn-primary w-100">登录</button>
    </form>
  </div>
</div>
{% endblock %}
'''

register_html = '''
{% extends "base.html" %}
{% block title %}注册{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-4">
    <h4 class="mb-3">用户注册</h4>
    <form method="post">
      <div class="mb-3">
        <input class="form-control" name="username" placeholder="用户名" required autofocus>
      </div>
      <div class="mb-3">
        <input class="form-control" name="password" type="password" placeholder="密码" required>
      </div>
      <button class="btn btn-success w-100">注册</button>
    </form>
  </div>
</div>
{% endblock %}
'''

# -----------------------
# ROUTES
# -----------------------

@app.route("/", methods=["GET", "POST"])
def index():
    """
    主页：已登录用户可上传视频，浏览自己视频列表；
    所有人都可搜索用户名。
    """
    # 上传处理
    if request.method == "POST" and current_user.is_authenticated:
        file = request.files.get("video_file")
        if not file or file.filename == "":
            flash("请选择一个视频文件", "warning")
        elif not allowed_file(file.filename):
            flash("不支持的文件格式", "danger")
        else:
            fname = secure_filename(file.filename)
            dst = os.path.join(user_folder(current_user.username), fname)
            # 避免覆盖
            base, ext = os.path.splitext(fname)
            counter = 1
            while os.path.exists(dst):
                fname = f"{base}_{counter}{ext}"
                dst = os.path.join(user_folder(current_user.username), fname)
                counter += 1
            file.save(dst)
            flash("上传成功！", "success")
        return redirect(url_for("index"))

    # 列出当前用户的视频文件
    videos = []
    if current_user.is_authenticated:
        folder = user_folder(current_user.username)
        videos = sorted(os.listdir(folder))
    return render_template_string(index_html,
                                  videos=videos,
                                  search_results=None,
                                  keyword=None,
                                  current_user=current_user,
                                  )

@app.route("/delete/<filename>", methods=["POST"])
@login_required
def delete_video(filename):
    """删除当前用户上传的视频"""
    safe_name = secure_filename(filename)
    path = os.path.join(user_folder(current_user.username), safe_name)
    if os.path.exists(path):
        os.remove(path)
        flash("删除成功", "success")
    else:
        flash("文件不存在", "danger")
    return redirect(url_for("index"))

@app.route("/uploads/<username>/<filename>")
def uploaded_file(username, filename):
    """提供视频静态资源访问"""
    safe_username = secure_filename(username)
    safe_filename = secure_filename(filename)
    path = os.path.join(user_folder(safe_username), safe_filename)
    if not os.path.exists(path):
        abort(404)
    return send_from_directory(user_folder(safe_username), safe_filename)

@app.route("/search", methods=["POST"])
def search():
    """根据用户名模糊搜索"""
    keyword = request.form.get("username", "").strip()
    results = []
    if keyword:
        results = User.query.filter(User.username.ilike(f"%{keyword}%")).all()
        if not results:
            flash("未找到匹配用户", "info")
    return render_template_string(index_html,
                                  search_results=results,
                                  keyword=keyword,
                                  videos=[],
                                  current_user=current_user)

@app.route("/user/<username>")
def user_videos(username):
    """浏览某个用户的所有视频"""
    user = User.query.filter_by(username=username).first_or_404()
    vids = sorted(os.listdir(user_folder(user.username)))
    return render_template_string(user_videos_html, user=user, videos=vids, current_user=current_user)

@app.route("/register", methods=["GET", "POST"])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        uname = request.form["username"].strip()
        pwd = request.form["password"]
        if not uname or not pwd:
            flash("用户名和密码不能为空", "warning")
        elif User.query.filter_by(username=uname).first():
            flash("用户名已存在", "danger")
        else:
            u = User(username=uname)
            u.set_password(pwd)
            db.session.add(u)
            db.session.commit()
            flash("注册成功，请登录！", "success")
            return redirect(url_for("login"))
    return render_template_string(register_html, current_user=current_user)

@app.route("/login", methods=["GET", "POST"])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        uname = request.form["username"].strip()
        pwd = request.form["password"]
        user = User.query.filter_by(username=uname).first()
        if not user or not user.check_password(pwd):
            flash("无效的用户名或密码", "danger")
        else:
            login_user(user)
            return redirect(url_for("index"))
    return render_template_string(login_html, current_user=current_user)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# 注册 base 模板
@app.context_processor
def inject_base():
    return dict(
        base=base_html
    )

from jinja2 import Template

# Trick: render_template_string with extends requires base.html registered.
# Patch Flask's template loader temporarily:
from flask import template_rendered

from jinja2 import DictLoader

app.jinja_loader = DictLoader({
    'base.html': base_html,
})

if __name__ == "__main__":
    # 提示：首次运行需初始化数据库：
    # flask db init
    # flask db migrate -m "init"
    # flask db upgrade
    app.run(debug=True)
