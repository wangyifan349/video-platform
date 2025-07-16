import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, abort, g, flash, send_file, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload size

DATABASE = 'users.db'

# 允许上传的扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'txt'}

# 初始化数据库连接（单例模式 for request）
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

# 关闭数据库连接回调
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 检查文件扩展名是否允许
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 创建上传的文件夹层级，按用户名和文件类型分类
def create_user_file_dirs(username):
    base = os.path.join(app.config['UPLOAD_FOLDER'], username)
    for folder in ['image', 'video', 'text']:
        dir_path = os.path.join(base, folder)
        os.makedirs(dir_path, exist_ok=True)

# 读取文本文件内容辅助函数（用于搜索页面显示文本文件内容）
def get_text_content(username, filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], username, 'text', filename)
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
            return text
    except Exception:
        return '[无内容或文件读取失败]'

# 应用主页，简单重定向到搜索页面
@app.route('/')
def index():
    return redirect(url_for('search'))

# 用户注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        if not username or not password:
            flash('用户名和密码不能为空')
            return redirect(url_for('register'))

        conn = get_db()
        c = conn.cursor()
        # 检查用户名是否存在
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        if c.fetchone():
            flash('用户名已存在')
            return redirect(url_for('register'))
        
        # 插入用户
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        conn.close()

        # 创建文件目录
        create_user_file_dirs(username)
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    
    # 注册页面HTML模板
    return render_template_string('''
    {% extends "base.html" %}
    {% block body %}
    <h2>注册</h2>
    <form method="post">
      用户名: <input type="text" name="username"><br>
      密码: <input type="password" name="password"><br>
      <input type="submit" value="注册">
    </form>
    <p>已有账号？<a href="{{ url_for('login') }}">登录</a></p>
    {% endblock %}
    ''')

# 用户登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username=?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('登录成功')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误')
            return redirect(url_for('login'))
    
    # 登录页面HTML模板
    return render_template_string('''
    {% extends "base.html" %}
    {% block body %}
    <h2>登录</h2>
    <form method="post">
      用户名: <input type="text" name="username"><br>
      密码: <input type="password" name="password"><br>
      <input type="submit" value="登录">
    </form>
    <p>没有账号？<a href="{{ url_for('register') }}">注册</a></p>
    {% endblock %}
    ''')

# 用户登出
@app.route('/logout')
def logout():
    session.clear()
    flash('已登出')
    return redirect(url_for('login'))

# 用户文件列表页面，可以在线浏览图像、视频、文本
@app.route('/user/<username>')
def user_files(username):
    conn = get_db()
    c = conn.cursor()
    # 查询用户是否存在
    c.execute('SELECT id FROM users WHERE username=?', (username,))
    user = c.fetchone()
    if not user:
        abort(404)
    user_id = user['id']

    # 查询用户文件
    c.execute('SELECT id, filename, filetype FROM files WHERE user_id=?', (user_id,))
    files = c.fetchall()
    conn.close()

    # 根据文件类型列表分类
    images = [f for f in files if f['filetype'] == 'image']
    videos = [f for f in files if f['filetype'] == 'video']
    texts = [f for f in files if f['filetype'] == 'text']

    # 页面模板，支持在线浏览文件
    return render_template_string('''
    {% extends "base.html" %}
    {% block head %}
    <style>
    .file-item {
        margin-bottom: 10px;
        border: 1px solid #ddd;
        padding: 5px;
        max-width: 400px;
    }
    pre {
        white-space: pre-wrap;
        max-height: 200px;
        overflow: auto;
        border:1px solid #ccc;
        padding: 5px;
        background-color: #f9f9f9;
    }
    </style>
    {% endblock %}
    {% block body %}
    <h2>{{ username }}的文件列表</h2>

    <h3>图片</h3>
    {% if images %}
      {% for f in images %}
        <div class="file-item">
          <p>{{ f['filename'] }}</p>
          <img src="{{ url_for('user_file', username=username, filetype='image', filename=f['filename']) }}" style="max-width: 300px;" alt="{{ f['filename'] }}"/>
        </div>
      {% endfor %}
    {% else %}
      <p>无</p>
    {% endif %}

    <h3>视频</h3>
    {% if videos %}
      {% for f in videos %}
        <div class="file-item">
          <p>{{ f['filename'] }}</p>
          <video width="320" controls>
            <source src="{{ url_for('user_file', username=username, filetype='video', filename=f['filename']) }}" type="video/mp4">
            您的浏览器不支持视频播放
          </video>
        </div>
      {% endfor %}
    {% else %}
      <p>无</p>
    {% endif %}

    <h3>文本</h3>
    {% if texts %}
      {% for f in texts %}
        <div class="file-item">
          <p>{{ f['filename'] }}</p>
          <pre>{{ get_text_content(username, f['filename']) }}</pre>
        </div>
      {% endfor %}
    {% else %}
      <p>无</p>
    {% endif %}
    {% endblock %}
    ''', username=username, images=images, videos=videos, texts=texts, get_text_content=get_text_content)

