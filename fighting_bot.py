import requests
import time
import json
import asyncio
import os
from pyrogram import Client
from pytgcalls import GroupCallFactory
from pytgcalls.types import AudioPiped
from config import API_ID, API_HASH, BOT_TOKEN, OWNER_ID

TOKEN = BOT_TOKEN
API_URL = f"https://api.telegram.org/bot{TOKEN}"

# Data storage
user_sessions = []
user_clients = {}
active_vc = {}
groups_list = []
current_group = None
current_vc = None
last_update_id = 0
user_states = {}

print("="*60)
print("🎵 VC RECORDING BOT")
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

async def test_session(session_string):
    try:
        client = Client("test_temp", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
        await client.start()
        me = await client.get_me()
        await client.stop()
        return {"success": True, "name": me.first_name, "id": me.id, "username": me.username}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def connect_and_play(client, chat_id, audio_path, group_name):
    """Connect to VC and play audio"""
    try:
        factory = GroupCallFactory(client)
        vc = factory.get_file_group_call()
        await vc.start(chat_id)
        await vc.play(AudioPiped(audio_path))
        return True, None
    except Exception as e:
        return False, str(e)

async def play_recording(chat_id, group_name, group_chat_id, session_index, audio_path):
    """Play recording using specific session"""
    results = []
    
    if session_index >= len(user_sessions):
        return [{"success": False, "error": "Session not found!"}]
    
    session_data = user_sessions[session_index]
    session_string = session_data["string"]
    acc_name = session_data["name"]
    
    try:
        # Create client if not exists
        if acc_name not in user_clients:
            print(f"  🔌 Creating client for {acc_name}...")
            client = Client(f"sessions/{acc_name}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
            await client.start()
            user_clients[acc_name] = client
            print(f"  ✅ Client created for {acc_name}")
        
        client = user_clients[acc_name]
        
        # Join VC and play audio
        success, error = await connect_and_play(client, group_chat_id, audio_path, group_name)
        
        if success:
            results.append({"success": True, "name": acc_name, "group": group_name})
            print(f"  ✅ {acc_name} playing in {group_name}")
        else:
            results.append({"success": False, "name": acc_name, "error": error[:50]})
            print(f"  ❌ {acc_name} failed: {error}")
            
    except Exception as e:
        results.append({"success": False, "name": acc_name, "error": str(e)[:50]})
        print(f"  ❌ {acc_name} error: {e}")
    
    return results

def show_all_sessions(chat_id):
    if not user_sessions:
        send_message(chat_id, "❌ No sessions added! Use /start to add sessions")
        return
    text = "**📱 Your Sessions:**\n\n"
    for i, s in enumerate(user_sessions, 1):
        status = "✅ Connected" if s['name'] in user_clients else "⭕ Not Connected"
        text += f"{i}. **{s['name']}**\n"
        text += f"   🆔 ID: `{s['id']}`\n"
        text += f"   📊 Status: {status}\n"
        text += f"   🔢 Index: `{i-1}`\n\n"
    send_message(chat_id, text)

def show_groups_list(chat_id):
    if not groups_list:
        send_message(chat_id, "❌ No groups added! Use /addgroup")
        return
    text = "**📋 Your Groups:**\n\n"
    for i, g in enumerate(groups_list, 1):
        text += f"{i}. **{g['name']}**\n"
        text += f"   🆔 Chat ID: `{g['chat_id']}`\n"
        if g.get('username'):
            text += f"   🔗 Username: @{g['username']}\n"
        text += f"   🔢 Index: `{i-1}`\n\n"
    send_message(chat_id, text)

async def main():
    global last_update_id, current_group, current_vc
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
                    
                    if user_id != OWNER_ID:
                        send_message(chat_id, "❌ Access Denied! Only bot owner can use this bot.")
                        requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback["id"]})
                        continue
                    
                    if data_cb == "connect":
                        user_states[user_id] = {"step": "awaiting_session"}
                        send_message(chat_id, "📱 **Send Pyrogram String Session**\n\nGet from @StringSessionBot\nType `/done` when finished")
                    
                    elif data_cb == "status":
                        status_text = f"**📊 Status**\n\n"
                        status_text += f"📱 Sessions: {len(user_sessions)}\n"
                        status_text += f"🔌 Connected: {len(user_clients)}\n"
                        status_text += f"📋 Groups: {len(groups_list)}\n\n"
                        if user_sessions:
                            status_text += "**Sessions:**\n"
                            for s in user_sessions:
                                status = "✅" if s['name'] in user_clients else "⭕"
                                status_text += f"{status} `{s['name']}`\n"
                        send_message(chat_id, status_text)
                    
                    elif data_cb == "public_group":
                        user_states[user_id] = {"step": "public_username"}
                        send_message(chat_id, "📝 Send group @username\nExample: `@mygroup`")
                    
                    elif data_cb == "private_group":
                        user_states[user_id] = {"step": "private_link"}
                        send_message(chat_id, "🔗 Send invite link")
                    
                    elif data_cb == "show_sessions":
                        show_all_sessions(chat_id)
                    
                    elif data_cb == "show_groups":
                        show_groups_list(chat_id)
                    
                    requests.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": callback["id"]})
                
                elif "message" in update:
                    msg = update["message"]
                    user_id = msg["from"]["id"]
                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    audio = msg.get("audio")
                    voice = msg.get("voice")
                    
                    print(f"\n📨 Message: {text if text else '[Audio/Voice]'}")
                    
                    if user_id != OWNER_ID:
                        continue
                    
                    # Regular commands
                    if text == "/start":
                        kb = {"inline_keyboard": [
                            [{"text": "🔌 Connect Session", "callback_data": "connect"}],
                            [{"text": "📊 Status", "callback_data": "status"}],
                            [{"text": "📱 My Sessions", "callback_data": "show_sessions"}],
                            [{"text": "➕ Add Group", "callback_data": "public_group"}],
                            [{"text": "📋 My Groups", "callback_data": "show_groups"}]
                        ]}
                        send_message(chat_id, "**🎵 VC Recording Bot**\n\n**How to use:**\n1. Add sessions using Connect Session\n2. Add groups using Add Group\n3. Send audio/voice to play\n\n**Commands:**\n/addgroup - Add group\n/sessions - All sessions\n/groups - All groups\n/done - Finish adding sessions", kb)
                    
                    elif text == "/addgroup":
                        kb = {"inline_keyboard": [
                            [{"text": "🌐 Public", "callback_data": "public_group"}],
                            [{"text": "🔒 Private", "callback_data": "private_group"}]
                        ]}
                        send_message(chat_id, "Select group type:", kb)
                    
                    elif text == "/add":
                        kb = {"inline_keyboard": [
                            [{"text": "🌐 Public", "callback_data": "public_group"}],
                            [{"text": "🔒 Private", "callback_data": "private_group"}]
                        ]}
                        send_message(chat_id, "Select group type:", kb)
                    
                    elif text == "/sessions":
                        show_all_sessions(chat_id)
                    
                    elif text == "/groups":
                        show_groups_list(chat_id)
                    
                    elif text == "/status":
                        status_text = f"**📊 Status**\n\n"
                        status_text += f"📱 Sessions: {len(user_sessions)}\n"
                        status_text += f"🔌 Connected: {len(user_clients)}\n"
                        status_text += f"📋 Groups: {len(groups_list)}"
                        send_message(chat_id, status_text)
                    
                    elif text == "/done":
                        send_message(chat_id, f"✅ Done! Total sessions: {len(user_sessions)}")
                        if user_id in user_states:
                            del user_states[user_id]
                    
                    # Handle session string input
                    elif user_id in user_states and user_states[user_id].get("step") == "awaiting_session":
                        if len(text) > 50:
                            send_message(chat_id, "⏳ Testing session...")
                            result = await test_session(text)
                            if result["success"]:
                                # Check if session already exists
                                exists = False
                                for s in user_sessions:
                                    if s["id"] == result["id"]:
                                        exists = True
                                        break
                                if exists:
                                    send_message(chat_id, f"⚠️ Session for {result['name']} already exists!")
                                else:
                                    user_sessions.append({
                                        "string": text,
                                        "name": result["name"],
                                        "id": result["id"],
                                        "username": result["username"]
                                    })
                                    send_message(chat_id, f"✅ **Session Added!**\n\n👤 {result['name']}\n🆔 `{result['id']}`\n📊 Total: {len(user_sessions)}\n\nSend more or type /done")
                            else:
                                send_message(chat_id, f"❌ Invalid session: {result['error']}")
                        else:
                            send_message(chat_id, "❌ Invalid session string!")
                    
                    # Handle public group username
                    elif user_id in user_states and user_states[user_id].get("step") == "public_username":
                        username = text.replace("@", "")
                        send_message(chat_id, f"⏳ Resolving @{username}...")
                        try:
                            resp = requests.get(f"{API_URL}/getChat", params={"chat_id": f"@{username}"}, timeout=10)
                            if resp.ok:
                                ci = resp.json()["result"]
                                gtitle = ci.get("title", username)
                                gcid = ci["id"]
                                groups_list.append({"name": gtitle, "chat_id": gcid, "username": username})
                                send_message(chat_id, f"✅ **Group Added!**\n\n📌 {gtitle}\n🆔 `{gcid}`\n\nNow send audio/voice to play!")
                            else:
                                send_message(chat_id, f"❌ Could not resolve @{username}")
                        except Exception as e:
                            send_message(chat_id, f"❌ Error: {e}")
                        del user_states[user_id]
                    
                    # Handle private group link
                    elif user_id in user_states and user_states[user_id].get("step") == "private_link":
                        user_states[user_id] = {"step": "private_chatid", "link": text}
                        send_message(chat_id, "Send Chat ID (example: -1001234567890)")
                    
                    # Handle private group chat_id
                    elif user_id in user_states and user_states[user_id].get("step") == "private_chatid":
                        try:
                            cid = int(text)
                            groups_list.append({"name": f"Private_{cid}", "chat_id": cid, "invite_link": user_states[user_id]["link"]})
                            send_message(chat_id, f"✅ **Private Group Added!**\n\n🆔 `{cid}`\n\nNow send audio/voice to play!")
                            del user_states[user_id]
                        except:
                            send_message(chat_id, "Invalid Chat ID!")
                    
                    # Handle audio for playing
                    elif audio or voice:
                        if len(user_sessions) == 0:
                            send_message(chat_id, "❌ No sessions added! Use /start first")
                            continue
                        if len(groups_list) == 0:
                            send_message(chat_id, "❌ No groups added! Use /addgroup first")
                            continue
                        
                        # Ask which session and group to use
                        sessions_text = ""
                        for i, s in enumerate(user_sessions):
                            sessions_text += f"{i}. {s['name']}\n"
                        
                        groups_text = ""
                        for i, g in enumerate(groups_list):
                            groups_text += f"{i}. {g['name']}\n"
                        
                        kb = {"inline_keyboard": []}
                        for i in range(min(len(user_sessions), 5)):
                            kb["inline_keyboard"].append([{"text": f"Session {i}: {user_sessions[i]['name'][:20]}", "callback_data": f"select_session_{i}"}])
                        
                        send_message(chat_id, f"**🎵 Select Session to Play**\n\nAvailable Sessions:\n{sessions_text}\n\nClick on a session to continue, then select group.")
                        
                        # Store audio info temporarily
                        if audio:
                            user_states[user_id] = {"step": "waiting_session_select", "audio_type": "audio", "msg_id": msg["message_id"]}
                        else:
                            user_states[user_id] = {"step": "waiting_session_select", "audio_type": "voice", "msg_id": msg["message_id"]}
                    
                    # Handle session selection via callback
                    elif text and text.startswith("/play") and len(user_sessions) > 0 and len(groups_list) > 0:
                        parts = text.split()
                        if len(parts) == 3:
                            try:
                                session_idx = int(parts[1])
                                group_idx = int(parts[2])
                                
                                if session_idx < len(user_sessions) and group_idx < len(groups_list):
                                    send_message(chat_id, f"🎵 **Send audio file or voice message**\n\nSelected Session: {user_sessions[session_idx]['name']}\nSelected Group: {groups_list[group_idx]['name']}")
                                    user_states[user_id] = {"step": "waiting_audio_for_play", "session_idx": session_idx, "group_idx": group_idx}
                                else:
                                    send_message(chat_id, "❌ Invalid session or group index!")
                            except:
                                send_message(chat_id, "Usage: /play <session_index> <group_index>\nExample: /play 0 0")
                        else:
                            send_message(chat_id, f"Usage: /play <session_index> <group_index>\n\nSessions:\n{sessions_text}\nGroups:\n{groups_text}")
                    
                    # Handle direct audio after selection
                    elif user_id in user_states and user_states[user_id].get("step") == "waiting_audio_for_play":
                        if audio or voice:
                            session_idx = user_states[user_id]["session_idx"]
                            group_idx = user_states[user_id]["group_idx"]
                            
                            session_data = user_sessions[session_idx]
                            group_data = groups_list[group_idx]
                            
                            os.makedirs("audio", exist_ok=True)
                            
                            send_message(chat_id, f"📥 Downloading audio...\n\nSession: {session_data['name']}\nGroup: {group_data['name']}")
                            
                            if audio:
                                audio_path = await msg.download("audio/")
                            else:
                                audio_path = await msg.download("audio/")
                            
                            results = await play_recording(chat_id, group_data["name"], group_data["chat_id"], session_idx, audio_path)
                            
                            for r in results:
                                if r["success"]:
                                    send_message(chat_id, f"✅ **Playing!**\n\n🎵 Account: {r['name']}\n📻 Group: {r['group']}\n🎤 Recording playing in voice chat!")
                                else:
                                    send_message(chat_id, f"❌ Failed: {r['error']}")
                            
                            del user_states[user_id]
                        else:
                            send_message(chat_id, "❌ Please send an audio file or voice message!")
        
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
