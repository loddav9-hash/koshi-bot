import asyncio
import csv
import os
from datetime import datetime
from vkbottle.bot import Bot, Message
from openai import OpenAI

# === НАСТРОЙКИ ===
VK_TOKEN = os.environ.get("VK_TOKEN")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
ADMIN_VK_ID = int(os.environ.get("ADMIN_VK_ID", "0"))
GROUP_ID = 240688636

# === ИИ (NVIDIA NIM) ===
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "deepseek-ai/deepseek-v4-flash-0731"

# Инициализация клиента ИИ
ai_client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)

# === СИСТЕМНЫЙ ПРОМПТ ===
SYSTEM_PROMPT = """
Ты — вежливый и дружелюбный администратор школы танцев KOSHI в Северодвинске.
Твоя задача — отвечать на вопросы клиентов, помогать выбрать направление и записывать на пробное занятие.

ИНФОРМАЦИЯ О ШКОЛЕ:
- Название: Школа танцев KOSHI.
- Для кого: Дети с 3 лет и взрослые.
- Адрес: г. Северодвинск, Беломорский проспект, 44А. Вход со двора, 3-й этаж.
- Пробное занятие: 350 ₽.
- Аренда зала: от 250 до 2000 ₽ (по договорённости).
- Работает: Онлайн с 8:30 до 22:45, офлайн с 8:45 до 14:00 и с 16:30 до 22:45.

НАПРАВЛЕНИЯ:
Frame Up Strip, High Heels, Vogue, Contemporary, Pole Exotic, Pole Acro, Chair Dance, Партерная акробатика, Растяжка, Силовая подготовка, Hip-Hop, Коммерция, Шпагат, Solo бачата.

РАСПИСАНИЕ (сентябрь):
Большой зал:
- Пн: 09:00 Frame up strip, 10:00 Pole Exotic, 19:00 High Heels, 20:00 Растяжка, 21:30 Pole Exotic.
- Вт: 09:00 Pole Exotic, 10:00 Pole Acro, 17:00 Pole Acro, 18:00 Girly hip-hop, 19:00 Frame up strip, 20:00 Pole Exotic, 21:00 Pole Acro.
- Ср: 09:00 Растяжка, 10:30 Партерная акробатика, 18:00 Pole Acro, 19:00 Frame up strip, 20:00 Pole Exotic, 21:00 Pole Acro.
- Чт: 09:00 Pole Exotic, 10:00 Pole Acro, 17:00 Pole Acro, 18:00 Frame up strip, 19:00 Girly hip-hop, 20:00 Pole Exotic, 21:00 Pole Acro.
- Пт: 09:00 Frame up strip, 10:00 Pole Exotic, 19:00 High Heels, 20:00 Растяжка, 21:30 Pole Exotic.
- Сб: 12:00 Pole Acro, 15:00 Pole Exotic, 16:00 СФП, 17:00 Pole Exotic, 18:30 Pole Acro.
- Вс: 09:00 Растяжка, 10:30 Партерная акробатика, 13:00 Frame up strip.

Малый зал:
- Пн/Пт: 18:00 High Heels, 20:00 Solo бачата.
- Ср: 17:00 Hip-hop (подростки), 18:00 Коммершл, 19:00 Шпагат.
- Сб: 15:30 Girly hip-hop, 17:00 Hip-hop (подростки), 18:00 Коммершл.
- Вс: 14:00 Solo бачата.

КАК ЗАПИСАТЬСЯ:
1. Спроси имя клиента.
2. Спроси номер телефона для связи.
3. Спроси направление и удобное время.
4. Скажи: "Отлично! Я передал вашу заявку менеджеру, он перезвонит в ближайшее время для подтверждения. Спасибо! ❤️"

ПРАВИЛА ОБЩЕНИЯ:
- Отвечай вежливо, дружелюбно, используй эмодзи (но не перебарщивай).
- Если не знаешь точный ответ — предложи написать менеджеру.
- Не выдумывай информацию, которой нет в этом промпте.
- Отвечай кратко, но по делу.
"""

bot = Bot(token=VK_TOKEN)

# === ХРАНИЛИЩЕ ИСТОРИИ ===
user_histories = {}

# === ФУНКЦИЯ СОХРАНЕНИЯ ЗАЯВКИ ===
def save_application(user_id: int, user_name: str, phone: str, direction: str, time: str):
    """Сохраняет заявку в CSV-файл."""
    filename = "заявки.csv"
    file_exists = False
    try:
        with open(filename, "r", encoding="utf-8") as f:
            file_exists = True
    except FileNotFoundError:
        pass
    
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        if not file_exists:
            writer.writerow(["Дата", "VK ID", "Имя", "Телефон", "Направление", "Время"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            user_id,
            user_name,
            phone,
            direction,
            time,
        ])

# === ФУНКЦИЯ ОТПРАВКИ ЗАЯВКИ АДМИНУ ===
async def notify_admin(user_name: str, phone: str, direction: str, time: str):
    """Отправляет уведомление админу в личку ВК."""
    text = (
        f"🔔 НОВАЯ ЗАЯВКА\n\n"
        f"Имя: {user_name}\n"
        f"Телефон: {phone}\n"
        f"Направление: {direction}\n"
        f"Время: {time}\n\n"
        f"Проверьте и перезвоните!"
    )
    try:
        await bot.api.messages.send(
            user_id=ADMIN_VK_ID,
            message=text,
            random_id=0,
        )
    except Exception as e:
        print(f"Не удалось отправить заявку админу: {e}")

# === ФУНКЦИЯ ИИ ===
def get_ai_response(user_message: str, history: list = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        import traceback
        print("=== ОШИБКА ИИ ===")
        traceback.print_exc()
        print("=================")
        return "Извините, у меня сейчас небольшая заминка 😅 Напишите, пожалуйста, менеджеру напрямую."

# === ОБРАБОТЧИКИ ===
@bot.on.message(text=["начать", "start", "привет", "здравствуйте", "hi", "hello"])
async def start_handler(message: Message):
    await message.answer(
        "Привет! 👋 Я бот школы танцев KOSHI.\n\n"
        "Могу помочь:\n"
        "• Рассказать о направлениях\n"
        "• Показать расписание\n"
        "• Записать на пробное занятие (350 ₽)\n\n"
        "Что вас интересует?"
    )

@bot.on.message()
async def all_messages(message: Message):
    user_id = message.from_id
    user_text = message.text
    
    history = user_histories.get(user_id, [])
    response = get_ai_response(user_text, history)
    
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": response})
    user_histories[user_id] = history[-10:]
    
    await message.answer(response)

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# === ПРОСТОЙ HEALTH SERVER ДЛЯ RENDER ===
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass  # Отключаем лишние логи

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server запущен на порту {port}")
    server.serve_forever()

# Запускаем health server в фоновом потоке
threading.Thread(target=run_health_server, daemon=True).start()
# === ЗАПУСК ===
if __name__ == "__main__":
    print("Бот запущен и готов к работе...")
    bot.run()