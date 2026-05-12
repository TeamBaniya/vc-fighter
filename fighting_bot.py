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
sudo_users = [OWNER_ID]
temp_data = {}
user_states = {}
last_update_id = 0

print("="*60)
print("🎵 VC FIGHTING BOT")
print("="*60)
print("Bot started! Send /start on Telegram\n")

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        print(f"📤 Sent: {text[:50]}... Response: {r.status_code}")
    except Exception as e:
        print(f"Send error: {e}")

def is_sudo(user_id):
    return user_id in sudo_users

async def login_user(phone_number, chat_id):
    try:
        client = Client(f"user_{phone_number}", api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        sent_code = await client.send_code(phone_number)
        temp_data[chat_id] = {
            "client": client, 
            "phone": phone_number, 
            "phone_code_hash": sent_code.phone_code_hash, 
            "step": "waiting_otp"
        }
        send_message(chat_id, "📨 OTP Sent!\n\nSend OTP code (numbers only):")
        print(f"✅ Login initiated for {phone_number}")
        return True
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)[:100]}")
        print(f"Login error: {e}")
        return False

async def verify_otp(chat_id, code):
    print(f"🔐 Verifying OTP for chat {chat_id}")
    
    if chat_id not in temp_data:
        send_message(chat_id, "❌ Session expired! Use /start again")
        return False
    
    data = temp_data[chat_id]
    client = data["client"]
    
    try:
        # Sign in
        await client.sign_in(data["phone"], code, phone_code_hash=data["phone_code_hash"])
        me = await client.get_me()
        
        global user_account, user_client, user_vc
        user_client = client
        user_account = {"name": me.first_name, "id": me.id, "username": me.username}
        
        # Initialize voice call
        factory = GroupCallFactory(client)
        user_vc = factory.get_group_call()
        
        # Send success messages
        send_message(chat_id, f"✅ Logged in as {me.first_name}!")
        await asyncio.sleep(0.5)
        send_message(chat_id, f"📎 Now send group username or invite link")
        
        # Cleanup
        del temp_data[chat_id]
        print(f"✅ Login successful for {me.first_name}")
        return True
        
    except SessionPasswordNeeded:
        temp_data[chat_id]["step"] = "waiting_2fa"
        send_message(chat_id, "🔐 2FA Required\n\nSend your password:")
        return False
    except PhoneCodeInvalid:
        send_message(chat_id, "❌ Invalid OTP! Try again:")
        return False
    except Exception as e:
        error_msg = str(e)[:100]
        send_message(chat_id, f"❌ Error: {error_msg}")
        print(f"OTP Error: {e}")
        return False

async def verify_2fa(chat_id, password):
    if chat_id not in temp_data:
        send_message(chat_id, "❌ Session expired!")
        return False
    
    data = temp_data[chat_id]
    client = data["client"]
    
    try:
        await client.check_password(password)
        me = await client.get_me()
        
        global user_account, user_client, user_vc
        user_client = client
        user_account = {"name": me.first_name, "id": me.id, "username": me.username}
        
        factory = GroupCallFactory(client)
        user_vc = factory.get_group_call()
        
        send_message(chat_id, f"✅ Logged in as {me.first_name}!")
        send_message(chat_id, f"📎 Now send group username or invite link")
        
        del temp_data[chat_id]
        return True
    except Exception as e:
        send_message(chat_id, f"❌ Wrong password! Try again:")
        return False

async def join_and_play(chat_id, group_input, audio_path):
    global user_vc, current_group, user_account
    
    if not user_vc:
        send_message(chat_id, "❌ Not logged in!")
        return False
    
    try:
        # Get group chat ID
        if group_input.startswith("@"):
            username = group_input[1:]
            resp = requests.get(f"{API_URL}/getChat", params={"chat_id": f"@{username}"}, timeout=10)
            if resp.ok:
                chat_info = resp.json()["result"]
                group_id = chat_info["id"]
                group_name = chat_info.get("title", username)
            else:
                send_message(chat_id, f"❌ Cannot find group @{username}")
                return False
        elif "t.me/" in group_input:
            send_message(chat_id, "❌ Please use @username format")
            return False
        else:
            send_message(chat_id, "❌ Send @groupusername format")
            return False
        
        current_group = {"name": group_name, "chat_id": group_id}
        
        # Join voice chat
        send_message(chat_id, f"🔊 Joining {group_name}...")
        await user_vc.join(group_id)
        await asyncio.sleep(2)
        
        # Play audio
        send_message(chat_id, f"🎵 Playing audio...")
        await user_vc.start_audio(audio_path)
        
        send_message(chat_id, f"✅ Now playing in {group_name}!\nUse /stop to stop")
        return True
        
    except Exception as e:
        send_message(chat_id, f"❌ Error: {str(e)[:100]}")
        return False

