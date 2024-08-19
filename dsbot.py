import discord
from discord.ext import commands
from discord.ui import Button, View
import requests
import datetime
import asyncio
from discord.ext import commands, tasks


# Bot configuration
PREFIX = '!'
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Dictionary to store user choices
user_choices = {}
events_cache = {}

# Define channel IDs (replace these with actual IDs)
CHANNEL_ID_1 = 922836245216886804  # Example channel ID for the first message
CHANNEL_ID_2 = 1273526618962268251  # Example channel ID for the second message
CHANNEL_ID_3 = 1273526644350386199  # Example channel ID for the third message

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
    end = start + datetime.timedelta(days=7)  # End of the week (next Monday)
    return int(start.timestamp()), int(end.timestamp())

async def send_event_selection_message(channel, events):
    # Создаем список событий с их деталями
    event_list = '\n'.join([
        f"**{event['title']}**\nДата: {event['start']} - {event['finish']}\nВес: {event['weight']}\n" 
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
    print(f'Logged in as {bot.user.name}')
    scheduled_ping.start()

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

                    # Prompt user for credentials
                    await interaction.channel.send('Теперь введите креды для входа.')
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
                        start_datetime = datetime.datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
                        finish_datetime = datetime.datetime.fromisoformat(event['finish'].replace('Z', '+00:00'))
                        formatted_start_date = start_datetime.strftime('%a, %d %b. %Y, %H:%M UZT')
                        formatted_finish_date = finish_datetime.strftime('%a, %d %b. %Y, %H:%M UZT')

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
                        await channel1.send(f"1. {event['title']}\n2. {formatted_start_date} — {formatted_finish_date}\n3. {event['url']}\n4. {event['format']}\n5. {categories}")
                        await channel2.send(f"<@&619806398514987039> <@994586539822690334>  Прошу (требую) поучаствовать в ниже указанном ctf: @3 курс @2 курс @1 курс\n\n"
                                            f"{event['title']} ({formatted_start_date} — {formatted_finish_date}) - w. {event['weight']}\n{categories}\n\n"
                                            f"Задачи:\nПосле окончания сделать райтап и загрузить в ⁠⁠‖-📑writeups")
                        await channel3.send(f"1. {event['title']} ⁠‖-👾ctf-time\n2. Rating weight: {event['weight']}\n3. team: {credentials}")

                        await interaction.response.send_message('Сообщения отправлены.')
                        del user_choices[user_id]

            elif custom_id == 'cancel':
                await interaction.response.send_message('Процесс отменен.')
                del user_choices[user_id]
        else:
            await interaction.response.send_message('Неизвестное взаимодействие.')


user_ids = [ ]
CHANNEL_ID = 922836245216886804

async def send_ping_message():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        mentions = ' '.join([f'<@{user_id}>' for user_id in user_ids])
        await channel.send(f"Внимание всем CTF ИДЕТ АААААААААААААА: {mentions}")

# Task that runs every Saturday at 15:00
@tasks.loop(minutes=1)
async def scheduled_ping():
    now = datetime.datetime.utcnow()
    if now.weekday() == 5 and now.hour == 15 and now.minute == 0:  # Saturday at 15:00 UTC
        await send_ping_message()

bot.run('')