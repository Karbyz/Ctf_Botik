import discord
from discord.ui import Button, View
import requests
import datetime 
import asyncio
from discord.ext import commands, tasks
from datetime import time, timedelta
import pytz
import json
import re

# Bot configuration
PREFIX = '!'
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
ALLOWED_CHANNEL_ID = CHANNEL_ID
intents.voice_states = True
intents.guilds = True

user_times = {}

# Часовой пояс GMT+5
gmt_plus_5 = pytz.timezone('Etc/GMT-5') 
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Dictionary to store user choices
user_choices = {}
events_cache = {}

# Define channel IDs (replace these with actual IDs)
CHANNEL_ID_1 =CHANNEL_ID  # Example channel ID for the first message
CHANNEL_ID_2 =CHANNEL_ID  # Example channel ID for the second message
CHANNEL_ID_3 =CHANNEL_ID  # Example channel ID for the third message

def fetch_ctf_events(start_timestamp, end_timestamp):
    url = f'https://ctftime.org/api/v1/events/?limit=100&start={start_timestamp}&finish={end_timestamp}'
    headers = {
        'Host': 'ctftime.org',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Chromium";v="103", ".Not/A)Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Referer': 'https://ctftime.org/api/',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Ошибка запроса: {response.status_code}")
        return []
    return response.json()

def get_current_week():
    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(days=now.weekday())  # Start of the week (Monday)
    end = start + datetime.timedelta(days=9)  # End of the week (next Monday)
    return int(start.timestamp()), int(end.timestamp())


async def process_messages(channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    if channel is None:
        print(f"Не удалось найти канал с ID {channel_id}")
        return

    now = datetime.datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())  # Понедельник

    earliest_date = None

    async for message in channel.history(after=start_of_week):
        print(f"Processing message: {message.content}")  # Отладочное сообщение
        # Поиск всех дат в сообщении
        dates = re.findall(r'\b\w{3}, \d{2} \w{3}. \d{4}', message.content)
        for date_str in dates:
            try:
                # Преобразование строки в объект datetime
                date = datetime.datetime.strptime(date_str, '%a, %d %b. %Y')
                if earliest_date is None or date < earliest_date:
                    earliest_date = date
            except ValueError:
                # Если формат даты не совпадает, пропустить
                pass

    # Преобразование earliest_date в строку, если она не равна None
    result = {
        'earliest_date': earliest_date.isoformat() if earliest_date else None
    }

    print(f"Result: {result}")  # Отладочное сообщение

    # Сохранение результата в JSON файл
    with open('result.json', 'w') as f:
        json.dump(result, f, indent=4)

async def send_event_selection_message(channel, events):
    # Определите временную зону (UZT)
    uzt_tz = pytz.timezone('Asia/Tashkent')

    def format_datetime(iso_str):
        # Преобразуем строку ISO в объект datetime
        dt = datetime.datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        # Локализуем datetime в нужный часовой пояс
        dt_uzt = dt.astimezone(uzt_tz)
        # Форматируем в нужный формат
        return dt_uzt.strftime('%a, %d %b. %Y, %H:%M UZT')

    # Создаем список событий с их деталями, включая форматирование даты
    event_list = '\n'.join([
        f"**{event['title']}**\nНачало: {format_datetime(event['start'])}\nКонец: {format_datetime(event['finish'])}\nВес: {event['weight']}\n <{event['url']}>\n" 
        for event in events
    ])

    # Отправляем сообщение с деталями событий и кнопками для выбора
    view = EventSelectionView(events)
    await channel.send(f"Выберите CTF событие:\n\n{event_list}", view=view)

def format_event_list(events):
    output = f"{'№':<5} | {'Название':<30} | {'Дата':<25} | {'Вес':<10}\n"
    output += '-' * 65 + '\n'
    
    for idx, event in enumerate(events, start=1):
        name = event.get('title', 'Неизвестно')
        start = event.get('start', 'Неизвестно')
        weight = event.get('weight', '0.0')
        
        try:
            start_datetime = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
            formatted_date = start_datetime.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            formatted_date = 'Неизвестно'
            
        output += f"{idx:<5} | {name:<30} | {formatted_date:<25} | {weight:<10}\n"
    
    return output

