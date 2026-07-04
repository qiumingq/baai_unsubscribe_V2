# BAAI-CFTS 退订服务 - 香港轻量应用服务器部署包

## 目录结构

baai_unsubscribe_V2/
├── app.py              已改造：适配轻量服务器常驻部署，端口可配置，SQLite本地持久化
├── requirements.txt    Flask + gunicorn 依赖声明
├── README.md           本文件
└── templates/
    └── unsubscribe.html   【需要你手动放入】把你原来的unsubscribe.html原样复制到这个文件夹，文件名不变

## 服务器基本信息

- 系统：Alibaba Cloud Linux (alinux)，内核 5.10.134-19.1.al8.x86_64
- Python版本：3.10（已通过源码编译安装在 /usr/local/python3.10/bin/python3.10，与系统自带3.6隔离共存）
- 地域：香港节点（无需ICP备案，可直接对外提供服务）
- 服务端口：10000（可通过环境变量 PORT 修改）
- 域名：baai-cfts.org.cn（阿里云已购买，需手动做A记录解析）

## app.py 相比FC版本的主要改动

1. 数据库路径由 /tmp/unsubscribe.db 改为项目目录下的 unsubscribe.db，避免服务器重启/进程重启导致数据丢失
2. 端口默认改回 10000，与之前已验证成功的开发环境端口保持一致，可通过环境变量 PORT 自定义
3. 修复了原始文件中函数体缩进丢失导致的语法错误问题
4. 保留 GET /unsubscribe（渲染退订页并做token校验）、POST /api/unsubscribe（写入数据库+邮件转发）、GET /health（健康检查）三个路由不变
5. SMTP_USER / SMTP_PASS / NOTIFY_TO / SMTP_HOST / SMTP_PORT 依旧从环境变量读取，代码中不硬编码敏感信息
6. requirements.txt 新增 gunicorn，用于生产环境常驻运行

## 部署前必须手动完成的1个步骤

由于之前上传的 unsubscribe.html 是渲染后内容，为避免破坏你精心设计的样式和JS逻辑，请手动将本地原始的 unsubscribe.html 文件复制到本包的 templates/ 目录下，文件名保持 unsubscribe.html 不变，app.py 已经写好了对应的 render_template 调用。

## 完整部署步骤（香港轻量应用服务器）

### 第一步：上传项目文件到服务器

将整个 baai_unsubscribe_V2 文件夹（含 templates/unsubscribe.html）上传到服务器，例如放在 /root/baai_unsubscribe_V2 目录下。可以用 scp 命令从本地传，或者直接在服务器上用 git clone 从你的仓库拉取。

### 第二步：安装依赖

cd /root/baai_unsubscribe_V2
pip install -r requirements.txt

如果你已经按之前的配置把 pip 别名指向了3.10版本，这一步会自动装到正确的Python环境里；如未配置，改用完整路径：

/usr/local/python3.10/bin/python3.10 -m pip install -r requirements.txt

### 第三步：配置环境变量（先临时测试用）

export SMTP_HOST="smtp.qiye.aliyun.com"
export SMTP_USER="noreply@baai-cfts.org.cn"
export SMTP_PASS="你的真实授权码"
export NOTIFY_TO="hychen@baai.ac.cn"
export PORT="10000"

### 第四步：临时测试运行（开发模式，仅用于验证代码可用）

python3 app.py

看到 Running on http://0.0.0.0:10000 说明代码没问题，按 Ctrl+C 停止，准备切换到生产模式。

### 第五步：用gunicorn以生产模式启动

gunicorn -w 4 -b 0.0.0.0:10000 app:app

-w 4 表示启用4个工作进程，可根据服务器CPU核数调整（2核服务器建议设为2-4）。

### 第六步：配置systemd开机自启、后台常驻

创建服务配置文件：

sudo vi /etc/systemd/system/baai-unsub.service

填入以下内容（路径和授权码换成你的真实信息）：

