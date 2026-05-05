import re
import os
import pymongo
import urllib
from pyrogram import Client, filters
from pyrogram.types import Message

bot = Client(
    name=":memory:",
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"],
    bot_token=os.environ["BOT_TOKEN"]
)

@bot.on_message(filters.command("start"))
async def _start(_, msg: Message):
    START = """
**Hii {}**, `I am MongoDB Url Checker Bot, Just Send me your MongoDB Url I will tell your Url having any issues to connect or not.`
__Made with ❤ by [𝄟͢🦋⃟≛⃝ 𝐃𝐚𝐫𝐤 𝐨𝐟 𝐃𝐚𝐧𝐠𝐞𝐫 𝄟⃝❤](https://t.me/Dark_of_Danger)__.
"""
    await msg.reply(START.format(msg.from_user.mention), disable_web_page_preview=True)

@bot.on_message(filters.private & filters.text & ~filters.command(["start", "check"]))
async def _private_filter(_, msg: Message):
    url = msg.text
    await check_url(msg, url)
    await msg.delete()  # For Security

@bot.on_message(filters.command("check"))
async def _check(_, msg: Message):
    if len(msg.command) > 1:
        url = msg.command[1]
    else:
        return await msg.reply("`URL not Found!`")
    await check_url(msg, url)
    try:
        await msg.delete()
    except:
        await msg.reply("`I can't delete this Url Myself, Any admin delete this for Security.")

async def check_url(msg: Message, url: str):
    # Supports both old and new MongoDB Atlas URL formats:
    # Old: mongodb+srv://user:pass@cluster0.xxx.mongodb.net/dbname?retryWrites=true&w=majority
    # New: mongodb+srv://user:pass@cluster0.xxx.mongodb.net/?appName=Cluster0
    PATTERN = r"^mongodb(\+srv)?:\/\/([^:]+):([^@]+)@([^\/]+)\/([^\?]*)(\?.*)?"
    s_r = re.compile(r"[@_!#$%^&*()<>?/\|}{~:]")
    match = re.match(PATTERN, url)

    if not match or not url.startswith("mongodb"):
        return await msg.reply(f"**Invalid MongoDB Url**: `{url}`")

    try:
        client = pymongo.MongoClient(url, serverSelectionTimeoutMS=5000)
        client.server_info()  # Force connection check
    except Exception as e:
        err = str(e)
        if "Username and password must be escaped" in err:
            username = match.group(2)
            password = match.group(3)
            host = match.group(4)
            dbname = match.group(5) or "mydb"
            query = match.group(6) or "?retryWrites=true&w=majority"

            if s_r.search(username):
                username = urllib.parse.quote_plus(username)
            if s_r.search(password):
                password = urllib.parse.quote_plus(password)
            if '<' in dbname or '>' in dbname:
                dbname = "Userge"

            prefix = "mongodb+srv" if match.group(1) else "mongodb"
            new_url = f"{prefix}://{username}:{password}@{host}/{dbname}{query}"

            await msg.reply(
                "`Your URL having Invalid Username and Password.`\n\n"
                "`I quoted your Username and Password and created new DB_URI, "
                f"Use this to connect to MongoDB.`\n\n`{new_url}`"
            )
        elif "Authentication failed" in err:
            await msg.reply("`Authentication Failed! Wrong username or password in this URL.`")
        elif "timed out" in err or "ServerSelectionTimeoutError" in err:
            await msg.reply("`Connection Timed Out! IP not whitelisted in MongoDB Atlas (Allow 0.0.0.0/0).`")
        else:
            await msg.reply(f"`Connection Error:` `{err}`")
    else:
        dbname = match.group(5)
        if dbname and ('<' in dbname or '>' in dbname):
            new_url = url.replace(dbname, "Userge")
            return await msg.reply(f"`You forgot to remove '<' and '>' signs.`\n\n**Use this URL:** `{new_url}`")
        await msg.reply("`This URL is ERROR Free. You can use this to connect to MongoDB.`")

if __name__ == "__main__":
    bot.run()
