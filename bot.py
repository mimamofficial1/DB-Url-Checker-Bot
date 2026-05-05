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

# Track processed message IDs to prevent duplicate responses (Railway multi-instance fix)
processed_msgs = set()

@bot.on_message(filters.command("start"))
async def _start(_, msg: Message):
    START = """
**Hii {}**, `I am MongoDB Url Checker Bot, Just Send me your MongoDB Url I will tell your Url having any issues to connect or not.`
__Made with ❤ by [Krishna](https://t.me/Krishna_Singhal)__.
"""
    await msg.reply(START.format(msg.from_user.mention), disable_web_page_preview=True)

@bot.on_message(filters.private & filters.text & ~filters.command(["start", "check"]))
async def _private_filter(_, msg: Message):
    # Prevent duplicate processing from multiple Railway instances
    if msg.id in processed_msgs:
        return
    processed_msgs.add(msg.id)
    # Keep set small
    if len(processed_msgs) > 1000:
        processed_msgs.clear()

    url = msg.text.strip()
    await check_url(msg, url)
    try:
        await msg.delete()
    except:
        pass

@bot.on_message(filters.command("check"))
async def _check(_, msg: Message):
    if msg.id in processed_msgs:
        return
    processed_msgs.add(msg.id)

    if len(msg.command) > 1:
        url = msg.command[1]
    else:
        return await msg.reply("`URL not Found!`")
    await check_url(msg, url)
    try:
        await msg.delete()
    except:
        await msg.reply("`I can't delete this Url Myself, Any admin delete this for Security.`")

async def check_url(msg: Message, url: str):
    # Supports both old and new MongoDB Atlas URL formats
    PATTERN = r"^mongodb(\+srv)?:\/\/([^:]+):([^@]+)@([^\/]+)\/([^\?]*)(\?.*)?"
    s_r = re.compile(r"[@_!#$%^&*()<>?/\|}{~:]")
    match = re.match(PATTERN, url)

    if not match:
        return await msg.reply(f"**Invalid MongoDB Url**: `{url}`")

    # Send a "checking" message while we test the connection
    status_msg = await msg.reply("`🔄 Checking your MongoDB URL, please wait...`")

    try:
        client = pymongo.MongoClient(
            url,
            serverSelectionTimeoutMS=8000,  # 8 second timeout
            connectTimeoutMS=8000
        )
        client.server_info()  # Actually attempts connection
        client.close()
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

            await status_msg.edit(
                "`⚠️ Your URL has Invalid Username/Password (special characters).`\n\n"
                "`I fixed it for you. Use this URL:`\n\n"
                f"`{new_url}`"
            )

        elif "Authentication failed" in err or "bad auth" in err.lower():
            await status_msg.edit("`❌ Authentication Failed! Wrong username or password.`")

        elif "timed out" in err.lower() or "ServerSelectionTimeoutError" in err:
            await status_msg.edit(
                "`⏱️ Connection Timed Out!`\n\n"
                "`Your URL format is correct but connection failed.\n"
                "Possible reasons:\n"
                "• IP not whitelisted in MongoDB Atlas\n"
                "• Go to Atlas → Network Access → Add 0.0.0.0/0`"
            )

        elif "Name or service not known" in err or "nodename nor servname" in err:
            await status_msg.edit("`❌ Invalid hostname in URL! Check your cluster address.`")

        else:
            await status_msg.edit(f"`❌ Connection Error:`\n`{err[:300]}`")
        return

    # Connection successful
    dbname = match.group(5)
    if dbname and ('<' in dbname or '>' in dbname):
        new_url = url.replace(dbname, "Userge")
        await status_msg.edit(
            f"`⚠️ You forgot to remove '<' and '>' signs.`\n\n"
            f"**Use this URL:** `{new_url}`"
        )
    else:
        await status_msg.edit("`✅ This URL is ERROR Free. You can use this to connect to MongoDB.`")

if __name__ == "__main__":
    bot.run()
