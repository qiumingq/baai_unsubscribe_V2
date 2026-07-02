# BAAI-CFTS 退订服务 - 阿里云FC部署包

## 目录结构
baai_unsubscribe_fc/
├── app.py              已修改：新增GET /unsubscribe路由、端口改为9000、SMTP配置改为环境变量、增加token校验占位、增加/health健康检查
├── requirements.txt    Flask依赖声明
└── templates/
    └── unsubscribe.html   【需要你手动放入】把你原来的unsubscribe.html原样复制到这个文件夹，文件名不变

## 重要：部署前必须手动完成的1个步骤
由于你上传的unsubscribe.html是渲染后的内容（不含原始HTML标签），
系统无法自动重建逐字节一致的源文件，为避免破坏你精心设计的样式和JS逻辑，
请手动将你本地原始的 unsubscribe.html 文件复制到本包的 templates/ 目录下，
文件名保持 unsubscribe.html 不变即可，app.py 已经写好了对应的 render_template 调用。

## app.py 相比原版的主要改动
1. 新增 GET /unsubscribe 路由：解析URL中的 email、token、cid 参数，校验后渲染 templates/unsubscribe.html
2. 端口由5000改为9000，与FC控制台"监听端口"配置保持一致
3. SMTP_USER / SMTP_PASS / NOTIFY_TO / SMTP_HOST / SMTP_PORT 全部改为从环境变量读取，代码中不再硬编码敏感信息
4. 新增 verify_token() 占位函数，目前只校验非空，生产环境务必替换为HMAC签名校验或数据库比对，防止恶意刷退订
5. DB_PATH 默认改为 /tmp/unsubscribe.db（FC实例的可写目录），并强烈建议后续迁移到RDS或表格存储做持久化
6. 新增 /health 健康检查路由，方便FC或负载均衡做存活检测
7. POST接口增加token校验，与GET页面共用同一套校验逻辑

## 部署到阿里云FC的步骤
1. 在本地 templates/ 目录放入你的 unsubscribe.html 原始文件
2. 在项目根目录执行: pip install -r requirements.txt -t . (将依赖打包进目录，自定义运行时不会自动安装依赖)
3. 将整个 baai_unsubscribe_fc 目录打包为zip
4. 回到FC控制台创建Web函数页面，代码上传方式选择"通过ZIP包上传代码"
5. 启动命令保持: python3 app.py
6. 监听端口保持: 9000
7. 在"环境变量"配置区域(高级配置下方)添加: SMTP_USER, SMTP_PASS, NOTIFY_TO, SMTP_HOST(可选), SMTP_PORT(可选)
8. 部署完成后，用FC分配的域名访问 https://<域名>/health 确认返回healthy
9. 再访问 https://<域名>/unsubscribe?email=test@test.com&token=abc&cid=001 确认退订页面正常渲染
10. 最后在邮件模板中把退订链接替换为 https://<你的FC域名>/unsubscribe?email={{email}}&token={{token}}&cid={{campaign_id}}

## 后续建议(未在本次修改中实现，需要你后续补充)
- verify_token() 替换为真实的HMAC签名校验
- SQLite迁移到阿里云RDS或表格存储做持久化，避免FC实例回收导致数据丢失
- 执行超时时间可从60秒调整到90-120秒，为数据库校验预留余量
