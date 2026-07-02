"""
BAAI-CFTS 退订收集后端 - 阿里云函数计算 FC Web函数版本
技术栈：Python + Flask + SQLite(示例) + SMTP转发
部署方式：阿里云函数计算 FC 自定义运行时（Web函数）
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import datetime
import os

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "/tmp/unsubscribe.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS unsubscribe_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            name TEXT,
            organization TEXT,
            campaign_id TEXT,
            token TEXT,
            reasons TEXT,
            other_text TEXT,
            user_agent TEXT,
            ip TEXT,
            page_url TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


init_db()

# ---------- SMTP转发配置：全部通过环境变量注入，不要硬编码 ----------
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qiye.aliyun.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
NOTIFY_TO = os.environ.get("NOTIFY_TO", "")

# ---------- 简单的退订Token校验（占位实现，建议替换为签名校验或数据库比对） ----------
def verify_token(email: str, token: str, campaign_id: str) -> bool:
    """
    校验退订链接中的token是否有效。
    当前为占位实现：仅校验token非空。
    生产环境建议：
    1. 生成链接时用 HMAC(secret, email+campaign_id) 作为token，此处重新计算并比对；
    2. 或在数据库中记录token与email的映射，查库比对。
    """
    if not token or not email:
        return False
    return True


def forward_to_email(record):
    if not SMTP_USER or not SMTP_PASS or not NOTIFY_TO:
        print("SMTP 环境变量未配置完整，跳过邮件转发")
        return False

    subject = "[退订通知] " + (record["name"] or record["email"]) + " 已退订"
    body = (
        "姓名：" + str(record["name"]) + "\n"
        + "所属机构：" + str(record["organization"]) + "\n"
        + "退订邮箱：" + str(record["email"]) + "\n"
        + "活动编号：" + str(record["campaign_id"]) + "\n"
        + "退订原因：" + str(record["reasons"]) + "\n"
        + "补充说明：" + str(record["other_text"]) + "\n"
        + "提交时间：" + str(record["created_at"]) + "\n"
        + "IP地址：" + str(record["ip"]) + "\n"
        + "User-Agent：" + str(record["user_agent"]) + "\n"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_TO

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [NOTIFY_TO], msg.as_string())
        return True
    except Exception as e:
        print("邮件转发失败：", e)
        return False


@app.route("/unsubscribe", methods=["GET"])
def unsubscribe_page():
    """
    渲染退订页面。邮件模板中的退订链接应指向：
    https://<你的FC域名>/unsubscribe?email=xxx&token=xxx&cid=活动编号
    页面内的JS会自行从URL参数中读取email/token/cid并展示、并在提交时POST到/api/unsubscribe。
    """
    email = request.args.get("email", "")
    token = request.args.get("token", "")
    campaign_id = request.args.get("cid", "")

    if not verify_token(email, token, campaign_id):
        return "退订链接无效或已过期，请联系管理员。", 400

    # 直接渲染 templates/unsubscribe.html（页面内JS会自己读取URL参数，无需服务端注入变量）
    return render_template("unsubscribe.html")


@app.route("/api/unsubscribe", methods=["POST"])
def unsubscribe():
    data = request.get_json(force=True)
    email = data.get("email", "")
    token = data.get("token", "")
    campaign_id = data.get("campaignid", data.get("campaign_id", ""))

    if not verify_token(email, token, campaign_id):
        return jsonify({"status": "error", "message": "invalid token"}), 400

    record = {
        "email": email,
        "name": data.get("name", ""),
        "organization": data.get("organization", ""),
        "campaign_id": campaign_id,
        "token": token,
        "reasons": ",".join(data.get("reasons", [])),
        "other_text": data.get("othertext", data.get("other_text", "")),
        "user_agent": data.get("useragent", data.get("user_agent", "")),
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "page_url": data.get("pageurl", data.get("page_url", "")),
        "created_at": datetime.datetime.utcnow().isoformat(),
    }

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO unsubscribe_log
        (email, name, organization, campaign_id, token, reasons, other_text, user_agent, ip, page_url, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        tuple(record.values()),
    )
    conn.commit()
    conn.close()

    forward_to_email(record)

    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
