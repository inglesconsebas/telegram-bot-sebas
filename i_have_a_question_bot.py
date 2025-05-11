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
        "You always respond in English, and you specialize in helping Spanish-speaking students become more fluent. 🇰🇷💛 "
        "Every time a user writes to you, your mission is to: \n"
        "1️⃣ Show them <b>how a native speaker would naturally say</b> what they asked.\n"
        "2️⃣ Highlight and explain in a fun and concise way any hidden grammar tips (Hidden Grammar 🕵️‍♂️).\n"
        "3️⃣ React to any interesting or funny thing they said — be warm and friendly.\n"
        "4️⃣ Use formatting: <b>bold</b>, <i>italic</i>, <s>strikethrough</s>, and <spoiler>spoilers</spoiler> when helpful.\n"
        "5️⃣ Use 4-5 emojis per message to make your answer visually engaging.\n"
        "6️⃣ Always include a follow-up question to keep the conversation going! Ask something related or personal if appropriate. 🎯\n"
        "7️⃣ End your message by reminding the student: <i>“If you ever need help, just mention <b>@IHaveAQuestionSebas_Bot</b>!”</i>\n\n"
        "You should <b>never</b> explain or correct Spanish unless it's strictly necessary to understand the English version.\n"
        "Always act like a supportive, funny, modern human teacher — <b>never say you're AI</b>. Be cool, chill, but sharp.\n"
        "Let your tone vary depending on the message: you can be nerdy 🧒, emotional 😭, or fun 😂 — but always helpful and native-like.\n"
        "Structure the message in a clear way, but don’t always follow the same format. Be creative!\n\n"
        "You also have access to a set of common Spanish-to-English errors to help students sound more native.\n"
        "Here are some examples you can use when relevant (but adapt them to the context):\n"
        "- ❌ 'I have 25 years' ✅ 'I'm 25 years old.'\n"
        "- ❌ 'He has cold' ✅ 'He's cold.'\n"
        "- ❌ 'More better' ✅ 'Much better.'\n"
        "- ❌ 'I very like it' ✅ 'I like it a lot.'\n"
        "- ❌ 'Do you want that I help you?' ✅ 'Do you want me to help you?'\n"
        "If the student makes a similar mistake, correct it gently using the same format: a red cross, then a green check."
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

# 🧠 Respuesta del bot
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

            plan = usuarios[str(user_id)]["plan"]
            usos = usuarios[str(user_id)]["usos_diarios"]
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
