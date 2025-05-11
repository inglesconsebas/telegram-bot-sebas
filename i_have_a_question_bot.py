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
        "You always respond in English, and you specialize in helping Spanish-speaking students become more fluent. 🇪🇸✨ "
        "Your job is to: \n"
        "1️⃣ Detect and highlight any errors in what the student wrote using ❌. Show the incorrect version with <s>strikethrough</s>.\n"
        "2️⃣ Provide a natural correction using ✅ and <b>bold</b> formatting.\n"
        "3️⃣ Offer a <i>Hidden Grammar tip</i> 🕵️‍♂️ that is casual, modern, and very easy to understand (no technical terms).\n"
        "4️⃣ Use 5-10 emojis that help illustrate and make it more fun and visual (e.g., 🧼 for soap, 🍲 for soup).\n"
        "5️⃣ Always include a follow-up question to encourage conversation.\n"
        "6️⃣ End every answer with: <i>Recuerda que siempre puedes preguntar cualquier cosa mencionando <b>@IHaveAQuestionSebas_Bot</b> 💬</i>\n"
        "7️⃣ If the student asks to explain in Spanish, provide the previous explanation in Spanish, keeping emojis and format.\n"
        "You must always answer in English unless the student explicitly asks for an explanation in Spanish.\n"
        "You're warm, funny, visual, and act like a real human. Be helpful, specific, and sound like the best English teacher ever."
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

# 🧠 Memoria de usuario
memoria = {}

# 🤖 Respuesta del bot
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_username = "@IHaveAQuestionSebas_Bot"

    if update.message:
        message_text = update.message.text
        user_id = update.message.from_user.id
        user_str = str(user_id)

        if user_str not in memoria:
            memoria[user_str] = []

        # Verificar si pidió explicación en español
        if any(phrase in message_text.lower() for phrase in ["en español", "in spanish", "explícalo en español"]):
            if len(memoria[user_str]) == 0:
                await update.message.reply_text("No tengo contexto previo para explicar. Escríbeme algo primero 😊")
                return

            ultimo_mensaje = memoria[user_str][-1]

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Traduce y explica en español este mensaje, pero manteniendo emojis, estructura, y el estilo educativo y amigable de un buen profesor de inglés."},
                        {"role": "user", "content": ultimo_mensaje}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )
                reply = response.choices[0].message.content.strip()
                await update.message.reply_text(reply, parse_mode="HTML")
                return

            except Exception as e:
                logging.error(f"Error: {e}")
                await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")
                return

        if bot_username.lower() in message_text.lower():
            pregunta = message_text.replace(bot_username, "").strip()

            estado, usuarios = validar_usuario(user_id)

            if estado == "no_registrado":
                await update.message.reply_text("Tu usuario no está registrado. Escríbenos para activar tu acceso.")
                return
            elif estado == "límite_superado":
                await update.message.reply_text("Has alcanzado tu límite diario según tu plan. ¡Vuelve mañana o mejora tu plan!")
                return

            plan = usuarios[user_str]["plan"]
            usos = usuarios[user_str]["usos_diarios"]
            total = limites[plan]
            restantes = total - usos

            if not pregunta:
                await update.message.reply_text("Hey! Just type your question or say 'Let's practice!' and I’ll help you! 😊")
                return

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": mensaje_sistema["content"]},
                        {"role": "user", "content": pregunta}
                    ],
                    max_tokens=800,
                    temperature=0.7
                )
                reply = response.choices[0].message.content.strip()
                memoria[user_str].append(reply)
                if len(memoria[user_str]) > 3:
                    memoria[user_str].pop(0)

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
