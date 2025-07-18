package main

import (
	"fmt"
	"html/template"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/gin-contrib/sessions"
	"github.com/gin-contrib/sessions/cookie"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

type User struct {
	gorm.Model
	Username     string `gorm:"uniqueIndex"`
	PasswordHash string
}

var (
	database           *gorm.DB
	allowedExtensions  = map[string]bool{".mp4": true, ".mov": true, ".avi": true, ".mkv": true}
	templates          *template.Template
)

func initTemplates() {
	// 合并所有模板为一个template.Template
	// 下面以 define 分别定义模板名字，方便调用
	templates = template.Must(template.New("all").Funcs(template.FuncMap{}).Parse(`
{{define "index"}}
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8" />
    <title>视频首页</title>
</head>
<body>
<h1>欢迎 {{if .User}}{{.User}}{{else}}游客{{end}}</h1>

{{ if .Flash }}
<p style="color:green;">{{ .Flash }}</p>
{{ end }}

{{ if .User }}
<form action="/upload" method="post" enctype="multipart/form-data">
    <label>上传视频（限 mp4 mov avi mkv）: <input type="file" name="video_file" required></label>
    <button type="submit">上传</button>
</form>
<p>你的视频列表：</p>
<ul>
    {{range .Videos}}
    <li>
        <a href="/uploads/{{$.User}}/{{.}}" target="_blank">{{.}}</a>
        <form style="display:inline" method="post" action="/delete/{{.}}">
            <button type="submit">删除</button>
        </form>
    </li>
    {{else}}
    <li>你还没有上传视频</li>
    {{end}}
</ul>

<form action="/search" method="post" style="margin-top:20px;">
    <label>搜索用户: <input type="text" name="username" value="{{.SearchKeyword}}" required></label>
    <button type="submit">搜索</button>
</form>

<a href="/logout">登出</a>

{{ else }}
<p><a href="/login">登录</a> | <a href="/register">注册</a></p>
{{end}}

{{if .SearchUsers}}
<h2>搜索结果：</h2>
<ul>
    {{range .SearchUsers}}
        <li><a href="/user/{{.Username}}">{{.Username}}</a></li>
    {{else}}
        <li>暂无匹配用户</li>
    {{end}}
</ul>
{{end}}

</body>
</html>
{{end}}

{{define "login"}}
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8" />
    <title>登录</title>
</head>
<body>
<h1>用户登录</h1>

{{ if .Flash }}
<p style="color:green;">{{ .Flash }}</p>
{{ end }}

{{ if .Error }}
<p style="color:red;">{{ .Error }}</p>
{{ end }}

<form action="/login" method="post">
    <label>用户名: <input type="text" name="username" required></label><br/>
    <label>密码: <input type="password" name="password" required></label><br/>
    <button type="submit">登录</button>
</form>

<p><a href="/register">注册新用户</a></p>
<p><a href="/">返回首页</a></p>

</body>
</html>
{{end}}

{{define "register"}}
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8" />
    <title>注册</title>
</head>
<body>
<h1>用户注册</h1>

{{ if .Error }}
<p style="color:red;">{{ .Error }}</p>
{{ end }}

<form action="/register" method="post">
    <label>用户名: <input type="text" name="username" required></label><br/>
    <label>密码: <input type="password" name="password" required></label><br/>
    <button type="submit">注册</button>
</form>

<p><a href="/login">已有账号，去登录</a></p>
<p><a href="/">返回首页</a></p>

</body>
</html>
{{end}}

{{define "user_videos"}}
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8" />
    <title>{{.ViewedUser}} 的主页</title>
</head>
<body>
<h1>用户 {{.ViewedUser}} 的视频</h1>

{{ if .Videos }}
<ul>
    {{range .Videos}}
    <li><a href="/uploads/{{$.ViewedUser}}/{{.}}" target="_blank">{{.}}</a></li>
    {{end}}
</ul>
{{ else }}
<p>此用户未上传视频</p>
{{ end }}

<p><a href="/">返回首页</a> | {{if .User}}<a href="/user/{{.User}}">我的主页</a> | <a href="/logout">登出</a>{{else}}<a href="/login">登录</a>{{end}}</p>

</body>
</html>
{{end}}
`))
}

func isAllowedFile(filename string) bool {
	ext := strings.ToLower(filepath.Ext(filename))
	return allowedExtensions[ext]
}

func directoryForUser(username string) string {
	dir := filepath.Join("uploads", username)
	_ = os.MkdirAll(dir, os.ModePerm)
	return dir
}

func getUsernameFromSession(c *gin.Context) (string, bool) {
	session := sessions.Default(c)
	u := session.Get("user")
	username, ok := u.(string)
	return username, ok
}

// 计算LCS长度
func longestCommonSubsequenceLength(a, b string) int {
	m, n := len(a), len(b)
	dp := make([][]int, m+1)
	for i := range dp {
		dp[i] = make([]int, n+1)
	}
	for i := 1; i <= m; i++ {
		for j := 1; j <= n; j++ {
			if a[i-1] == b[j-1] {
				dp[i][j] = dp[i-1][j-1] + 1
			} else if dp[i-1][j] > dp[i][j-1] {
				dp[i][j] = dp[i-1][j]
			} else {
				dp[i][j] = dp[i][j-1]
			}
		}
	}
	return dp[m][n]
}

func searchUsersByLCS(keyword string, users []User) []User {
	type scoredUser struct {
		User  User
		Score int
	}
	var scoredList []scoredUser
	lowerKeyword := strings.ToLower(keyword)
	for _, u := range users {
		lowerUsername := strings.ToLower(u.Username)
		score := longestCommonSubsequenceLength(lowerKeyword, lowerUsername)
		if score > 0 {
			scoredList = append(scoredList, scoredUser{User: u, Score: score})
		}
	}
	sort.Slice(scoredList, func(i, j int) bool {
		return scoredList[i].Score > scoredList[j].Score
	})
	result := make([]User, len(scoredList))
	for i, v := range scoredList {
		result[i] = v.User
	}
	return result
}

func main() {
	var err error
	database, err = gorm.Open(sqlite.Open("app.db"), &gorm.Config{})
	if err != nil {
		log.Fatal(err)
	}
	err = database.AutoMigrate(&User{})
	if err != nil {
		log.Fatal(err)
	}

	initTemplates()

	r := gin.Default()

	// 静态目录——提供视频访问
	r.Static("/uploads", "./uploads")

	// session中间件
	store := cookie.NewStore([]byte("secret"))
	r.Use(sessions.Sessions("mysession", store))

	// 首页
	r.GET("/", func(c *gin.Context) {
		username, loggedIn := getUsernameFromSession(c)
		var videoFiles []string
		if loggedIn {
			dir := directoryForUser(username)
			files, err := os.ReadDir(dir)
			if err == nil {
				for _, fileInfo := range files {
					if !fileInfo.IsDir() {
						videoFiles = append(videoFiles, fileInfo.Name())
					}
				}
			}
		}
		data := gin.H{
			"User":          username,
			"Videos":        videoFiles,
			"Flash":         c.Query("flash"),
			"SearchUsers":   nil,
			"SearchKeyword": "",
		}
		c.Status(200)
		if err := templates.ExecuteTemplate(c.Writer, "index", data); err != nil {
			log.Println("template index execute error:", err)
		}
	})

	// 上传视频
	r.POST("/upload", func(c *gin.Context) {
		username, loggedIn := getUsernameFromSession(c)
		if !loggedIn {
			c.Redirect(http.StatusFound, "/login?flash=必须先登录才能上传")
			return
		}

		file, err := c.FormFile("video_file")
		if err != nil {
			c.Redirect(http.StatusFound, "/?flash=请选择上传文件")
			return
		}
		if !isAllowedFile(file.Filename) {
			c.Redirect(http.StatusFound, "/?flash=不支持的文件格式")
			return
		}

		dstDir := directoryForUser(username)
		baseName := strings.TrimSuffix(filepath.Base(file.Filename), filepath.Ext(file.Filename))
		ext := filepath.Ext(file.Filename)
		dstPath := filepath.Join(dstDir, filepath.Base(file.Filename))
		index := 1
		for {
			if _, err := os.Stat(dstPath); os.IsNotExist(err) {
				break
			}
			dstPath = filepath.Join(dstDir, fmt.Sprintf("%s_%d%s", baseName, index, ext))
			index++
		}
		err = c.SaveUploadedFile(file, dstPath)
		if err != nil {
			c.Redirect(http.StatusFound, "/?flash=上传失败")
			return
		}

		c.Redirect(http.StatusFound, "/?flash=上传成功")
	})

	// 删除视频
	r.POST("/delete/:filename", func(c *gin.Context) {
		username, loggedIn := getUsernameFromSession(c)
		if !loggedIn {
			c.Redirect(http.StatusFound, "/login?flash=请先登录")
			return
		}
		filename := c.Param("filename")
		if strings.Contains(filename, "/") || strings.Contains(filename, "\\") {
			c.Redirect(http.StatusFound, "/?flash=非法文件名")
			return
		}
		f := filepath.Join(directoryForUser(username), filename)
		err := os.Remove(f)
		if err != nil {
			c.Redirect(http.StatusFound, "/?flash=删除失败或文件不存在")
			return
		}
		c.Redirect(http.StatusFound, "/?flash=删除成功")
	})

	// 用户搜索
	r.POST("/search", func(c *gin.Context) {
		keyword := c.PostForm("username")
		if keyword == "" {
			c.Redirect(http.StatusFound, "/?flash=搜索关键词不能为空")
			return
		}
		var allUsers []User
		database.Find(&allUsers)
		usersMatched := searchUsersByLCS(keyword, allUsers)
		if len(usersMatched) > 20 {
			usersMatched = usersMatched[:20]
		}
		username, _ := getUsernameFromSession(c)
		data := gin.H{
			"User":          username,
			"SearchUsers":   usersMatched,
			"SearchKeyword": keyword,
			"Videos":        nil,
			"Flash":         "",
		}
		c.Status(200)
		if err := templates.ExecuteTemplate(c.Writer, "index", data); err != nil {
			log.Println("template index execute error:", err)
		}
	})

	// 查看某用户主页和视频
	r.GET("/user/:username", func(c *gin.Context) {
		viewedUser := c.Param("username")
		dir := directoryForUser(viewedUser)
		files, err := os.ReadDir(dir)
		var userVideos []string
		if err == nil {
			for _, fileInfo := range files {
				if !fileInfo.IsDir() {
					userVideos = append(userVideos, fileInfo.Name())
				}
			}
		}
		currentUser, _ := getUsernameFromSession(c)
		data := gin.H{"User": currentUser, "ViewedUser": viewedUser, "Videos": userVideos, "Flash": ""}
		c.Status(200)
		if err := templates.ExecuteTemplate(c.Writer, "user_videos", data); err != nil {
			log.Println("template user_videos execute error:", err)
		}
	})

	// 注册页
	r.GET("/register", func(c *gin.Context) {
		c.Status(200)
		if err := templates.ExecuteTemplate(c.Writer, "register", gin.H{"Error": ""}); err != nil {
			log.Println("template register execute error:", err)
		}
	})

	// 注册处理
	r.POST("/register", func(c *gin.Context) {
		username := c.PostForm("username")
		password := c.PostForm("password")
		if username == "" || password == "" {
			c.Status(200)
			if err := templates.ExecuteTemplate(c.Writer, "register", gin.H{"Error": "用户名密码不能为空"}); err != nil {
				log.Println("template register execute error:", err)
			}
			return
		}
		var count int64
		database.Model(&User{}).Where("username = ?", username).Count(&count)
		if count > 0 {
			c.Status(200)
			if err := templates.ExecuteTemplate(c.Writer, "register", gin.H{"Error": "用户名已经存在"}); err != nil {
				log.Println("template register execute error:", err)
			}
			return
		}
		hashedPassword, _ := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
		database.Create(&User{Username: username, PasswordHash: string(hashedPassword)})
		c.Redirect(http.StatusFound, "/login?flash=注册成功，请登录")
	})

	// 登录页
	r.GET("/login", func(c *gin.Context) {
		c.Status(200)
		if err := templates.ExecuteTemplate(c.Writer, "login", gin.H{"Flash": c.Query("flash"), "Error": ""}); err != nil {
			log.Println("template login execute error:", err)
		}
	})

	// 登录处理
	r.POST("/login", func(c *gin.Context) {
		username := c.PostForm("username")
		password := c.PostForm("password")
		if username == "" || password == "" {
			c.Status(200)
			if err := templates.ExecuteTemplate(c.Writer, "login", gin.H{"Error": "用户名密码不能为空"}); err != nil {
				log.Println("template login execute error:", err)
			}
			return
		}
		var user User
		err := database.Where("username = ?", username).First(&user).Error
		if err != nil {
			c.Status(200)
			if err2 := templates.ExecuteTemplate(c.Writer, "login", gin.H{"Error": "用户名或密码错误"}); err2 != nil {
				log.Println("template login execute error:", err2)
			}
			return
		}
		err = bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password))
		if err != nil {
			c.Status(200)
			if err2 := templates.ExecuteTemplate(c.Writer, "login", gin.H{"Error": "用户名或密码错误"}); err2 != nil {
				log.Println("template login execute error:", err2)
			}
			return
		}
		session := sessions.Default(c)
		session.Set("user", user.Username)
		session.Save()
		c.Redirect(http.StatusFound, "/")
	})

	// 登出
	r.GET("/logout", func(c *gin.Context) {
		session := sessions.Default(c)
		session.Clear()
		session.Save()
		c.Redirect(http.StatusFound, "/")
	})

	fmt.Println("服务器启动在 http://localhost:8080")
	err = r.Run(":8080")
	if err != nil {
		log.Fatal(err)
	}
}
