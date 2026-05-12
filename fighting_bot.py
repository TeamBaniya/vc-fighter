import requests
import time
import json
import asyncio
import os
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
from pytgcalls import GroupCallFactory
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID

TOKEN = BOT_TOKEN
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Data storage
user_account = None
user_client = None
user_vc = None
current_group = None
current_vc_chat_id = None
sudo_users = [OWNER_ID]
temp_data = {}

last_update_id = 0
user_states = {}

print("="*60)
print("🎵 VC FIGHTING BOT")
print("="*60)
print("Bot started! Send /start on Telegram\n")

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"{API_URL}/sendMessage", json=data, timeout=5)
    except:
        pass

def is_sudo(user_id):
    return user_id in sudo_users

async def login_user(phone_number, chat_id):
    try:
        client = Client(f"user_{phone_number}", api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        
        sent_code = await client.send_code(phone_number)
        temp_data[chat_id] = {"client": client, "phone": phone_number, "phone_code_hash": sent_code.phone_code_hash, "step": "waiting_otp"}
        send_message(chat_id, "📨 OTP Sent!\n\nPlease send the OTP code:")
        return True
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)}")
        return False

async def verify_otp(chat_id, code):
    if chat_id not in temp_data:
        send_message(chat_id, "❌ Session expired! Please start over.")
        return False
    
    data = temp_data[chat_id]
    client = data["client"]
    
    try:
        await client.sign_in(data["phone"], code, phone_code_hash=data["phone_code_hash"])
        me = await client.get_me()
        
        global user_account, user_client, user_vc
        user_client = client
        user_account = {"name": me.first_name, "id": me.id, "username": me.username, "phone": data["phone"]}
        
        # Fixed: Use get_group_call() instead of get_file_group_call()
        factory = GroupCallFactory(client)
        user_vc = factory.get_group_call()
        # Note: Don't auto-start here, start when needed
        
        send_message(chat_id, f"✅ Logged in successfully!\n\n👤 Name: {me.first_name}\n🆔 ID: {me.id}\n\n📎 Send Group Info\n\nFor Public Groups:\nSend username: @groupusername\n\nFor Private Groups:\nSend invite link: https://t.me/+xxxxx")
        
        del temp_data[chat_id]
        return True
    except SessionPasswordNeeded:
        temp_data[chat_id]["step"] = "waiting_2fa"
        send_message(chat_id, "🔐 2FA Enabled\n\nPlease send your 2FA password:")
        return False
    except PhoneCodeInvalid:
        send_message(chat_id, "❌ Invalid OTP! Please try again.\n\nSend OTP code:")
        return False
    except PhoneCodeExpired:
        send_message(chat_id, "❌ OTP Expired! Please start over with /start")
        del temp_data[chat_id]
        return False
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)}")
        return False

async def verify_2fa(chat_id, password):
    if chat_id not in temp_data:
        send_message(chat_id, "❌ Session expired! Please start over.")
        return False
    
    data = temp_data[chat_id]
    client = data["client"]
    
    try:
        await client.check_password(password)
        me = await client.get_me()
        
        global user_account, user_client, user_vc
        user_client = client
        user_account = {"name": me.first_name, "id": me.id, "username": me.username, "phone": data["phone"]}
        
        # Fixed: Use get_group_call() instead of get_file_group_call()
        factory = GroupCallFactory(client)
        user_vc = factory.get_group_call()
        
        send_message(chat_id, f"✅ Logged in successfully!\n\n👤 Name: {me.first_name}\n🆔 ID: {me.id}\n\n📎 Send Group Info\n\nFor Public Groups:\nSend username: @groupusername\n\nFor Private Groups:\nSend invite link: https://t.me/+xxxxx")
        
        del temp_data[chat_id]
        return True
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)}\n\nPlease send 2FA password again:")
        return False

async def play_audio(chat_id, audio_source, group_id, group_name):
    global user_vc, current_vc_chat_id
    
    if not user_vc:
        send_message(chat_id, "❌ No account logged in! Use /start to login")
        return False
    
    try:
        # Join the voice chat if not already in it
        if current_vc_chat_id != group_id:
            await user_vc.join(group_id)
            current_vc_chat_id = group_id
        
        # Fixed: Use start_audio() instead of play(MediaStream())
        await user_vc.start_audio(audio_source)
        send_message(chat_id, f"✅ Now Playing!\n\n📻 Group: {group_name}\n🎵 Audio is playing!\n\nUse /stop to stop.")
        return True
    except Exception as e:
        send_message(chat_id, f"❌ Error playing audio: {str(e)[:100]}")
        return False

