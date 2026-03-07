from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import subprocess
import json
import os
import functools

app = Flask(__name__)
app.secret_key = "perfectorganic2026"

DASHBOARD_PASSWORD = "admin123"
BOT_DIR = "/opt/bot/telegram_bot"
SERVICE_NAME = "perfectorganic-bot"


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Неверный пароль"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/status")
@login_required
def api_status():
    output = run_cmd(f"systemctl is-active {SERVICE_NAME}")
    is_running = output.strip() == "active"
    uptime = run_cmd(f"systemctl show {SERVICE_NAME} --property=ActiveEnterTimestamp --value").strip()
    return jsonify({"running": is_running, "uptime": uptime})


@app.route("/api/logs")
@login_required
def api_logs():
    lines = request.args.get("lines", 50)
    logs = run_cmd(f"journalctl -u {SERVICE_NAME} -n {lines} --no-pager -o short-iso")
    return jsonify({"logs": logs})


@app.route("/api/restart", methods=["POST"])
@login_required
def api_restart():
    run_cmd(f"systemctl restart {SERVICE_NAME}")
    return jsonify({"ok": True, "message": "Бот перезапущен"})


@app.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    run_cmd(f"systemctl stop {SERVICE_NAME}")
    return jsonify({"ok": True, "message": "Бот остановлен"})


@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    run_cmd(f"systemctl start {SERVICE_NAME}")
    return jsonify({"ok": True, "message": "Бот запущен"})


@app.route("/api/update", methods=["POST"])
@login_required
def api_update():
    output = run_cmd("cd /opt/bot && git pull origin main")
    run_cmd(f"systemctl restart {SERVICE_NAME}")
    return jsonify({"ok": True, "message": output.strip()})


@app.route("/api/saved_posts")
@login_required
def api_saved_posts():
    path = os.path.join(BOT_DIR, "saved_posts.json")
    if not os.path.exists(path):
        return jsonify({"posts": []})
    with open(path) as f:
        posts = json.load(f)
    return jsonify({"posts": posts})


@app.route("/api/delete_post/<int:index>", methods=["POST"])
@login_required
def api_delete_post(index):
    path = os.path.join(BOT_DIR, "saved_posts.json")
    if not os.path.exists(path):
        return jsonify({"ok": False})
    with open(path) as f:
        posts = json.load(f)
    if 0 <= index < len(posts):
        posts.pop(index)
        with open(path, "w") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
