import re
import os
import time
import json
import urllib
import pymongo
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

# ─── Config ───────────────────────────────────────────────────────────────────
API_ID      = int(os.environ["API_ID"])
API_HASH    = os.environ["API_HASH"]
BOT_TOKEN   = os.environ["BOT_TOKEN"]
ADMIN_IDS   = list(map(int, os.environ.get("ADMIN_IDS", "0").split()))
STATS_FILE  = "stats.json"

bot = Client(name=":memory:", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ─── Duplicate message guard ───────────────────────────────────────────────────
processed_msgs = set()

def guard(msg_id):
    if msg_id in processed_msgs:
        return False
    processed_msgs.add(msg_id)
    if len(processed_msgs) > 1000:
        processed_msgs.clear()
    return True

# ─── Stats helpers ─────────────────────────────────────────────────────────────
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE) as f:
            return json.load(f)
    return {"total_checks": 0, "valid": 0, "invalid": 0, "errors": 0, "users": [], "start_time": time.time()}

def save_stats(s):
    with open(STATS_FILE, "w") as f:
        json.dump(s, f)

def add_user(user_id):
    s = load_stats()
    if user_id not in s["users"]:
        s["users"].append(user_id)
        save_stats(s)

def bump(key):
    s = load_stats()
    s[key] = s.get(key, 0) + 1
    save_stats(s)

# ─── URL helpers ───────────────────────────────────────────────────────────────
PATTERN = r"^mongodb(\+srv)?:\/\/([^:]+):([^@]+)@([^\/]+)\/([^\?]*)(\?.*)?"
SPECIAL  = re.compile(r"[@_!#$%^&*()<>?/\|}{~:]")

def parse_url(url):
    return re.match(PATTERN, url.strip())

def is_admin(user_id):
    return user_id in ADMIN_IDS

def mongo_connect(url, timeout=8000):
    client = pymongo.MongoClient(url, serverSelectionTimeoutMS=timeout, connectTimeoutMS=timeout)
    client.server_info()
    return client

# ═══════════════════════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    add_user(msg.from_user.id)
    text = (
        f"**👋 Hello {msg.from_user.mention}!**\n\n"
        "**I am MongoDB URL Checker Bot** — **your one-stop tool to validate, "
        "diagnose, and inspect MongoDB connection strings.**\n\n"
        "**🚀 Quick Start:**\n"
        "**Just send me any MongoDB URL and I'll check it instantly!**\n\n"
        "**Use /help to see all commands.**\n\n"
        "__Made with ❤️ by [𝄟͢🦋⃟≛⃝ 𝐃𝐚𝐫𝐤 𝐨𝐟 𝐃𝐚𝐧𝐠𝐞𝐫 𝄟⃝❤](https://t.me/Dark_of_Danger)__"
    )
    await msg.reply(text, disable_web_page_preview=True)

# ═══════════════════════════════════════════════════════════════════════════════
# /help
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("help"))
async def cmd_help(_, msg: Message):
    text = (
        "**📖 Commands List**\n\n"
        "**🔍 Checking**\n"
        "`/check <url>` — Check if a MongoDB URL is valid\n"
        "`/ping <url>` — Measure connection latency\n"
        "`/info <url>` — Get detailed DB info (version, DBs, collections)\n\n"
        "**🔧 Tools**\n"
        "`/encode <url>` — Auto-encode special characters in URL\n"
        "`/convert <url>` — Convert between old & new URL formats\n\n"
        "**📊 Stats**\n"
        "`/stats` — Bot usage statistics\n\n"
        "**📢 Admin Only**\n"
        "`/broadcast <msg>` — Send message to all users\n"
        "`/users` — Total user count\n\n"
        "💡 **Tip:** You can also just paste a MongoDB URL directly — no command needed!"
    )
    await msg.reply(text)

# ═══════════════════════════════════════════════════════════════════════════════
# /check
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("check"))
async def cmd_check(_, msg: Message):
    if not guard(msg.id): return
    if len(msg.command) < 2:
        return await msg.reply("`Usage: /check <mongodb_url>`")
    url = msg.text.split(None, 1)[1].strip()
    await do_check(msg, url)
    try: await msg.delete()
    except: pass

# ═══════════════════════════════════════════════════════════════════════════════
# /ping
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("ping"))
async def cmd_ping(_, msg: Message):
    if not guard(msg.id): return
    if len(msg.command) < 2:
        return await msg.reply("`Usage: /ping <mongodb_url>`")
    url = msg.text.split(None, 1)[1].strip()

    if not parse_url(url):
        return await msg.reply("**❌ Invalid MongoDB URL format.**")

    status = await msg.reply("`⚡ Pinging MongoDB server...`")
    try:
        start = time.time()
        client = mongo_connect(url)
        latency = round((time.time() - start) * 1000, 2)
        client.close()
        bar = "🟩" * min(10, int(latency / 50)) + "⬜" * max(0, 10 - int(latency / 50))
        quality = "🟢 Excellent" if latency < 100 else ("🟡 Good" if latency < 300 else "🔴 Slow")
        await status.edit(
            f"**⚡ Ping Result**\n\n"
            f"`{bar}`\n\n"
            f"**Latency:** `{latency} ms`\n"
            f"**Quality:** {quality}"
        )
    except Exception as e:
        await status.edit(f"**❌ Ping Failed!**\n\n`{str(e)[:300]}`")