[Unit]
Description=BAAI Unsubscribe Service
After=network.target

[Service]
WorkingDirectory=/root/baai_unsubscribe_V2
Environment="SMTP_HOST=smtp.qiye.aliyun.com"
Environment="SMTP_USER=noreply@baai-cfts.org.cn"
Environment="SMTP_PASS=你的真实授权码"
Environment="NOTIFY_TO=hychen@baai.ac.cn"
Environment="PORT=10000"
ExecStart=/usr/local/python3.10/bin/python3.10 -m gunicorn -w 4 -b 0.0.0.0:10000 app:app
Restart=always

[Install]
WantedBy=multi-user.target

保存退出（Ctrl+O 回车，Ctrl+X 退出），然后启动并设置开机自启：

sudo systemctl daemon-reload
sudo systemctl start baai-unsub
sudo systemctl enable baai-unsub

查看服务运行状态：

sudo systemctl status baai-unsub

查看实时日志（排查问题时用）：

sudo journalctl -u baai-unsub -f

### 第七步：开放服务器防火墙端口

登录阿里云控制台，进入轻量应用服务器管理页面：

1. 找到目标服务器实例，点击"防火墙"标签
2. 点击"添加规则"
3. 应用类型选"自定义"，端口范围填 10000，协议选TCP，来源填 0.0.0.0/0
4. 保存生效

### 第八步：配置域名解析

1. 登录阿里云"云解析DNS"控制台
2. 找到 baai-cfts.org.cn 域名，点击"解析设置"
3. 点击"添加记录"，记录类型选"A"，主机记录填 unsub（或按需自定义），记录值填服务器公网IP
4. 点击确认保存，等待几分钟生效

### 第九步：验证部署是否成功

先测试健康检查接口：

http://unsub.baai-cfts.org.cn:10000/health

返回 {"status": "healthy"} 说明服务正常运行。

再测试退订页面（token需要用邮箱和活动编号按 md5(email:campaign_id) 取前16位算出）：

http://unsub.baai-cfts.org.cn:10000/unsubscribe?email=test@test.com&token=xxxx&cid=001

能看到退订页面正常渲染即部署成功。

### 第十步（可选，强烈建议）：配置Nginx反代 + HTTPS证书

直接用 域名:10000 这种方式访问虽然能用，但正式对外发送邮件时建议走标准的443端口（HTTPS），体验和安全性更好：

sudo yum install nginx -y
sudo nano /etc/nginx/conf.d/baai-unsub.conf

写入以下反代配置：

server {
    listen 80;
    server_name unsub.baai-cfts.org.cn;

    location / {
        proxy_pass http://127.0.0.1:10000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

保存后重启Nginx：

sudo systemctl restart nginx

之后在阿里云SSL证书控制台申请一个免费DV证书，绑定到这个域名，配置好HTTPS后就能用 https://unsub.baai-cfts.org.cn/unsubscribe?... 这种标准链接了，不用再带端口号。

## 邮件模板中退订链接的正确格式

批量发信脚本(batch_mailer.py)生成退订链接时，需要用以下格式：

https://unsub.baai-cfts.org.cn/unsubscribe?email={{email}}&token={{token}}&cid={{campaign_id}}

其中 token 必须用以下算法计算，与 app.py 里的 generate_token() 保持完全一致：

import hashlib
token = hashlib.md5(f"{email}:{campaign_id}".encode("utf-8")).hexdigest()[:16]

## 后续建议（未在本次修改中实现，需要你后续补充）

- verify_token() 目前是md5简单校验，如需更高安全性可替换为HMAC签名校验
- 定期备份 unsubscribe.db 数据库文件，避免服务器故障导致数据丢失，可用 crontab 配置每日自动备份到OSS
- 如果退订量较大，建议后续迁移到阿里云RDS做数据库持久化，而不是单文件SQLite
- 生产环境如需调整并发能力，可修改 gunicorn 的 -w 参数（工作进程数），或改用 gevent worker 提升并发处理能力
