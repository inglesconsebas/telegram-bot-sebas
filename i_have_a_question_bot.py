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
        "You always respond in English and specialize in helping Spanish-speaking students become fluent. 🇪🇸🇬🇧\n"
        "Every time a user writes to you, follow this structure:\n"
        "1️⃣ Detect and correct any mistakes using the format: \n"
        "   - Wrong: ❌ <s>incorrect sentence</s>\n"
        "   - Correct: ✅ <b>correct sentence</b>\n"
        "2️⃣ Provide a fun and simple tip using the Hidden Grammar method 🕵️‍♂️.\n"
        "3️⃣ React to the topic warmly and add emojis to illustrate ideas (5–10 per message).\n"
        "4️⃣ End with a follow-up question to keep the conversation going. 🎯\n"
        "5️⃣ If the student says something like 'can you explain in Spanish?', give the same explanation as before but in simple Spanish.\n"
        "Use <b>bold</b>, <i>italic</i>, <s>strikethrough</s>, and <spoiler>spoilers</spoiler> when needed.\n"
        "Be dynamic, fun, and creative — never say you're AI."
    )
}

# 🔹 Límites por plan
limites = {
    "pro": 20,
    "max": 50
}

# 🧠 Memoria de usuario (últimos 3 mensajes)
historial = {}

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
        pregunta = message_text.replace(bot_username, "").strip()

        if user_id not in historial:
            historial[user_id] = []

        # Verificar si pide traducción
        if "en español" in pregunta.lower():
            if historial[user_id]:
                ultima_respuesta = historial[user_id][-1]
                try:
                    traduccion = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "Eres un traductor profesional y profesor de inglés que explica a estudiantes hispanohablantes con claridad y amabilidad. Traduce y explica de forma sencilla el siguiente mensaje en español."},
                            {"role": "user", "content": ultima_respuesta }
                        ],
                        max_tokens=400,
                        temperature=0.6
                    )
                    explicacion = traduccion.choices[0].message.content.strip()
                    await update.message.reply_text(explicacion, parse_mode="HTML")
                except Exception as e:
                    logging.error(f"Error: {e}")
                    await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")
            else:
                await update.message.reply_text("No hay nada para traducir todavía. Hazme una pregunta primero.")
            return

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

        if not pregunta:
            await update.message.reply_text("Hey! Just type your question or say 'Let's practice!' and I’ll help you! 😊")
            return

        try:
            contexto = [
                {"role": "system", "content": mensaje_sistema["content"]},
            ] + [
                {"role": "user", "content": msg} for msg in historial[user_id][-3:]
            ] + [
                {"role": "user", "content": pregunta}
            ]

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=contexto,
                max_tokens=600,
                temperature=0.7
            )
            reply = response.choices[0].message.content.strip()
            historial[user_id].append(pregunta)
            historial[user_id].append(reply)

            await update.message.reply_text(reply, parse_mode="HTML")

            if restantes <= 2:
                await update.message.reply_text(f"⚠️ Te queda{' solo' if restantes == 1 else 'n'} {restantes} interacción{'es' if restantes > 1 else ''} disponible{'s' if restantes > 1 else ''} hoy según tu plan. ¡Aprovéchala al máximo! 💪📘")

        except Exception as e:
            logging.error(f"Error: {e}")
            await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")

# 🚀 Iniciar el bot con Webhook
def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    print("✅ Bot username: @IHaveAQuestionSebas_Bot")

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