def format_event_details(event):
    name = event.get('title', 'Неизвестно')
    start = event.get('start', 'Неизвестно')
    finish = event.get('finish', 'Неизвестно')
    url = event.get('url', 'Неизвестно')
    format_type = event.get('format', 'Неизвестно')

    try:
        start_datetime = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
        formatted_start_date = start_datetime.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        formatted_start_date = 'Неизвестно'
        
    try:
        finish_datetime = datetime.datetime.fromisoformat(finish.replace('Z', '+00:00'))
        formatted_finish_date = finish_datetime.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        formatted_finish_date = 'Неизвестно'

    format_display = {
        'Jeopardy': 'Jeopardy',
        'Attack-Defence': 'Attack-Defence'
    }.get(format_type, 'Неизвестно')

    return (f"Имя: {name}\n"
            f"Дата начала: {formatted_start_date}\n"
            f"Дата окончания: {formatted_finish_date}\n"
            f"Сайт: {url}\n"
            f"Формат: {format_display}")

class EventSelectionView(View):
    def __init__(self, events):
        super().__init__()
        self.events = events
        for event in events:
            button = Button(
                label=event['title'],
                style=discord.ButtonStyle.primary,
                custom_id=str(event['id'])  # Убедитесь, что это строка
            )
            self.add_item(button)

class CategoryInputView(View):
    def __init__(self, event_id):
        super().__init__()
        self.event_id = event_id
        self.add_item(Button(label="Submit Categories", style=discord.ButtonStyle.primary, custom_id='submit_categories'))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in user_choices

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class CredentialsInputView(View):
    def __init__(self):
        super().__init__()
        self.add_item(Button(label="Submit Credentials", style=discord.ButtonStyle.primary, custom_id='submit_credentials'))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in user_choices

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class ConfirmationView(View):
    def __init__(self):
        super().__init__()
        self.add_item(Button(label="Confirm", style=discord.ButtonStyle.success, custom_id='confirm'))
        self.add_item(Button(label="Cancel", style=discord.ButtonStyle.danger, custom_id='cancel'))
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in user_choices

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

@bot.command()
async def ctf_events(ctx):
    if ctx.channel.id == ALLOWED_CHANNEL_ID:
        start_timestamp, end_timestamp = get_current_week()
        events = fetch_ctf_events(start_timestamp, end_timestamp)
           
        if not events:
            await ctx.send('Не удалось получить события.')
            return

        # Сохраняем события в глобальном словаре
        events_cache[ctx.channel.id] = events

        await send_event_selection_message(ctx.channel, events)


class CTFSelectionView(View):
    def __init__(self, events):
        super().__init__()
        self.events = events
        for event in events:
            self.add_item(Button(label=event['title'], custom_id=str(event['id']), style=discord.ButtonStyle.primary))

@bot.event
async def on_ready():
    print(f'Бот {bot.user} подключен и готов к работе!')

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user_id = interaction.user.id
    if isinstance(interaction, discord.Interaction):
        if interaction.data.get('custom_id'):
            custom_id = interaction.data['custom_id']

            # Handle event selection
            if custom_id.isdigit():
                selected_event_id = int(custom_id)
                user_choices[user_id] = {'event_id': selected_event_id}

                # Prompt user for categories
                await interaction.response.send_message('Вы выбрали событие. Пожалуйста, введите категории для этого события.')

                # Wait for user's categories input
                def check(msg):
                    return msg.author == interaction.user and msg.channel == interaction.channel

                try:
                    
                    msg = await bot.wait_for('message', check=check, timeout=300)  # 5 minutes timeout
                    user_choices[user_id]['categories'] = msg.content
                    await msg.delete()  # Optionally delete the user's message


                    await interaction.channel.send(f"Теперь введите креды для входа.")
                    msg = await bot.wait_for('message', check=check, timeout=300)
                    user_choices[user_id]['credentials'] = msg.content
                    await msg.delete()

                    # Prompt user to confirm or cancel
                    await interaction.channel.send('Подтвердите отправку.')
                    view = ConfirmationView()
                    message = await interaction.channel.send('Подтвердите или отмените:', view=view)
                    view.message = message

                except asyncio.TimeoutError:
                    await interaction.channel.send('Время ожидания истекло. Процесс отменен.')
                    del user_choices[user_id]

            # Handle confirmation or cancellation
            elif custom_id == 'confirm':
                if user_id in user_choices:
                    data = user_choices[user_id]
                    event_id = data['event_id']
                    categories = data['categories']
                    credentials = data['credentials']

                    # Fetch event details from cache
                    event = next((e for e in events_cache.get(interaction.channel.id, []) if e['id'] == event_id), None)

                    if event:
                        start_datetime = datetime.datetime.fromisoformat(event['start'].replace('Z', '+05:00'))
                        finish_datetime = datetime.datetime.fromisoformat(event['finish'].replace('Z', '+05:00'))
                        local_tz = pytz.timezone('Asia/Tashkent')  # UZT соответствует Tashkent
                        start_datetime_local = start_datetime.astimezone(local_tz)
                        finish_datetime_local = finish_datetime.astimezone(local_tz)
                        formatted_start_date = start_datetime_local.strftime('%a, %d %b. %Y, %H:%M UZT')
                        formatted_finish_date = finish_datetime_local.strftime('%a, %d %b. %Y, %H:%M UZT')

                        # Replace these with your actual channel IDs
                        channel1 = bot.get_channel(CHANNEL_ID_1)
                        channel2 = bot.get_channel(CHANNEL_ID_2)
                        channel3 = bot.get_channel(CHANNEL_ID_3)

                        # Format event details
                        formatted_details = (f"**Event Name:** {event['title']}\n"
                                             f"Date: {formatted_start_date} — {formatted_finish_date}\n"
                                             f"Website: {event['url']}\n"
                                             f"Format: {event['format']}\n"
                                             f"Categories: {categories}")

                        # Send messages to channels
                        await channel1.send(f"1. {event['title']}\n2. {formatted_start_date} — {formatted_finish_date}\n3. <{event['url']}>\n4. {event['format']}\n5. {categories}")
                        await channel2.send(f"<@&1196817406966894722> Прошу (требую) поучаствовать в ниже указанном ctf: <@&1180062636361134110> <@&1180062609941205013> <@&1180062567452901466>\n\n"
                                            f"{event['title']} ({formatted_start_date} — {formatted_finish_date}) - w. {event['weight']}\n{categories}\n\n"
                                            f"Задачи:\nПосле окончания сделать райтап и загрузить в <#{1165842000591990814}>")
                        await channel3.send(f"1. {event['title']} <#{1165835889533014016}>\n2. Rating weight: {event['weight']}\n3. team: {credentials}")
                        await interaction.response.send_message('Сообщения отправлены.')
                        await process_messages('1165835889533014016')
                        del user_choices[user_id]

            elif custom_id == 'cancel':
                await interaction.response.send_message('Процесс отменен.')
                del user_choices[user_id]
        else:
            await interaction.response.send_message('Неизвестное взаимодействие.')


