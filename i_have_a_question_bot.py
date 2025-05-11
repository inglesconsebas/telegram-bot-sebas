import json
import datetime
import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import openai

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai.api_key = OPENAI_API_KEY

mensaje_sistema = {
    "role": "system",
    "content": (
        "You are a friendly, helpful English tutor named 'Sebas Bot'. "
        "When a student asks a question, respond clearly using a natural, easy-to-understand tone. "
        "Correct mistakes kindly, give examples when correcting, and always include a tip to sound more natural in English. "
        "Use emojis to make responses friendly and fun. "
        "If the student wants to practice (e.g., says 'Let's practice', 'Can we chat?', or anything similar), "
        "start a simple, engaging conversation and correct them gently when they say something unnatural. "
        "Always be supportive and cheerful!"
    )
}

limites = {
    "lite": 5,
    "estandar": 10,
    "premium": 20,
    "super": 50
}

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

    if usuario["usos_diarios"] < limites[usuario["plan"]]:
        usuario["usos_diarios"] += 1
        guardar_usuarios(usuarios)
        return "permitido", usuarios
    else:
        return "límite_superado", usuarios

async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mention = update.message.text[entity.offset:entity.offset + entity.length]
                if mention.lower() == f"@{context.bot.username.lower()}":
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
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                mensaje_sistema,
                                {"role": "user", "content": pregunta}
                            ],
                            max_tokens=500,
                            temperature=0.7
                        )
                        reply = response.choices[0].message.content
                        await update.message.reply_text(reply)

                        if restantes <= 2:
                            await update.message.reply_text(f"⚠️ Te queda{' solo' if restantes == 1 else 'n'} {restantes} interacción{'es' if restantes > 1 else ''} disponible{'s' if restantes > 1 else ''} hoy según tu plan. ¡Aprovéchala al máximo! 💪📘")

                    except Exception as e:
                        logging.error(f"Error: {e}")
                        await update.message.reply_text("Oops! Algo salió mal. Intenta de nuevo en un momento.")
                        return

def main():
    logging.basicConfig(level=logging.INFO)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder))
    print("✅ Bot activo y esperando menciones en Render")
    app.run_polling()

if __name__ == '__main__':
    main()
