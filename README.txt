🧠 BOT EN RENDER - DEPLOY AUTOMÁTICO

PASOS:
1. Crea una cuenta en https://render.com
2. Conecta tu cuenta de GitHub
3. Crea un nuevo repositorio llamado "telegram-bot-sebas" y sube estos 3 archivos:
   - i_have_a_question_bot.py
   - usuarios.json
   - requirements.txt

4. En Render, crea un nuevo "Web Service" y elige tu repositorio

5. Configura:
   - Build Command: pip install -r requirements.txt
   - Start Command: python i_have_a_question_bot.py

6. En la pestaña de "Environment", añade estas 2 variables:
   - TELEGRAM_TOKEN = tu token de BotFather
   - OPENAI_API_KEY = tu clave de OpenAI

¡Listo! Tu bot quedará funcionando 24/7 en la nube ☁️🚀
