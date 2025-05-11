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
        "You always respond in English, and you specialize in helping Spanish-speaking students become more fluent. 🇪🇸🗣️\n"
        "Every time a user writes to you, your job is to:\n"
        "1️⃣ Detect and clearly show any mistakes with <s>strikethrough</s> and ❌.\n"
        "2️⃣ Show the corrected version in <b>bold</b> and with a ✅.\n"
        "3️⃣ Share a <b>Hidden Grammar tip</b> 🕵️‍♂️ that's short, natural, and fun — no technical terms.\n"
        "4️⃣ Include helpful emojis in your examples or tips (aim for 5-10 per response).\n"
        "5️⃣ Finish your message with a follow-up question to keep the conversation going.\n"
        "6️⃣ If the user asks in Spanish to explain the last message, translate and explain it in Spanish.\n"
        "Always be warm, clear, and engaging. Never say you're an AI. Act like a funny, modern, amazing human teacher who wants the student to feel empowered.\n"
        "Structure your answer, but don’t follow a rigid format — be natural!"
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

# 🧠 Memoria de usuario
memoria_conversaciones = {}

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
        user_str = str(user_id)

        # Guardar y recordar los últimos 3 mensajes del usuario
        if user_str not in memoria_conversaciones:
            memoria_conversaciones[user_str] = []
        memoria_conversaciones[user_str].append({"role": "user", "content": message_text})
        memoria_conversaciones[user_str] = memoria_conversaciones[user_str][-3:]

        # Si pide explicación en español
        if "explícamelo en español" in message_text.lower():
            historial = memoria_conversaciones.get(user_str, [])
            if len(historial) > 1:
                ultimo_mensaje = historial[-2]["content"]
                try:
                    respuesta = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": "Explica en español y de forma sencilla lo siguiente para que un estudiante principiante de inglés lo entienda:"},
                            {"role": "user", "content": ultimo_mensaje}
                        ],
                        max_tokens=500,
                        temperature=0.7
                    )
                    explicacion = respuesta.choices[0].message.content.strip()
                    await update.message.reply_text(explicacion)
                    return
                except Exception as e:
                    logging.error(f"Error en traducción: {e}")
                    await update.message.reply_text("Oops! No pude traducirlo. Intenta de nuevo.")
                    return

        if "@ihaveaquestionsebas_bot" in message_text.lower():
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
                messages = [
                    {"role": "system", "content": mensaje_sistema["content"]},
                    *memoria_conversaciones[user_str]
                ]

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7
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