async def stop_audio(chat_id):
    global user_vc
    if user_vc:
        try:
            await user_vc.stop_audio()
            send_message(chat_id, "✅ Stopped!")
        except Exception as e:
            send_message(chat_id, f"❌ Error: {e}")

async def logout_user(chat_id):
    global user_client, user_account, user_vc, current_group
    
    if user_vc:
        try:
            await user_vc.leave()
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
    current_group = None
    
    send_message(chat_id, "✅ Logged out!")

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
                
                # Handle callback queries
                if "callback_query" in update:
                    callback = update["callback_query"]
                    user_id = callback["from"]["id"]
                    chat_id = callback["message"]["chat"]["id"]
                    data_cb = callback["data"]
                    
                    if not is_sudo(user_id):
                        send_message(chat_id, "❌ Access Denied!")
                        continue
                    
                    if data_cb == "login_account":
                        send_message(chat_id, "📱 Send phone number with country code:\nExample: +919876543210")
                        user_states[chat_id] = {"step": "waiting_phone"}
                    elif data_cb == "play_audio":
                        if not user_account:
                            send_message(chat_id, "❌ Login first using /start")
                        else:
                            send_message(chat_id, "🎵 Send audio file or voice message")
                            user_states[chat_id] = {"step": "waiting_audio"}
                    elif data_cb == "logout":
                        await logout_user(chat_id)
                    
                    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback["id"]})
                
                # Handle messages
                elif "message" in update:
                    msg = update["message"]
                    user_id = msg["from"]["id"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    audio = msg.get("audio")
                    voice = msg.get("voice")
                    
                    if not is_sudo(user_id):
                        continue
                    
                    print(f"\n📨 {text if text else '[File]'}")
                    
                    # Step 1: Waiting for phone
                    if chat_id in user_states and user_states[chat_id].get("step") == "waiting_phone":
                        if text.startswith("+"):
                            await login_user(text, chat_id)
                            del user_states[chat_id]
                        else:
                            send_message(chat_id, "❌ Send phone with + code")
                    
                    # Step 2: Waiting for OTP
                    elif chat_id in temp_data and temp_data[chat_id].get("step") == "waiting_otp":
                        code = ''.join(filter(str.isdigit, text))
                        if code:
                            await verify_otp(chat_id, code)
                        else:
                            send_message(chat_id, "❌ Send numbers only")
                    
                    # Step 3: Waiting for 2FA
                    elif chat_id in temp_data and temp_data[chat_id].get("step") == "waiting_2fa":
                        await verify_2fa(chat_id, text)
                    
                    # Step 4: Waiting for group
                    elif chat_id in user_states and user_states[chat_id].get("step") == "waiting_group":
                        if text.startswith("@"):
                            user_states[chat_id]["group"] = text
                            user_states[chat_id]["step"] = "waiting_audio"
                            send_message(chat_id, "✅ Group saved!\n\nNow send audio file or voice message")
                        else:
                            send_message(chat_id, "❌ Send @username")
                    
                    # Step 5: Waiting for audio file
                    elif chat_id in user_states and user_states[chat_id].get("step") == "waiting_audio":
                        if audio or voice:
                            send_message(chat_id, "📥 Downloading...")
                            os.makedirs("audio", exist_ok=True)
                            file_path = await msg.download("audio/")
                            
                            # Get group from state or use current_group
                            group = user_states[chat_id].get("group") or (current_group.get("username") if current_group else None)
                            
                            if group:
                                await join_and_play(chat_id, group, file_path)
                                del user_states[chat_id]
                            else:
                                send_message(chat_id, "❌ Send group username first")
                        else:
                            send_message(chat_id, "❌ Send audio file or voice message")
                    
                    # Commands
                    elif text == "/start":
                        if user_account:
                            kb = {"inline_keyboard": [
                                [{"text": "🎵 Play Audio", "callback_data": "play_audio"}],
                                [{"text": "🚪 Logout", "callback_data": "logout"}]
                            ]}
                            send_message(chat_id, f"Welcome back {user_account['name']}!", kb)
                        else:
                            kb = {"inline_keyboard": [[{"text": "📱 Login", "callback_data": "login_account"}]]}
                            send_message(chat_id, "🎵 Welcome!\nClick Login to start", kb)
                    
                    elif text == "/stop":
                        await stop_audio(chat_id)
                    
                    elif text == "/logout":
                        await logout_user(chat_id)
                    
                    # If logged in and no state, ask for group
                    elif user_account and chat_id not in user_states:
                        if text.startswith("@"):
                            user_states[chat_id] = {"step": "waiting_audio", "group": text}
                            send_message(chat_id, "✅ Group saved!\nNow send audio file")
                        elif text and not text.startswith("/"):
                            send_message(chat_id, "Send @groupusername first")
            
            time.sleep(1)
        except Exception as e:
            print(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