async def stop_audio(chat_id):
    global user_vc
    if not user_vc:
        send_message(chat_id, "❌ No active voice chat!")
        return
    
    try:
        # Fixed: Use stop_audio() instead of stop()
        await user_vc.stop_audio()
        send_message(chat_id, f"✅ Stopped playing!")
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)}")

async def logout_user(chat_id):
    global user_client, user_account, user_vc, current_vc_chat_id, current_group
    
    if user_vc:
        try:
            await user_vc.leave()  # Leave the voice chat
            await user_vc.stop_audio()
        except:
            pass
    
    if user_client:
        try:
            await user_client.stop()
        except:
            pass
    
    user_client = None
    user_account = None
    user_vc = None
    current_vc_chat_id = None
    current_group = None
    
    send_message(chat_id, "✅ Logged out successfully!\n\nSend /start to login again.")

async def handle_callback(chat_id, user_id, data_cb):
    if data_cb == "default_account":
        send_message(chat_id, "🔧 Default account coming soon!\n\nUse 'Login My Account' for now.")
    elif data_cb == "login_account":
        send_message(chat_id, "📱 Login to Your Account\n\nSend your phone number with country code:\nExample: +919876543210")
        user_states[user_id] = {"step": "waiting_phone"}
    elif data_cb == "play_audio":
        if not user_account:
            send_message(chat_id, "❌ No account logged in! Use /start first.")
        elif not current_group:
            send_message(chat_id, "❌ No group selected! Send group username or invite link.")
        else:
            send_message(chat_id, "🎵 Send Audio\n\nYou can send:\n• Audio file 🎵\n• Voice message 🎤")
            user_states[user_id] = {"step": "waiting_audio"}
    elif data_cb == "logout":
        await logout_user(chat_id)

