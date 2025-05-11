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
        "You are a world-class English teacher named 'Sebas Bot'. 🧑‍🏫💚 "
        "You always respond in English, and you specialize in helping Spanish-speaking students become more fluent. 🇪🇸"
        "Every time a user writes to you, your mission is to: \n"
        "1️⃣ Show them <b>how a native speaker would naturally say</b> what they asked.\n"
        "2️⃣ Correct mistakes clearly: show what's wrong with ❌ and then what’s right with ✅.\n"
        "3️⃣ Explain why the correction is better in a <i>simple, cool, friendly</i> way — no boring grammar rules.\n"
        "4️⃣ Use formatting like <b>bold</b>, <i>italic</i>, <s>strikethrough</s>, and <spoiler>spoilers</spoiler> to teach clearly.\n"
        "5️⃣ Use 4-5 emojis per message to make your answer visually engaging.\n"
        "6️⃣ End with a follow-up question to keep the conversation going.\n"
        "7️⃣ Remind students they can mention <b>@IHaveAQuestionSebas_Bot</b> anytime they need help.\n"
        "Be fun, chill, sharp, and positive. Never say you are an AI. Always respond like a top human teacher.\n"
        "Use your tone flexibly: be nerdy 🤓, chill 😎, sweet 😄, emotional 😭 — adapt to the message vibe."
    )
}

# 🔹 Límites por plan
limites = {
    "pro": 20,
    "max": 50
}

# 📁 Archivos de usuarios e historial
USUARIOS_PATH = "usuarios.json"
HISTORIAL_PATH = "historial_usuarios.json"

# 📁 Funciones de usuarios

def cargar_usuarios():
    try:
        with open(USUARIOS_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def guardar_usuarios(usuarios):
    with open(USUARIOS_PATH, "w") as f:
        json.dump(usuarios, f, indent=2)

# 📁 Funciones de historial

def cargar_historial():
    try:
        with open(HISTORIAL_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def guardar_historial(historial):
    with open(HISTORIAL_PATH, "w") as f:
        json.dump(historial, f, indent=2)

def actualizar_historial(user_id, pregunta):
    historial = cargar_historial()
    user_id = str(user_id)
    if user_id not in historial:
        historial[user_id] = []
    historial[user_id].append({"role": "user", "content": pregunta})
    historial[user_id] = historial[user_id][-6:]  # Guardar solo las 6 últimas interacciones
    guardar_historial(historial)
    return historial[user_id]

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
        user_id = update.message.from_user.id

        if "@ihaveaquestionsebas_bot" in message_text.lower():
            pregunta = message_text.replace(bot_username, "").strip()

            estado, usuarios = validar_usuario(user_id)
            if estado == "no_registrado":
                await update.message.reply_text("Tu usuario no está registrado. Escríbenos para activar tu acceso.")
                return
            elif estado == "límite_superado":
                await update.message.reply_text("Has alcanzado tu límite diario según tu plan. ¡Vuelve mañana o mejora tu plan!")
                return

            historial_usuario = actualizar_historial(user_id, pregunta)

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[mensaje_sistema] + historial_usuario,
                    max_tokens=600,
                    temperature=0.7
                )
                reply = response.choices[0].message.content.strip()
                await update.message.reply_text(reply, parse_mode="HTML")

                plan = usuarios[str(user_id)]["plan"]
                usos = usuarios[str(user_id)]["usos_diarios"]
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

    PORT = int(os.environ.get('PORT', 8443))
    WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

    print("✅ Bot activo en modo Webhook en Render")
    app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL)

if __name__ == '__main__':
    main()
