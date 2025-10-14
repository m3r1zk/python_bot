import requests
import json
import asyncio
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ====================
# КОНФИГУРАЦИЯ
# ====================

TELEGRAM_BOT_TOKEN = "8294257120:AAEwUsIRVTeopgwjWajzbulDx-P_yZFHd1A"
OPENROUTER_API_KEY = "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"
API_URL = "https://router.huggingface.co/v1/chat/completions"

# Попробуем разные модели, если текущая не работает
MODEL_NAME = "meta-llama/Llama-3.1-8B-Instruct"  # Текущая модель

# ====================
# ФУНКЦИЯ ДЛЯ ЗАПРОСА К OPENROUTER API
# ====================

async def get_ai_response(user_message: str) -> str:
    """
    Отправляет запрос к API и возвращает ответ модели.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",
        "X-Title": "Telegram AI Bot"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system", 
                "content": """Ты - полезный AI-ассистент в Telegram. Твоя задача - помогать пользователям отвечать на вопросы, генерировать текст и решать различные задачи.

                    ОСНОВНЫЕ ПРИНЦИПЫ:
                    - Будь полезным, вежливым и информативным
                    - Отвечай точно на вопросы
                    - Если не знаешь ответа - честно признайся
                    - Сохраняй нейтральный профессиональный тон
                    - Будь краток, но содержателен

                    ТВОИ ВОЗМОЖНОСТИ:
                    - Отвечать на вопросы
                    - Генерировать текст (сообщения, идеи, списки)
                    - Объяснять сложные темы простым языком
                    - Предлагать решения проблем
                    - Помогать с формулировками

                    ПРАВИЛА:
                    - Не притворяйся человеком
                    - Не используй мат или оскорбительные выражения
                    - Не давай медицинских, юридических или финансовых консультаций
                    - Уважай конфиденциальность данных
                    - Будь честен о своих ограничениях"""
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "max_tokens": 300,
        "temperature": 0.7
    }

    try:
        print("🔍 Отправляем запрос к API...")
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        print(f"📊 Статус код: {response.status_code}")

        if response.status_code != 200:
            error_msg = f"Ошибка API: HTTP {response.status_code}. Ответ: {response.text[:200]}"
            print(f"❌ {error_msg}")
            return f"⚠️ {error_msg}"

        response_data = response.json()
        print(f"🔍 Полный ответ от API: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

        # ОБНОВЛЕННАЯ ЛОГИКА: обрабатываем reasoning-модели
        if ('choices' in response_data and 
                len(response_data['choices']) > 0 and 
                'message' in response_data['choices'][0]):
            
            message = response_data['choices'][0]['message']
            
            # Пытаемся получить основной ответ
            if message.get('content') and message['content'] is not None:
                ai_response = message['content'].strip()
            # Если основного ответа нет, берем reasoning_content
            elif message.get('reasoning_content') and message['reasoning_content'] is not None:
                print("🔍 Используем reasoning_content как ответ")
                ai_response = message['reasoning_content'].strip()
                # Очищаем reasoning от английских размышлений
                ai_response = clean_reasoning_response(ai_response)
            else:
                return "Не удалось получить ответ от модели."
            
            return ai_response
        else:
            return "Неожиданная структура ответа API."

    except Exception as e:
        error_msg = f"Ошибка: {str(e)}"
        print(f"❌ {error_msg}")
        return f"⚠️ {error_msg}"

def clean_reasoning_response(reasoning_text: str) -> str:
    """
    Очищает reasoning-ответ, оставляя только финальный ответ на русском языке.
    """
    # Разделяем текст на строки
    lines = reasoning_text.split('\n')
    
    # Ищем строки с русским текстом (предполагая, что финальный ответ на русском)
    russian_lines = []
    for line in lines:
        # Проверяем, содержит ли строка кириллицу
        if any('\u0400' <= char <= '\u04FF' for char in line):
            russian_lines.append(line)
    
    if russian_lines:
        # Берем последние русские строки (скорее всего, это финальный ответ)
        clean_response = ' '.join(russian_lines[-2:]) if len(russian_lines) > 2 else ' '.join(russian_lines)
        return clean_response.strip()
    else:
        # Если русских строк нет, возвращаем оригинальный текст
        return reasoning_text

def aggressive_clean_response(response: str) -> str:
    """
    Агрессивно очищает ответ от любых размышлений.
    """
    # Разделяем на строки и берем только те, которые выглядят как естественная речь
    lines = response.split('\n')
    clean_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # УДАЛЯЕМ строки, которые содержат английские слова (размышления)
        if any(word in line.lower() for word in ['i think', 'i should', 'the user', 'alright', 'let me', 'also', 'means', 'which means']):
            continue
            
        # УДАЛЯЕМ строки, которые выглядят как анализ
        if line.startswith(('Пользователь', 'User', 'The user', 'I ', 'Мы ')) and 'значит' in line.lower():
            continue
            
        # УДАЛЯЕМ строки с английскими буквами (кроме смайликов)
        if any(c in 'abcdefghijklmnopqrstuvwxyz' for c in line.lower()) and not any(c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for c in line.lower()):
            continue
            
        # Берем только строки, которые выглядят как естественная речь
        if any(c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for c in line.lower()):
            clean_lines.append(line)
        elif len(line) < 50:  # Короткие строки без русских букв (может быть смайлик и т.д.)
            clean_lines.append(line)
    
    result = ' '.join(clean_lines)
    
    # Если после очистки ничего не осталось, возвращаем первую строку с русским текстом
    if not result:
        for line in lines:
            if any(c in 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя' for c in line.lower()):
                return line.strip()
    
    return result if result else "Не понял... Можешь повторить?"

# ====================
# ОБРАБОТЧИК СООБЩЕНИЙ В TELEGRAM
# ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message = update.message or update.edited_message or getattr(update, 'business_message', None)
        if not message or not message.text:
            return

        user_message = message.text
        
        # Получаем ответ от AI с обработкой ошибок
        try:
            ai_response = await get_ai_response(user_message)
        except Exception as e:
            print(f"❌ Ошибка AI: {e}")
            ai_response = "Произошла ошибка при обработке запроса"

        # ⭐⭐⭐ ИСПРАВЛЕННЫЙ БЛОК ОТПРАВКИ СООБЩЕНИЯ ⭐⭐⭐
        
        # Получаем business_connection_id из обновления
        business_connection_id = getattr(update, 'business_connection_id', None)
        print(f"🔍 Business connection ID: {business_connection_id}")
        
        try:
            # Если есть business_connection_id, используем его
            if business_connection_id:
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=ai_response,
                    business_connection_id=business_connection_id
                )
                print("✅ Ответ отправлен через бизнес-подключение")
            else:
                # Если business_connection_id нет, пробуем обычный способ
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=ai_response
                )
                print("✅ Ответ отправлен обычным способом")
                
        except Exception as send_error:
            print(f"❌ Ошибка при отправке сообщения: {send_error}")
            
            # Пробуем альтернативный способ отправки
            try:
                await message.reply_text(ai_response)
                print("✅ Ответ отправлен через reply_text")
            except Exception as reply_error:
                print(f"❌ Ошибка при отправке через reply_text: {reply_error}")

    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
            

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"❌ Ошибка при обработке обновления: {context.error}")

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    print("🤖 Бот запущен...")
    print("📍 Тестируем - отправьте 'Привет' или 'Расскажи анекдот'")
    application.run_polling()

# Приложение слушает 0.0.0.0 и порт из переменной окружения
import os

if __name__ == '__main__':
    # Ваша обычная логика создания Application
    application = Application.builder().token("8294257120:AAEwUsIRVTeopgwjWajzbulDx-P_yZFHd1A").build()
    # Запускаем поллинг. Явно указывать хост и порт обычно не нужно,
    # так как бот не является веб-сервером.
    application.run_polling()