# 静态文件的在线访问，比如图片、视频、文本内容读取
@app.route('/user/<username>/<filetype>/<filename>')
def user_file(username, filetype, filename):
    # 检查文件类型
    if filetype not in ['image', 'video', 'text']:
        abort(404)
    # 组合文件路径
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], username, filetype, filename)
    if not os.path.exists(file_path):
        abort(404)
    # 对文本直接读取后渲染，图片视频直接发送文件
    if filetype == 'text':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # 使用render_template_string返回简单页面展示文本
            return render_template_string('''
                {% extends "base.html" %}
                {% block body %}
                <h2>{{ filename }}</h2>
                <pre style="white-space: pre-wrap; border:1px solid #ccc; padding:10px; max-width:800px;">{{ content }}</pre>
                <p><a href="{{ url_for('user_files', username=username) }}">返回文件列表</a></p>
                {% endblock %}
            ''', content=content, filename=filename, username=username)
        except Exception:
            abort(500)
    else:
        return send_file(file_path)

# 文件上传，只允许登录用户上传自己的文件
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        flash('请先登录')
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('未选择文件')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('未选择文件')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.',1)[1].lower()

            # 判断文件类型对应文件夹
            if ext in ['png', 'jpg', 'jpeg', 'gif']:
                filetype = 'image'
            elif ext in ['mp4', 'avi']:
                filetype = 'video'
            elif ext == 'txt':
                filetype = 'text'
            else:
                flash('不支持的文件类型')
                return redirect(request.url)

            # 确保用户目录存在
            create_user_file_dirs(session['username'])
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], session['username'], filetype, filename)
            file.save(save_path)

            # 记录入数据库
            conn = get_db()
            c = conn.cursor()
            # 确认用户ID
            c.execute('SELECT id FROM users WHERE username=?', (session['username'],))
            user = c.fetchone()
            if not user:
                flash('用户不存在')
                return redirect(url_for('logout'))
            user_id = user['id']
            # 插入文件记录
            c.execute('INSERT INTO files (user_id, filename, filetype) VALUES (?,?,?)', (user_id, filename, filetype))
            conn.commit()
            conn.close()

            flash('上传成功')
            return redirect(url_for('user_files', username=session['username']))
        else:
            flash('不允许该类型文件或文件名异常')
            return redirect(request.url)

    # 上传页面HTML模板
    return render_template_string('''
    {% extends "base.html" %}
    {% block body %}
    <h2>上传文件（仅限登录用户）</h2>
    <form method="post" enctype="multipart/form-data">
      选择文件: <input type="file" name="file"><br>
      <input type="submit" value="上传">
    </form>
    <p><a href="{{ url_for('user_files', username=session.get('username')) }}">返回首页</a></p>
    {% endblock %}
    ''')

