from telebot import TeleBot, types
import os
import base64
import psycopg2
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
from command_handler import CommandHandler
from image_generator import ImageGenerator
import requests

load_dotenv()
bot = TeleBot(os.getenv('TG_TOKEN'))
api_key = os.getenv('KANDINSKY_API_KEY')
secret_key = os.getenv('KANDINSKY_SECRET_KEY')

price = 10


connection = psycopg2.connect(
    user=os.getenv('POSTGRES_USERNAME'),
    password=os.getenv('POSTGRES_PASSWORD'),
    host=os.getenv('POSTGRES_HOST'),
    port=os.getenv('POSTGRES_PORT'),
    dbname=os.getenv('POSTGRES_DBNAME')
)
cursor = connection.cursor()


@bot.message_handler(commands=['start', 'info'])
def send_welcome(message):
    coins = 100
    user_id = message.from_user.id
    username = message.from_user.username
    try:
        cursor.execute("""
                INSERT INTO users (user_id, username, coins) 
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, username, coins))
        connection.commit()
    except Exception as e:
        print(f"Ошибка при вставке данных: {e}")
    markup = types.ReplyKeyboardMarkup(row_width=3)
    generate_button = types.KeyboardButton('Сгенерировать изображение')
    get_balance_button = types.KeyboardButton('Узнать баланс')
    buy_button = types.KeyboardButton('Купить коины')
    markup.add(generate_button, get_balance_button, buy_button)
    bot.send_message(message.chat.id, 'Здарова, здесь ты можешь намутить себе мощнейшую пикчу.\n'
                                      f'Тебе дается {coins} бесплатных коинов.\n'
                                      f'Один запрос = {price} коинов.', reply_markup=markup)


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text
    if command_handler.has_command(text):
        command_handler.get_command(text)(message)


def ask_prompt(message):
    if get_balance(message.from_user.id) >= price:
        answer = bot.send_message(message.chat.id, 'Пришли описание картинки')
        bot.register_next_step_handler(answer, generate_image)
    else:
        bot.send_message(message.chat.id, 'У тебя нет коинов')


def get_headers():
    return {
        'X-Key': f'Key {api_key}',
        'X-Secret': f'Secret {secret_key}'
    }


def debit_coins(user_id, quantity):
    try:
        current_coins = get_balance(user_id)

        if current_coins < quantity:
            return False

        cursor.execute("""
            UPDATE users
            SET coins = coins - %s
            WHERE user_id = %s
        """, (quantity, user_id))

        connection.commit()

        return True

    except Exception as e:
        print(f"Ошибка при списании коинов: {e}")
        return False


def increase_coins(user_id, quantity):
    try:
        cursor.execute("""
            UPDATE users
            SET coins = coins + %s
            WHERE user_id = %s
        """, (quantity, user_id))
        connection.commit()

        print(f"Добавлено {quantity} коинов пользователю {user_id}")
        return True

    except Exception as e:
        print(f"Ошибка при добавлении коинов: {e}")
        return False


def get_balance(user_id):
    try:
        cursor.execute("SELECT coins FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()

        if result is None:
            print("Пользователь не найден")
            return False

        current_coins = result[0]
        return current_coins
    except Exception as e:
        print(e)


def send_balance(message):
    balance = get_balance(message.from_user.id)
    bot.send_message(message.from_user.id, f'У тебя сейчас {balance} коинов.')


def buy_coins(message):
    amount = 100
    increase_coins(message.from_user.id, amount)
    bot.send_message(message.from_user.id, f'Тебе добавлено {amount} коинов.')
    send_balance(message)


def generate_image(message):
    prompt = message.text
    bot.send_message(message.chat.id, 'Ожидайте')
    uuid = image_generator.generate(prompt, model_id)
    photo = image_generator.check_generation(uuid)[0]
    image_data = base64.b64decode(photo)
    image = BytesIO(image_data)
    img = Image.open(image)
    byte_io = BytesIO()
    img.save(byte_io, 'JPEG')
    byte_io.seek(0)
    bot.send_photo(message.chat.id, byte_io)
    debit_coins(message.from_user.id, price)
    bot.send_message(message.from_user.id, f'У тебя осталось {get_balance(message.from_user.id)} коинов.')


def get_model():
    response = requests.get('https://api-key.fusionbrain.ai/' + 'key/api/v1/models', headers=get_headers())
    data = response.json()
    return data[0]['id']


command_handler = CommandHandler({
    'Сгенерировать изображение': ask_prompt,
    'Узнать баланс': send_balance,
    'Купить коины': buy_coins,
})

image_generator = ImageGenerator('https://api-key.fusionbrain.ai/', api_key, secret_key)
model_id = image_generator.get_model()


bot.polling()
