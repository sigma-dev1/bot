import requests
import logging
import socket
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
import config
import asyncio

# Configurazione del logging
logging.basicConfig(level=logging.INFO)

bot = Client(
    "group_guardian",
    bot_token=config.BOT_TOKEN,
    api_id=config.API_ID,
    api_hash=config.API_HASH
)

# Memorizza chi ha aggiunto il bot e le configurazioni per ogni gruppo
GROUP_SETTINGS = {}
GROUP_IP_MEMORY = {}
GROUP_UNBANNED_USERS = {}
GROUP_TASKS = {}
GROUP_MESSAGES = {}
GROUP_ADMINS = {}  # Memorizza gli amministratori per ogni gruppo
GROUP_ADDED_BY = {}  # Memorizza chi ha aggiunto il bot a ogni gruppo

EUROPE_COUNTRY_CODES = ['AL', 'AD', 'AM', 'AT', 'AZ', 'BY', 'BE', 'BA', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'GE', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT', 'KZ', 'XK', 'LV', 'LI', 'LT', 'LU', 'MT', 'MD', 'MC', 'ME', 'NL', 'MK', 'NO', 'PL', 'PT', 'RO', 'SM', 'RS', 'SK', 'SI', 'ES', 'SE', 'CH', 'TR', 'UA', 'GB', 'VA']


# Funzioni di utilità
def initialize_group(group_id):
    """Inizializza i dati del gruppo se non esistono."""
    if group_id not in GROUP_SETTINGS:
        GROUP_SETTINGS[group_id] = {
            "VERIFICATION_ENABLED": True,  # Verifica all'ingresso attiva
        }
        GROUP_IP_MEMORY[group_id] = {}
        GROUP_UNBANNED_USERS[group_id] = set()
        GROUP_TASKS[group_id] = {}
        GROUP_MESSAGES[group_id] = []

def is_duplicate_ip(group_id, ip_address):
    return [user_id for user_id, ip in GROUP_IP_MEMORY[group_id].items() if ip == ip_address]

async def ban_user(client, chat_id, user_ids, reason):
    for user_id in user_ids:
        await client.ban_chat_member(chat_id, user_id)
    unban_button = InlineKeyboardButton(text="🔓 Sblocca Utenti", callback_data=f"unban_{'_'.join(map(str, user_ids))}")
    unban_keyboard = InlineKeyboardMarkup([[unban_button]])
    ban_message = await client.send_message(chat_id, reason, reply_markup=unban_keyboard)
    GROUP_MESSAGES[chat_id].append(ban_message.id)

async def unban_users(client, chat_id, user_ids):
    for user_id in user_ids:
        await client.unban_chat_member(chat_id, user_id)
        if user_id not in GROUP_UNBANNED_USERS[chat_id]:
            await client.send_message(chat_id, f"L'utente con ID {user_id} è stato sbloccato e non dovrà ripetere la verifica.")
        GROUP_UNBANNED_USERS[chat_id].add(user_id)

# Gestione dell'entrata del bot nel gruppo
@bot.on_chat_member_updated
async def on_bot_added_to_group(client, message):
    if message.new_chat_member.is_bot and message.new_chat_member.user.id == bot.me.id:
        group_id = message.chat.id
        user_id = message.from_user.id

        # Memorizza chi ha aggiunto il bot
        GROUP_ADDED_BY[group_id] = user_id
        GROUP_ADMINS[group_id] = {user_id}  # Solo chi ha aggiunto il bot è amministratore iniziale
        initialize_group(group_id)
        await client.send_message(group_id, "Il bot è stato aggiunto al gruppo. Solo l'amministratore che ha aggiunto il bot può configurarlo.")

# Comandi per abilitare/disabilitare la verifica
@bot.on_message(filters.command("enable_verification") & filters.group)
async def enable_verification(client, message):
    group_id = message.chat.id
    initialize_group(group_id)

    if message.from_user.id not in GROUP_ADMINS[group_id]:
        await message.reply("Non hai i permessi per eseguire questo comando.")
        return

    GROUP_SETTINGS[group_id]["VERIFICATION_ENABLED"] = True
    await message.reply("La verifica all'ingresso è stata abilitata.")

@bot.on_message(filters.command("disable_verification") & filters.group)
async def disable_verification(client, message):
    group_id = message.chat.id
    initialize_group(group_id)

    if message.from_user.id not in GROUP_ADMINS[group_id]:
        await message.reply("Non hai i permessi per eseguire questo comando.")
        return

    GROUP_SETTINGS[group_id]["VERIFICATION_ENABLED"] = False
    await message.reply("La verifica all'ingresso è stata disabilitata.")

# Aggiungi un nuovo amministratore
@bot.on_message(filters.command("add_admin") & filters.group)
async def add_admin(client, message):
    group_id = message.chat.id
    initialize_group(group_id)

    if message.from_user.id != GROUP_ADDED_BY[group_id]:
        await message.reply("Solo l'amministratore che ha aggiunto il bot può eseguire questo comando.")
        return

    if not message.reply_to_message:
        await message.reply("Rispondi a un messaggio dell'utente da autorizzare.")
        return

    user_id = message.reply_to_message.from_user.id
    GROUP_ADMINS[group_id].add(user_id)
    await message.reply(f"L'utente con ID {user_id} è stato aggiunto come amministratore.")

# Rimuovi un amministratore
@bot.on_message(filters.command("remove_admin") & filters.group)
async def remove_admin(client, message):
    group_id = message.chat.id
    initialize_group(group_id)

    if message.from_user.id != GROUP_ADDED_BY[group_id]:
        await message.reply("Solo l'amministratore che ha aggiunto il bot può eseguire questo comando.")
        return

    if not message.reply_to_message:
        await message.reply("Rispondi a un messaggio dell'utente da rimuovere come amministratore.")
        return

    user_id = message.reply_to_message.from_user.id
    if user_id == GROUP_ADDED_BY[group_id]:
        await message.reply("Non puoi rimuovere chi ha aggiunto il bot.")
        return

    GROUP_ADMINS[group_id].discard(user_id)
    await message.reply(f"L'utente con ID {user_id} è stato rimosso come amministratore.")

# Gestione dei nuovi membri
@bot.on_message(filters.new_chat_members)
async def welcome_and_mute(client, message):
    group_id = message.chat.id
    initialize_group(group_id)

    if not GROUP_SETTINGS[group_id]["VERIFICATION_ENABLED"]:
        return  # Verifica disabilitata

    for new_member in message.new_chat_members:
        if new_member.id in GROUP_UNBANNED_USERS[group_id]:
            continue

        logging.info("Nuovo membro: %s", new_member.id)
        await client.restrict_chat_member(
            group_id,
            new_member.id,
            ChatPermissions(can_send_messages=False)
        )

        verification_link = f"https://t.me/{client.me.username}?start=verifica_{new_member.id}"
        button = InlineKeyboardButton(text="✅ Verifica", url=verification_link)
        keyboard = InlineKeyboardMarkup([[button]])
        welcome_message = await message.reply_text(
            f"Benvenuto {new_member.first_name or new_member.username}! Completa la verifica cliccando il bottone qui sotto.",
            reply_markup=keyboard
        )
        GROUP_MESSAGES[group_id].append(welcome_message.id)

        task = asyncio.create_task(timer(client, group_id, new_member.id, welcome_message.id))
        GROUP_TASKS[group_id][new_member.id] = task

async def timer(client, group_id, user_id, message_id):
    await asyncio.sleep(180)
    if user_id not in GROUP_IP_MEMORY[group_id] and user_id not in GROUP_UNBANNED_USERS[group_id]:
        await ban_user(client, group_id, [user_id], f"L'utente {user_id} non ha passato la verifica ed è stato bannato.")
        await client.delete_messages(group_id, [message_id])
        GROUP_MESSAGES[group_id].remove(message_id)

# Avvia il bot
bot.run()