# ═══════════════════════════════════════════════════════════════════════════════
# /info
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("info"))
async def cmd_info(_, msg: Message):
    if not guard(msg.id): return
    if len(msg.command) < 2:
        return await msg.reply("`Usage: /info <mongodb_url>`")
    url = msg.text.split(None, 1)[1].strip()

    if not parse_url(url):
        return await msg.reply("**❌ Invalid MongoDB URL format.**")

    status = await msg.reply("`🔍 Fetching database info...`")
    try:
        client = mongo_connect(url)
        server_info = client.server_info()
        db_names = client.list_database_names()

        total_collections = 0
        db_lines = []
        for db_name in db_names:
            if db_name in ("admin", "local", "config"):
                continue
            db = client[db_name]
            cols = db.list_collection_names()
            total_collections += len(cols)
            db_lines.append(f"  • `{db_name}` — {len(cols)} collection(s)")

        client.close()

        dbs_text = "\n".join(db_lines) if db_lines else "  _No user databases found_"
        await status.edit(
            f"**📊 MongoDB Info**\n\n"
            f"**🖥 Server Version:** `{server_info.get('version', 'N/A')}`\n"
            f"**⚙️ Storage Engine:** `{server_info.get('storageEngines', ['N/A'])[0]}`\n"
            f"**🗃 Total Databases:** `{len(db_names)}`\n"
            f"**📁 Total Collections:** `{total_collections}`\n\n"
            f"**📂 Databases:**\n{dbs_text}"
        )
    except Exception as e:
        err = str(e)
        if "Authentication failed" in err or "bad auth" in err.lower():
            await status.edit("**❌ Authentication Failed!** Cannot fetch info — wrong credentials.")
        elif "timed out" in err.lower():
            await status.edit("**⏱ Connection Timed Out!** Check IP whitelist in Atlas.")
        else:
            await status.edit(f"**❌ Error:**\n`{err[:300]}`")

