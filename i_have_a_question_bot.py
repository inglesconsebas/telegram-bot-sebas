import json
import datetime
import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

mensaje_sistema = {
    "role": "system",
    "content": (
        "You are a world-class English teacher named 'Sebas Bot'. 🧑‍🏫💚 "
        "You always respond in English and specialize in helping Spanish-speaking students become fluent. "
        "Your job is to:\n"
        "1️⃣ Detect errors in the student’s sentence and respond like this:\n"
        "❌ Wrong: <s>what the user said with errors</s>\n"
        "✅ Correct: <b>the natural and corrected version</b>\n"
        "2️⃣ Provide a super friendly <b>Hidden Grammar tip 🕵️‍♂️</b> without technical grammar words. Be fun, clear and modern.\n"
        "3️⃣ Add related emojis to your examples — use 5 to 10 per response.\n"
        "4️⃣ Always ask a follow-up question to continue the conversation.\n"
        "5️⃣ Finish your response with this message in Spanish:\n"
        "Recuerda que siempre puedes preguntar cualquier cosa mencionando <b>@IHaveAQuestionSebas_Bot</b>\n"
        "Be expressive, funny, visual, dynamic. NEVER say you're an AI. You're a chill, wise, and super cool teacher!"
    )
}

# Límites por plan
limites = {
    "pro": 20,
    "max": 50
}

# Memoria por usuario
def cargar_usuarios():
    try:
        with open("usuarios.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def guardar_usuarios(usuarios):
    with open("usuarios.json", "w") as f:
        json.dump(usuarios, f, indent=2)

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
        usuario["memoria"] = []

    if usuario["usos_diarios"] < limites[usuario["plan"]]:
        usuario["usos_diarios"] += 1
        guardar_usuarios(usuarios)
        return "permitido", usuarios
    else:
        return "límite_superado", usuarios

# Generar prompt con memoria
def construir_prompt(pregunta, memoria):
    mensajes = [{"role": "system", "content": mensaje_sistema["content"]}]
    for entrada in memoria[-3:]:
        mensajes.append({"role": "user", "content": entrada["pregunta"]})
        mensajes.append({"role": "assistant", "content": entrada["respuesta"]})
    mensajes.append({"role": "user", "content": pregunta})
    return mensajes

# Bot
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

            memoria = usuarios[str(user_id)].get("memoria", [])

            if not pregunta:
                await update.message.reply_text("Hey! Just type your question or say 'Let's practice!' and I’ll help you! 😊")
                return

            try:
                mensajes = construir_prompt(pregunta, memoria)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=mensajes,
                    max_tokens=700,
                    temperature=0.7
                )
                reply = response.choices[0].message.content.strip()

                await update.message.reply_text(reply, parse_mode="HTML")

                memoria.append({"pregunta": pregunta, "respuesta": reply})
                usuarios[str(user_id)]["memoria"] = memoria[-3:]
                guardar_usuarios(usuarios)

                restantes = limites[usuarios[str(user_id)]["plan"]] - usuarios[str(user_id)]["usos_diarios"]
                if restantes <= 2:
                    await update.message.reply_text(
                        f"⚠️ Te queda{' solo' if restantes == 1 else 'n'} {restantes} interacción{'es' if restantes > 1 else ''} disponible{'s' if restantes > 1 else ''} hoy según tu plan. ¡Aprovéchala al máximo! 💪📘"
                    )

            except Exception as e:
                logging.error(f"Error: {e}")
                await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")
                return

# Webhook
def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    print(f"✅ Bot username: @IHaveAQuestionSebas_Bot")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))

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
