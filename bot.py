import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler, filters

# Configurazioni
BOT_TOKEN = "6988160636:AAEDg6wo4kpeHkP7JOLJ0ds7DYOznEd8b7o"
PROHIBITED_PATTERNS = [r"\+?\d{10,}", r"(porn|gore|badword1|badword2)"]

# Database locale simulato
users_db = {}
groups_config = {}

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Funzioni di utilità
def is_admin(update: Update, user_id: int) -> bool:
    """Controlla se un utente è amministratore nel gruppo."""
    admins = update.effective_chat.get_administrators()
    return any(admin.user.id == user_id for admin in admins)

def warn_user(update: Update, context: CallbackContext, user_id: int, reason: str):
    """Aggiungi warn all'utente e gestisci eventuali sanzioni."""
    chat_id = update.effective_chat.id
    username = update.message.from_user.username or "Utente sconosciuto"

    if user_id not in users_db:
        users_db[user_id] = {"username": username, "warns": 0, "muted": False, "blacklisted": False}

    user_data = users_db[user_id]
    if user_data["blacklisted"]:
        return  # Utente già blacklistato

    user_data["warns"] += 1
    warns = user_data["warns"]

    if warns >= 5:
        # Muta l'utente
        context.bot.restrict_chat_member(chat_id, user_id, permissions=None)
        user_data["muted"] = True
        update.message.reply_text(f"⚠️ {username} è stato mutato per aver raggiunto 5 warn!")
    else:
        update.message.reply_text(f"⚠️ Warn per {username}: {warns}/5. Motivo: {reason}")

def blacklist_user(update: Update, context: CallbackContext, user_id: int):
    """Blacklist l'utente e bannalo dal gruppo."""
    chat_id = update.effective_chat.id
    username = update.message.from_user.username or "Utente sconosciuto"

    users_db[user_id]["blacklisted"] = True
    context.bot.kick_chat_member(chat_id, user_id)
    update.message.reply_text(f"❌ {username} è stato blacklistato e bannato per contenuti vietati.")

# Gestione messaggi
def analyze_message(update: Update, context: CallbackContext):
    """Analizza i messaggi di testo e immagini."""
    user_id = update.message.from_user.id
    chat_id = update.effective_chat.id
    text = update.message.text
    username = update.message.from_user.username or "Utente sconosciuto"

    # Salta i messaggi degli admin
    if is_admin(update, user_id):
        return

    # Controllo testo
    if text:
        for pattern in PROHIBITED_PATTERNS:
            if re.search(pattern, text.lower()):
                warn_user(update, context, user_id, "Testo inappropriato")
                return

    # Controllo immagini
    if update.message.photo:
        update.message.reply_text(f"⚠️ {username}, la tua immagine è in fase di verifica.")
        # Simulazione di analisi immagini
        image_file_id = update.message.photo[-1].file_id
        file = context.bot.get_file(image_file_id)
        file.download("temp_image.jpg")
        
        # Esempio di logica per immagini vietate (semplificata)
        if is_suspicious_image("temp_image.jpg"):
            blacklist_user(update, context, user_id)

def is_suspicious_image(image_path):
    """Simula il rilevamento di un'immagine sospetta."""
    # Placeholder per analisi automatica
    # In futuro, potresti aggiungere modelli locali di rilevamento.
    # Ad esempio: controllare dimensioni, colore dominante o altre metriche.
    return False  # Cambia con logica reale se necessaria

# Comando /start
def start(update: Update, context: CallbackContext):
    """Messaggio iniziale."""
    update.message.reply_text("🤖 Ciao! Sono il bot di moderazione. Solo gli amministratori possono configurarmi.")

# Pannello impostazioni
def settings(update: Update, context: CallbackContext):
    """Pannello di controllo per gli amministratori."""
    if not is_admin(update, update.message.from_user.id):
        update.message.reply_text("⚠️ Solo gli amministratori possono accedere al pannello di controllo.")
        return

    keyboard = [
        [InlineKeyboardButton("Visualizza Warn/Blacklist", callback_data="view_users")],
        [InlineKeyboardButton("Reset Warn", callback_data="reset_warn")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("⚙️ Pannello di controllo:", reply_markup=reply_markup)

def button_callback(update: Update, context: CallbackContext):
    """Gestisce i bottoni del pannello."""
    query = update.callback_query
    query.answer()

    if query.data == "view_users":
        users_list = "\n".join([f"User: {data['username']} - Warns: {data['warns']}" for user_id, data in users_db.items()])
        query.edit_message_text(f"👥 Utenti:\n{users_list}")

    elif query.data == "reset_warn":
        for user in users_db.values():
            user["warns"] = 0
        query.edit_message_text("✅ Warn resettati per tutti gli utenti!")

# Main
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Comandi
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("settings", settings))

    # Messaggi
    dispatcher.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, analyze_message))

    # Callback
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    # Avvia il bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