# ═══════════════════════════════════════════════════════════════════════════════
# /encode
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("encode"))
async def cmd_encode(_, msg: Message):
    if not guard(msg.id): return
    if len(msg.command) < 2:
        return await msg.reply("`Usage: /encode <mongodb_url>`")
    url = msg.text.split(None, 1)[1].strip()
    match = parse_url(url)

    if not match:
        return await msg.reply("**❌ Invalid MongoDB URL format.**")

    username = urllib.parse.quote_plus(match.group(2))
    password = urllib.parse.quote_plus(match.group(3))
    host     = match.group(4)
    dbname   = match.group(5) or ""
    query    = match.group(6) or ""
    prefix   = "mongodb+srv" if match.group(1) else "mongodb"

    encoded_url = f"{prefix}://{username}:{password}@{host}/{dbname}{query}"

    if encoded_url == url:
        await msg.reply("**✅ URL already has no special characters — no encoding needed!**")
    else:
        await msg.reply(
            f"**🔐 Encoded URL:**\n\n`{encoded_url}`\n\n"
            f"**Username:** `{match.group(2)}` → `{username}`\n"
            f"**Password:** `{match.group(3)}` → `{password}`"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# /convert
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("convert"))
async def cmd_convert(_, msg: Message):
    if not guard(msg.id): return
    if len(msg.command) < 2:
        return await msg.reply("`Usage: /convert <mongodb_url>`")
    url = msg.text.split(None, 1)[1].strip()
    match = parse_url(url)

    if not match:
        return await msg.reply("**❌ Invalid MongoDB URL format.**")

    username = match.group(2)
    password = match.group(3)
    host     = match.group(4)
    prefix   = "mongodb+srv" if match.group(1) else "mongodb"

    # Detect current format
    if "retryWrites=true" in url:
        # Old → New
        new_url = f"{prefix}://{username}:{password}@{host}/?appName=Cluster0"
        fmt = "Old → New"
    else:
        # New → Old
        dbname  = match.group(5) or "myDatabase"
        new_url = f"{prefix}://{username}:{password}@{host}/{dbname}?retryWrites=true&w=majority"
        fmt = "New → Old"

    await msg.reply(
        f"**🔄 Converted URL ({fmt}):**\n\n"
        f"**Before:** `{url}`\n\n"
        f"**After:** `{new_url}`"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# /stats
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("stats"))
async def cmd_stats(_, msg: Message):
    s = load_stats()
    uptime_sec = int(time.time() - s.get("start_time", time.time()))
    h, rem = divmod(uptime_sec, 3600)
    m, sec = divmod(rem, 60)
    await msg.reply(
        f"**📈 Bot Statistics**\n\n"
        f"**👥 Total Users:** `{len(s.get('users', []))}`\n"
        f"**🔍 Total Checks:** `{s.get('total_checks', 0)}`\n"
        f"**✅ Valid URLs:** `{s.get('valid', 0)}`\n"
        f"**❌ Invalid URLs:** `{s.get('invalid', 0)}`\n"
        f"**⚠️ Errors:** `{s.get('errors', 0)}`\n"
        f"**⏱ Uptime:** `{h}h {m}m {sec}s`"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# /broadcast (Admin only)
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("broadcast"))
async def cmd_broadcast(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("**🚫 Admin only command!**")
    if len(msg.command) < 2:
        return await msg.reply("`Usage: /broadcast <message>`")

    text = msg.text.split(None, 1)[1]
    s = load_stats()
    users = s.get("users", [])

    status = await msg.reply(f"`📢 Broadcasting to {len(users)} users...`")
    success, fail = 0, 0
    for uid in users:
        try:
            await bot.send_message(uid, f"📢 **Broadcast:**\n\n{text}")
            success += 1
        except:
            fail += 1

    await status.edit(
        f"**📢 Broadcast Done!**\n\n"
        f"**✅ Sent:** `{success}`\n"
        f"**❌ Failed:** `{fail}`"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# /users (Admin only)
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.command("users"))
async def cmd_users(_, msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.reply("**🚫 Admin only command!**")
    s = load_stats()
    await msg.reply(f"**👥 Total Users:** `{len(s.get('users', []))}`")

# ═══════════════════════════════════════════════════════════════════════════════
# Direct URL (private chat — no command)
# ═══════════════════════════════════════════════════════════════════════════════
@bot.on_message(filters.private & filters.text & ~filters.command(
    ["start", "help", "check", "ping", "info", "encode", "convert", "stats", "broadcast", "users"]
))
async def direct_url(_, msg: Message):
    if not guard(msg.id): return
    add_user(msg.from_user.id)
    url = msg.text.strip()
    await do_check(msg, url)
    try: await msg.delete()
    except: pass

# ═══════════════════════════════════════════════════════════════════════════════
# Core check logic (shared)
# ═══════════════════════════════════════════════════════════════════════════════
async def do_check(msg: Message, url: str):
    match = parse_url(url)
    if not match:
        bump("invalid")
        return await msg.reply(f"**❌ Invalid MongoDB URL**\n\n`{url}`\n\n_Make sure it starts with `mongodb://` or `mongodb+srv://`_")

    bump("total_checks")
    status = await msg.reply("`🔄 Checking your MongoDB URL...`")

    try:
        client = mongo_connect(url)
        client.close()
    except Exception as e:
        err = str(e)
        bump("errors")

        if "Username and password must be escaped" in err:
            username = urllib.parse.quote_plus(match.group(2))
            password = urllib.parse.quote_plus(match.group(3))
            host     = match.group(4)
            dbname   = match.group(5) or "mydb"
            query    = match.group(6) or "?retryWrites=true&w=majority"
            if '<' in dbname or '>' in dbname: dbname = "Userge"
            prefix   = "mongodb+srv" if match.group(1) else "mongodb"
            new_url  = f"{prefix}://{username}:{password}@{host}/{dbname}{query}"
            await status.edit(
                f"**⚠️ Special Characters in Username/Password**\n\n"
                f"Use /encode command to fix, or use this:\n\n`{new_url}`"
            )
        elif "Authentication failed" in err or "bad auth" in err.lower():
            await status.edit("**❌ Authentication Failed!**\n\nWrong username or password.")
        elif "timed out" in err.lower() or "ServerSelectionTimeoutError" in err:
            await status.edit(
                "**⏱ Connection Timed Out!**\n\n"
                "URL format is correct but server is unreachable.\n"
                "👉 Go to **Atlas → Network Access → Add `0.0.0.0/0`**"
            )
        elif "Name or service not known" in err or "nodename" in err:
            await status.edit("**❌ Invalid Hostname!** Check your cluster address in the URL.")
        else:
            await status.edit(f"**❌ Connection Error:**\n`{err[:300]}`")
        return

    # Success
    bump("valid")
    dbname = match.group(5)
    if dbname and ('<' in dbname or '>' in dbname):
        new_url = url.replace(dbname, "Userge")
        await status.edit(
            f"**⚠️ Remove `<` and `>` from URL**\n\n**Fixed URL:** `{new_url}`"
        )
    else:
        await status.edit(
            "**✅ URL is ERROR Free!**\n\nYou can safely use this to connect to MongoDB.\n\n"
            "💡 Use /info to see database details or /ping to check latency."
        )

if __name__ == "__main__":
    bot.run()
