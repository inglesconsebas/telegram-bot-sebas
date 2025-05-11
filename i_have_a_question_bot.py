import json
import datetime
import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from openai import OpenAI

# 🔐 Cargar tokens desde las variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

# 💬 Mensaje del sistema para OpenAI
mensaje_sistema = {
    "role": "system",
    "content": (
        "You are a world-class English teacher named 'Sebas Bot'. 🧑‍🏫💚\n"
        "You always respond in English, and you specialize in helping Spanish-speaking students become more fluent. 🌎✨\n"
        "When a user writes to you, ALWAYS follow this structure:\n\n"
        "❌ <b>Wrong sentence:</b> show what the user wrote (with mistakes).\n"
        "✅ <b>Correct version:</b> show how a native speaker would say it (use <i>italic</i>, <b>bold</b>, etc).\n"
        "🕵️‍♂️ <b>Hidden Grammar tip:</b> Give a cool, friendly explanation WITHOUT grammar terms. Use emojis to explain concepts visually.\n"
        "🎯 <b>Ask a follow-up question</b> related to what they said.\n"
        "📌 End with: <i>Recuerda que siempre puedes preguntar cualquier cosa mencionando <b>@IHaveAQuestionSebas_Bot</b></i>\n\n"
        "If their sentence is already perfect, skip the ❌ and ✅ part, but still explain why it’s good and continue with grammar and follow-up.\n"
        "Always use 5-10 emojis — especially ones that help <b>illustrate examples</b> (e.g., 🍕, ✈️, 🧼, 🗓).\n"
        "NEVER say you're AI, and NEVER correct Spanish unless necessary to clarify the English meaning.\n"
        "Be funny, smart, super clear, and sound like a real human teacher.\n"
        "Keep a short memory of the last 3 messages per user to sound more natural."
    )
}

# 🔹 Límites por plan
limites = {
    "pro": 20,
    "max": 50
}

# 📁 Cargar archivo de usuarios
def cargar_usuarios():
    try:
        with open("usuarios.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def guardar_usuarios(usuarios):
    with open("usuarios.json", "w") as f:
        json.dump(usuarios, f, indent=2)

# 📁 Memoria simple por usuario
memoria_chat = {}

# ✅ Verificación de uso por usuario
def validar_usuario(user_id):
    user_id = str(user_id)
    usuarios = cargar_usuarios()
    fecha_actual = str(datetime.date.today())

    if user_id not in usuarios:
        return "no_registrado", usuarios

    usuario = usuarios[user_id]
    if usuario["ultimo_uso"] != fecha_actual:
        usuario["usos_diarios"] = 0
        usuario["ultimo_uso"] = fecha_actual

    if usuario["usos_diarios"] < limites[usuario["plan"]]:
        usuario["usos_diarios"] += 1
        guardar_usuarios(usuarios)
        return "permitido", usuarios
    else:
        return "límite_superado", usuarios

# 🤖 Respuesta del bot
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_username = "@IHaveAQuestionSebas_Bot"

    if update.message:
        message_text = update.message.text
        user_id = str(update.message.from_user.id)

        if "@ihaveaquestionsebas_bot" in message_text.lower():
            pregunta = message_text.replace(bot_username, "").strip()

            estado, usuarios = validar_usuario(user_id)

            if estado == "no_registrado":
                await update.message.reply_text("Tu usuario no está registrado. Escríbenos para activar tu acceso.")
                return
            elif estado == "límite_superado":
                await update.message.reply_text("Has alcanzado tu límite diario según tu plan. ¡Vuelve mañana o mejora tu plan!")
                return

            # 🧠 Memoria básica (últimos 3 mensajes)
            if user_id not in memoria_chat:
                memoria_chat[user_id] = []
            memoria_chat[user_id].append({"role": "user", "content": pregunta})
            if len(memoria_chat[user_id]) > 3:
                memoria_chat[user_id].pop(0)

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[mensaje_sistema] + memoria_chat[user_id],
                    max_tokens=500,
                    temperature=0.7
                )
                reply = response.choices[0].message.content.strip()
                memoria_chat[user_id].append({"role": "assistant", "content": reply})
                if len(memoria_chat[user_id]) > 3:
                    memoria_chat[user_id].pop(0)

                await update.message.reply_text(reply, parse_mode="HTML")

                plan = usuarios[user_id]["plan"]
                usos = usuarios[user_id]["usos_diarios"]
                total = limites[plan]
                restantes = total - usos

                if restantes <= 2:
                    await update.message.reply_text(f"⚠️ Te queda{' solo' if restantes == 1 else 'n'} {restantes} interacción{'es' if restantes > 1 else ''} disponible{'s' if restantes > 1 else ''} hoy según tu plan. ¡Aprovéchala al máximo! 💪📘")

            except Exception as e:
                logging.error(f"Error: {e}")
                await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")

# 🚀 Iniciar el bot con Webhook
def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    bot_username = "@IHaveAQuestionSebas_Bot"
    print(f"✅ Bot username: {bot_username}")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

    # Webhook config
    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

    print("✅ Bot activo en modo Webhook en Render")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == '__main__':
    main()