# 搜索用户，匹配用户名并显示文件预览（图片、视频、文本）
@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    conn = get_db()
    c = conn.cursor()
    users = []
    if q != '':
        param = '%' + q + '%'
        c.execute('SELECT id, username FROM users WHERE username LIKE ?', (param,))
        rows = c.fetchall()
        for row in rows:
            user_id = row['id']
            username = row['username']
            # 查询该用户所有文件
            c.execute('SELECT id, filename, filetype FROM files WHERE user_id=?', (user_id,))
            files = c.fetchall()
            images = []
            videos = []
            texts = []
            for f in files:
                if f['filetype'] == 'image':
                    images.append(f)
                elif f['filetype'] == 'video':
                    videos.append(f)
                elif f['filetype'] == 'text':
                    texts.append(f)
            users.append({
                'id': user_id,
                'username': username,
                'images': images,
                'videos': videos,
                'texts': texts
            })
    conn.close()

    # 搜索结果模板，支持在线查看对应文件
    return render_template_string('''
    {% extends "base.html" %}
    {% block head %}
    <style>
    .file-item {
        margin-bottom: 10px;
        border: 1px solid #ddd;
        padding: 5px;
        position: relative;
        max-width: 400px;
    }
    pre {
        white-space: pre-wrap;
        max-height: 200px;
        overflow: auto;
        border:1px solid #ccc;
        padding:5px;
        background:#f9f9f9;
    }
    </style>
    {% endblock %}
    {% block body %}
    <h2>搜索用户： {{ query }}</h2>
    {% if users %}
      {% for user in users %}
        <h3><a href="{{ url_for('user_files', username=user.username) }}">{{ user.username }}</a></h3>
        <div>
          <strong>图片:</strong>
          {% if user.images %}
            {% for f in user.images %}
              <div class="file-item">
                <p>{{ f['filename'] }}</p>
                <img src="{{ url_for('user_file', username=user.username, filetype='image', filename=f['filename']) }}" style="max-width: 300px;" alt="{{ f['filename'] }}"/>
              </div>
            {% endfor %}
          {% else %}
          <p>无</p>
          {% endif %}
        </div>
        <div>
          <strong>视频:</strong>
          {% if user.videos %}
            {% for f in user.videos %}
              <div class="file-item">
                <p>{{ f['filename'] }}</p>
                <video width="320" controls>
                  <source src="{{ url_for('user_file', username=user.username, filetype='video', filename=f['filename']) }}" type="video/mp4">
                  您的浏览器不支持视频播放
                </video>
              </div>
            {% endfor %}
          {% else %}
          <p>无</p>
          {% endif %}
        </div>
        <div>
          <strong>文本:</strong>
          {% if user.texts %}
            {% for f in user.texts %}
              <div class="file-item">
                <p>{{ f['filename'] }}</p>
                <pre>{{ get_text_content(user.username, f['filename']) }}</pre>
              </div>
            {% endfor %}
          {% else %}
          <p>无</p>
          {% endif %}
        </div>
        <hr>
      {% endfor %}
    {% else %}
      <p>无匹配用户</p>
    {% endif %}
    {% endblock %}
    ''', users=users, query=q, get_text_content=get_text_content)

# 基础HTML模板，所有页面继承这个
app.jinja_env.globals['base_template'] = '''
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>用户文件管理系统</title>
  {% block head %}{% endblock %}
</head>
<body>
  <nav style="margin-bottom:15px;">
    {% if session.get('username') %}
        <span>欢迎, {{ session.get('username') }} | </span>
        <a href="{{ url_for('index') }}">首页</a> |
        <a href="{{ url_for('upload') }}">上传</a> |
        <a href="{{ url_for('logout') }}">登出</a>
    {% else %}
        <a href="{{ url_for('login') }}">登录</a> |
        <a href="{{ url_for('register') }}">注册</a>
    {% endif %}
  </nav>

  {% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul style="color:red;">
      {% for message in messages %}
      <li>{{ message }}</li>
      {% endfor %}
    </ul>
  {% endif %}
  {% endwith %}

  {% block body %}{% endblock %}
</body>
</html>
'''

# 定制模板继承机制，所有页面都继承base.html
@app.context_processor
def base_template_processor():
    def base():
        return app.jinja_env.globals['base_template']
    return dict(base=base)

# 重写render_template_string函数，使其支持 {% extends "base.html" %}
original_render_template_string = render_template_string
def my_render_template_string(source, **context):
    if '{% extends "base.html" %}' in source:
        # 插入base模板作为底层模板
        base = app.jinja_env.from_string(app.jinja_env.globals['base_template'])
        tmpl = app.jinja_env.from_string(source)
        return tmpl.render(**context)
    else:
        return original_render_template_string(source, **context)
app.jinja_env.globals['render_template_string'] = my_render_template_string

# 创建数据库以及表结构，首次运行时调用此函数初始化
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # 创建用户表
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    # 创建文件表
    c.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    # 确保数据库和上传目录存在
    init_db()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # 运行Flask应用
    app.run(debug=True, host='0.0.0.0', port=5000)
