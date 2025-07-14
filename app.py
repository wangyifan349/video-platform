import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 请换成随机且安全的key
UPLOAD_FOLDER = 'static/videos'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- 数据库相关 ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # 用户表：id, username, password
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    ''')
    # 视频表：id, user_id, filename, title
    c.execute('''
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        title TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 辅助函数 ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 最强公共子序列计算（Longest Common Subsequence, LCS）
def lcs_length(a, b):
    dp = [[0]*(len(b)+1) for _ in range(len(a)+1)]
    for i in range(1, len(a)+1):
        for j in range(1, len(b)+1):
            if a[i-1] == b[j-1]:
                dp[i][j] = dp[i-1][j-1] +1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[len(a)][len(b)]

# --- 路由 ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# 注册
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if not username or not password:
            flash('用户名和密码不能为空')
            return redirect(url_for('register'))
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
        except sqlite3.IntegrityError:
            flash('用户名已存在')
            conn.close()
            return redirect(url_for('register'))
        conn.close()
        flash('注册成功，请登录')
        return redirect(url_for('login'))
    return render_template('register.html')

# 登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('用户名或密码错误')
            return redirect(url_for('login'))
    return render_template('login.html')

# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录')
    return redirect(url_for('index'))

# 仪表板（管理面板）：查看和管理用户自己的视频
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
    uid = session['user_id']
    conn = get_db_connection()
    videos = conn.execute('SELECT * FROM videos WHERE user_id = ?', (uid,)).fetchall()
    conn.close()
    return render_template('dashboard.html', videos=videos)

# 上传视频
@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
    if 'file' not in request.files:
        flash('未选择文件')
        return redirect(url_for('dashboard'))
    file = request.files['file']
    title = request.form.get('title', '').strip()
    if file.filename == '':
        flash('未选择文件')
        return redirect(url_for('dashboard'))
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # 为避免文件名冲突，加上用户id和随机数
        filename = f"{session['user_id']}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        conn = get_db_connection()
        conn.execute('INSERT INTO videos (user_id, filename, title) VALUES (?, ?, ?)',
                     (session['user_id'], filename, title))
        conn.commit()
        conn.close()
        flash('上传成功')
    else:
        flash('文件格式不支持')
    return redirect(url_for('dashboard'))

# 删除视频
@app.route('/delete/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    if 'user_id' not in session:
        flash('请先登录')
        return redirect(url_for('login'))
    uid = session['user_id']
    conn = get_db_connection()
    video = conn.execute('SELECT * FROM videos WHERE id = ? AND user_id = ?', (video_id, uid)).fetchone()
    if video:
        # 删除文件
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], video['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        conn.execute('DELETE FROM videos WHERE id = ?', (video_id,))
        conn.commit()
        flash('删除成功')
    else:
        flash('视频不存在或没有权限删除')
    conn.close()
    return redirect(url_for('dashboard'))

# 用户主页 - 显示某个用户的视频列表，可以刷视频
@app.route('/user/<username>')
def user_videos(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if not user:
        conn.close()
        flash('用户不存在')
        return redirect(url_for('index'))
    videos = conn.execute('SELECT * FROM videos WHERE user_id = ?', (user['id'],)).fetchall()
    conn.close()
    return render_template('user_videos.html', user=user, videos=videos)

# 播放单个视频页面
@app.route('/video/<int:video_id>')
def play_video(video_id):
    conn = get_db_connection()
    video = conn.execute('SELECT videos.*, users.username FROM videos JOIN users ON videos.user_id = users.id WHERE videos.id = ?', (video_id,)).fetchone()
    conn.close()
    if not video:
        flash('视频不存在')
        return redirect(url_for('index'))
    return render_template('play_video.html', video=video)

# 视频搜索（根据用户名最强公共子序列匹配）
@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('q', '').strip()
    if not keyword:
        flash('请输入搜索关键字')
        return redirect(url_for('index'))
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    # 计算每个用户名和关键词的LCS长度
    user_scores = []
    for u in users:
        score = lcs_length(keyword, u['username'])
        user_scores.append((u, score))
    # 按得分降序排序，取前几个相似用户展示
    user_scores.sort(key=lambda x: x[1], reverse=True)
    top_users = [u for u, s in user_scores if s > 0][:10]
    conn.close()
    return render_template('search_results.html', keyword=keyword, users=top_users)

# 静态文件中视频访问，Flask默认static路径已配置，直接访问/static/videos/filename即可

if __name__ == '__main__':
    app.run(debug=True)