user_ids = [
    USERS_ID
]
CHANNEL_ID = 1191768060500131922

async def send_ping_message():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids])
        await channel.send(f"Внимание всем CTF ИДЕТ АААААААААААААА: {mentions}")



def is_tracking_time():
    # Определяем текущую дату и время в UTC
    now = datetime.datetime.now(pytz.utc)
    # Переводим в местное время (GMT+5)
    local_time = now.astimezone(pytz.timezone('Etc/GMT+5'))

    weekday = local_time.weekday()
    hour = local_time.hour
    minute = local_time.minute

    # Проверяем, попадает ли текущее время в указанный диапазон
    if weekday == 4 and (hour > 10 or (hour == 10 and minute >= 0)):  # Пятница после 10:00
        return True
    elif weekday == 5 or weekday == 6:  # Суббота и Воскресенье
        return True
    elif weekday == 0 and (hour < 1 or (hour == 1 and minute <= 10)):  # Понедельник до 1:10
        return True
    
    return False

@bot.event
async def on_voice_state_update(member, before, after):
    if not is_tracking_time():
        return
    
    user_id = member.id

    # Если пользователь зашел в голосовой канал
    if before.channel is None and after.channel is not None:
        user_times[user_id] = {"join_time": datetime.datetime.now(pytz.utc)}
        print('aboba')
    
    # Если пользователь вышел из голосового канала
    elif before.channel is not None and after.channel is None:
        if user_id in user_times:
            join_time = user_times[user_id]["join_time"]
            time_spent = datetime.datetime.now(pytz.utc) - join_time

            # Обновляем общее время
            if "total_time" in user_times[user_id]:
                user_times[user_id]["total_time"] += time_spent
            else:
                user_times[user_id]["total_time"] = time_spent
            
            del user_times[user_id]["join_time"]

# Функция для получения общего времени
def get_time_report():
    report = {}
    for member_id, data in user_times.items():
        total_time = data.get("total_time", timedelta())
        
        # Если пользователь еще находится в канале, учитываем время до текущего момента
        if "join_time" in data:
            current_time = datetime.datetime.now(pytz.utc)
            time_spent = current_time - data["join_time"]
            total_time += time_spent
        
        hours, remainder = divmod(total_time.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        report[member_id] = {
            'total_hours': int(hours),
            'total_minutes': int(minutes)
        }
    return report

def process_time_report(report):
    filename = 'voice_channel_report.json'
    with open(filename, 'w') as file:
        json.dump(report, file, indent=4)
    print(f"Отчет записан в файл {filename}:")
    print(json.dumps(report, indent=4))



bot.run('TOKEN')