async def main():
    global last_update_id
    while True:
        try:
            response = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id + 1, "timeout": 30}, timeout=35)
            if response.status_code != 200:
                time.sleep(5)
                continue
            data = response.json()
            if not data.get("ok"):
                time.sleep(5)
                continue
            
            for update in data.get("result", []):
                last_update_id = update["update_id"]
                
                if "callback_query" in update:
                    callback = update["callback_query"]
                    user_id = callback["from"]["id"]
                    chat_id = callback["message"]["chat"]["id"]
                    data_cb = callback["data"]
                    
                    print(f"\n📞 Callback: {data_cb}")
                    
                    if not is_sudo(user_id):
                        send_message(chat_id, "❌ Access Denied! Only bot owner can use this bot.")
                        requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback["id"]})
                        continue
                    
                    await handle_callback(chat_id, user_id, data_cb)
                    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback["id"]})
                
                elif "message" in update:
                    msg = update["message"]
                    user_id = msg["from"]["id"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    audio = msg.get("audio")
                    voice = msg.get("voice")
                    
                    print(f"\n📨 Message: {text if text else '[Audio/Voice]'}")
                    
                    if not is_sudo(user_id):
                        send_message(chat_id, "❌ Access Denied!")
                        continue
                    
                    # Handle phone number input
                    if user_id in user_states and user_states[user_id].get("step") == "waiting_phone":
                        phone = text.strip()
                        if phone.startswith("+") and len(phone) > 8:
                            send_message(chat_id, "⏳ Logging in...")
                            await login_user(phone, chat_id)
                            del user_states[user_id]
                        else:
                            send_message(chat_id, "❌ Invalid phone number! Example: +919876543210")
                    
                    # Handle OTP input
                    elif user_id in temp_data and temp_data.get(user_id, {}).get("step") == "waiting_otp":
                        code = text.strip().replace(" ", "")
                        if code.isdigit():
                            await verify_otp(user_id, code)
                        else:
                            send_message(chat_id, "❌ Please send numbers only!")
                    
                    # Handle 2FA input
                    elif user_id in temp_data and temp_data.get(user_id, {}).get("step") == "waiting_2fa":
                        await verify_2fa(user_id, text.strip())
                    
                    # Handle group info
                    elif user_id in user_states and user_states[user_id].get("step") == "waiting_group":
                        group_input = text.strip()
                        
                        if group_input.startswith("@"):
                            username = group_input[1:]
                            try:
                                resp = requests.get(f"{API_URL}/getChat", params={"chat_id": f"@{username}"}, timeout=10)
                                if resp.ok:
                                    chat_info = resp.json()["result"]
                                    global current_group
                                    current_group = {"name": chat_info.get("title", username), "chat_id": chat_info["id"], "username": username}
                                    send_message(chat_id, f"✅ Group set: {current_group['name']}\n\n🎵 Send Audio")
                                    user_states[user_id] = {"step": "waiting_audio"}
                                else:
                                    send_message(chat_id, f"❌ Cannot find group @{username}")
                            except Exception as e:
                                send_message(chat_id, f"❌ Error: {e}")
                        
                        elif "t.me/" in group_input:
                            user_states[user_id] = {"step": "waiting_chat_id", "invite_link": group_input}
                            send_message(chat_id, "⚠️ Send Chat ID (example: -100123456789)")
                        
                        else:
                            send_message(chat_id, "❌ Invalid format! Send @username or invite link.")
                    
                    # Handle Chat ID
                    elif user_id in user_states and user_states[user_id].get("step") == "waiting_chat_id":
                        try:
                            chat_id_val = int(text.strip())
                            current_group = {"name": "Group", "chat_id": chat_id_val, "invite_link": user_states[user_id]["invite_link"]}
                            send_message(chat_id, f"✅ Chat ID received: {chat_id_val}\n\n🎵 Send Audio")
                            user_states[user_id] = {"step": "waiting_audio"}
                        except:
                            send_message(chat_id, "❌ Invalid Chat ID!")
                    
                    # Handle audio for playing
                    elif user_id in user_states and user_states[user_id].get("step") == "waiting_audio":
                        if not current_group:
                            send_message(chat_id, "❌ No group selected!")
                            del user_states[user_id]
                            continue
                        
                        os.makedirs("audio", exist_ok=True)
                        
                        if audio:
                            send_message(chat_id, "📥 Downloading audio...")
                            audio_path = await msg.download("audio/")
                            await play_audio(chat_id, audio_path, current_group["chat_id"], current_group["name"])
                            del user_states[user_id]
                        elif voice:
                            send_message(chat_id, "📥 Downloading voice...")
                            voice_path = await msg.download("audio/")
                            await play_audio(chat_id, voice_path, current_group["chat_id"], current_group["name"])
                            del user_states[user_id]
                        else:
                            send_message(chat_id, "❌ Please send an audio file or voice message.")
                    
                    # Handle commands
                    elif text == "/start":
                        if user_account:
                            kb = {"inline_keyboard": [[{"text": "🎵 Play Audio", "callback_data": "play_audio"}], [{"text": "🚪 Logout", "callback_data": "logout"}]]}
                            send_message(chat_id, f"🎵 Welcome Back, {user_account['name']}! ✅\n\nChoose an option:\n\nPowered by @sparsh_vc_bot", kb)
                        else:
                            kb = {"inline_keyboard": [[{"text": "📱 Login My Account", "callback_data": "login_account"}]]}
                            send_message(chat_id, "🎵 **Welcome to VC Fighting Bot!**\n\nChoose an option:\n\n• **Login My Account:** Use your own account\n\n**Commands:**\n• `/logout` - Logout\n• `/stop` - Stop playing\n\nPowered by @sparsh_vc_bot", kb)
                    
                    elif text == "/addsudo":
                        if user_id != OWNER_ID:
                            send_message(chat_id, "❌ Only bot owner can add sudo users!")
                            continue
                        parts = text.split()
                        if len(parts) != 2:
                            send_message(chat_id, "Usage: /addsudo <user_id>")
                            continue
                        try:
                            sudo_id = int(parts[1])
                            if sudo_id not in sudo_users:
                                sudo_users.append(sudo_id)
                                send_message(chat_id, f"✅ User {sudo_id} added as sudo user!")
                            else:
                                send_message(chat_id, "User already in sudo list!")
                        except:
                            send_message(chat_id, "❌ Invalid user ID!")
                    
                    elif text == "/rmsudo":
                        if user_id != OWNER_ID:
                            send_message(chat_id, "❌ Only bot owner can remove sudo users!")
                            continue
                        parts = text.split()
                        if len(parts) != 2:
                            send_message(chat_id, "Usage: /rmsudo <user_id>")
                            continue
                        try:
                            sudo_id = int(parts[1])
                            if sudo_id in sudo_users and sudo_id != OWNER_ID:
                                sudo_users.remove(sudo_id)
                                send_message(chat_id, f"✅ User {sudo_id} removed from sudo!")
                            else:
                                send_message(chat_id, "User not found in sudo list!")
                        except:
                            send_message(chat_id, "❌ Invalid user ID!")
                    
                    elif text == "/logout":
                        if user_account:
                            await logout_user(chat_id)
                        else:
                            send_message(chat_id, "❌ No account is logged in!")
                    
                    elif text == "/stop":
                        await stop_audio(chat_id)
                    
                    elif text and not text.startswith("/"):
                        if (text.startswith("@") or "t.me/" in text) and user_account:
                            user_states[user_id] = {"step": "waiting_group"}
                            send_message(chat_id, "📎 Send Group Info\n\nPublic: @username\nPrivate: invite link")
                        elif not user_account:
                            send_message(chat_id, "❌ Please login first using /start")
            
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
