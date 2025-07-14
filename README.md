# 🎥 Video Platform

欢迎使用 **Video Platform** —— 一个基于 Flask 框架构建的免费视频分享与管理平台。此项目旨在让用户能够轻松注册账号、上传和管理个人视频内容，浏览其他用户的视频作品，并支持通过用户名的模糊搜索快速查找用户主页和视频。

## 🚀 功能概述

- **用户系统**：支持用户注册、登录和注销，保证个人账户安全与隐私。🔒
- **视频上传和管理**：用户可以上传视频文件（支持多种格式），为视频添加标题，可管理和删除个人视频。📤🗂
- **视频播放**：内置视频播放器支持在线播放视频，支持多种设备访问。🎬
- **用户主页**：每个用户拥有公开主页，展示其所有上传的视频，方便分享和浏览。👤
- **搜索功能**：通过用户名的最长公共子序列（LCS）算法实现模糊搜索，方便查找和连接感兴趣的用户。🔍
- **响应式界面**：基于 Bootstrap 框架，优化桌面和移动端访问体验。💻📱

## 📁 项目结构

```
.
├── app.py                       # Flask应用主程序
├── templates/                   # 前端HTML模板文件
│   ├── base.html                # 基础模板，包含导航和公共布局
│   ├── index.html               # 主页
│   ├── register.html            # 用户注册页
│   ├── login.html               # 用户登录页
│   ├── dashboard.html           # 用户管理面板（上传/管理视频）
│   ├── user_videos.html         # 用户公开主页，展示视频列表
│   ├── play_video.html          # 视频播放页面
│   └── search_results.html      # 用户搜索结果页
├── static/
│   └── videos/                  # 视频文件存储目录
├── requirements.txt             # Python依赖列表
└── README.md                    # 项目说明文档（您正在阅读）
```

## 🛠 安装与使用指南

1. 从 GitHub 克隆项目代码：

   ```bash
   git clone https://github.com/wangyifan349/video-platform.git
   cd video-platform
   ```

2. 创建并激活 Python 虚拟环境（推荐）：

   ```bash
   python3 -m venv venv
   source venv/bin/activate       # macOS/Linux
   venv\Scripts\activate          # Windows
   ```

3. 安装依赖：

   ```bash
   pip install -r requirements.txt
   ```

4. 启动 Flask 服务：

   ```bash
   flask run
   ```

5. 打开浏览器，访问 [http://127.0.0.1:5000](http://127.0.0.1:5000) 开始使用。

## 📄 许可证

本项目遵循 GNU 通用公共许可证 (GNU GPL) 第3版，详见 [LICENSE](LICENSE) 文件。

简要说明：

- 您可以自由使用、修改和分发本项目的代码，但必须保持相同许可证。
- 转载请注明出处并提供本许可证副本。
- 本项目不提供任何形式的保证或担保。

完整许可内容请参考官方文档 <https://www.gnu.org/licenses/gpl-3.0.html>。

## 🙏 致谢

感谢所有支持和参与的开发者与开源社区，您们的贡献让项目不断完善。

---

© 2025 wangyifan349 版权所有
