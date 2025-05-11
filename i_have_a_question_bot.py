import json
import datetime
import logging
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from openai import OpenAI

# 🔐 Cargar tokens desde las variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=OPENAI_API_KEY)

# 💬 Mensaje del sistema para OpenAI con formato Markdown y emojis
mensaje_sistema = {
    "role": "system",
    "content": (
        "You are a friendly, funny, and highly skilled *English tutor* named 'Sebas Bot'. "
        "Your only job is to help people *improve their English skills*, no matter what language they use to ask.\n\n"
        "📌 IMPORTANT:\n"
        "- If users write in Spanish, it's because they want to learn or confirm something in **English**.\n"
        "- NEVER correct Spanish. You are not a Spanish teacher.\n"
        "- ALWAYS correct or explain things **in English**, with optional short Spanish support only if strictly needed.\n\n"
        "✅ FORMAT:\n"
        "You ALWAYS respond in *Markdown* format (for Telegram), using:\n"
        "- Bold **to highlight corrections, tips, and key phrases**\n"
        "- Emojis for structure: 🧠💡✅❌✨\n"
        "- Clear sections: ❌ Mistake, ✅ Correction, ✨ Tip, 📘 Fun Fact\n\n"
        "🧠 YOUR JOB:\n"
        "1️⃣ Detect the student’s level silently (basic/intermediate/advanced)\n"
        "2️⃣ Adapt your answer to be clear and natural for their level\n"
        "3️⃣ Correct their English kindly, using before/after style\n"
        "4️⃣ End with a short, high-level **tip** that teaches:\n"
        "    - A native-like way to say something\n"
        "    - A cultural or linguistic fun fact\n"
        "    - A smarter or more natural alternative\n\n"
        "✨ Tips must be short but super *pro*, like those from an expert private teacher. "
        "You may add one quick *Fun Fact* if it's interesting and relevant.\n\n"
        "Never say you're an AI. Never say 'as an AI model'. Always act like a top-level human English tutor named Sebas Bot. 😄"
    )
}

# 🔢 Límites por plan
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

# 🤖 Respuesta del bot
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot_username = "@IHaveAQuestionSebas_Bot"

    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mention = update.message.text[entity.offset:entity.offset + entity.length]
                if mention.lower() == bot_username.lower():
                    user_id = update.message.from_user.id
                    estado, usuarios = validar_usuario(user_id)

                    if estado == "no_registrado":
                        await update.message.reply_text("Tu usuario no está registrado. Escríbenos para activar tu acceso.")
                        return
                    elif estado == "límite_superado":
                        await update.message.reply_text("Has alcanzado tu límite diario según tu plan. ¡Vuelve mañana o mejora tu plan!")
                        return

                    plan = usuarios[str(user_id)]["plan"]
                    usos = usuarios[str(user_id)]["usos_diarios"]
                    total = limites[plan]
                    restantes = total - usos

                    pregunta = update.message.text.replace(mention, "").strip()

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
                            max_tokens=500,
                            temperature=0.7
                        )
                        reply = response.choices[0].message.content.strip()

                        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

                        if restantes <= 2:
                            await update.message.reply_text(
                                f"⚠️ Te queda{' solo' if restantes == 1 else 'n'} {restantes} interacción{'es' if restantes > 1 else ''} disponible{'s' if restantes > 1 else ''} hoy según tu plan. ¡Aprovéchala al máximo! 💪📘"
                            )

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
