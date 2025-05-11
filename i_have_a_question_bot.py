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
        "You always respond in English, and you specialize in helping Spanish-speaking students become more fluent. 🇪🇸🗣️\n"
        "Every time a user writes to you, your mission is to:\n"
        "1️⃣ Detect and clearly show any errors with a ❌, followed by the incorrect phrase.\n"
        "2️⃣ Provide a corrected version with ✅, using <i>italic</i> and <b>bold</b> formatting in HTML.\n"
        "3️⃣ Add a 🕵️‍♂️ <b>Hidden Grammar Tip</b> — it must sound natural, short, and helpful (no boring grammar terms). Use emojis to illustrate.\n"
        "4️⃣ End with a <b>follow-up question</b> to continue the conversation and a <i>reminder in Spanish</i>:\n"
        "<i>“¿Tienes dudas? ¡Solo menciona <b>@IHaveAQuestionSebas_Bot</b> y estaré aquí para ayudarte!”</i>\n"
        "5️⃣ Always use between 5 to 10 emojis per message.\n"
        "6️⃣ Always act like a modern, cool, supportive teacher — never say you're an AI.\n"
        "7️⃣ Use HTML formatting like <b>bold</b>, <i>italic</i>, <s>strikethrough</s>, and <spoiler>spoilers</spoiler> when it makes sense.\n"
        "8️⃣ Always reply in English, unless the reminder at the end.\n"
        "9️⃣ You have memory of the last 3 messages from each user to maintain context."
    )
}

# 🔹 Límites por plan
limites = {
    "pro": 20,
    "max": 50
}

# 🧠 Memoria por usuario
memoria_usuarios = {}

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

            plan = usuarios[user_id]["plan"]
            usos = usuarios[user_id]["usos_diarios"]
            total = limites[plan]
            restantes = total - usos

            # Agregar memoria
            if user_id not in memoria_usuarios:
                memoria_usuarios[user_id] = []
            memoria = memoria_usuarios[user_id][-3:]  # Últimos 3 mensajes
            mensajes_contexto = [{"role": "user", "content": m} for m in memoria]
            memoria_usuarios[user_id].append(pregunta)

            if not pregunta:
                await update.message.reply_text("Hey! Just type your question or say 'Let's practice!' and I’ll help you! 😊")
                return

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": mensaje_sistema["content"]},
                        *mensajes_contexto,
                        {"role": "user", "content": pregunta}
                    ],
                    max_tokens=600,
                    temperature=0.8
                )
                reply = response.choices[0].message.content.strip()
                await update.message.reply_text(reply, parse_mode="HTML")

                if restantes <= 2:
                    await update.message.reply_text(f"⚠️ Te queda{' solo' if restantes == 1 else 'n'} {restantes} interacción{'es' if restantes > 1 else ''} disponible{'s' if restantes > 1 else ''} hoy según tu plan. ¡Aprovéchala al máximo! 💪📘")

            except Exception as e:
                logging.error(f"Error: {e}")
                await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")
                return

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
