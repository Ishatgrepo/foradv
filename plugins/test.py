import os
import re
import sys
import typing
import asyncio
import logging
from hdatabase import db
from config import Config, temp
from pyrogram import Client, filters
from pyrogram.raw.all import layer
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from pyrogram.errors.exceptions.bad_request_400 import AccessTokenExpired, AccessTokenInvalid
from pyrogram.errors import FloodWait
from translation import Translation

from typing import Union, Optional, AsyncGenerator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)]\[buttonurl:/{0,2}(.+?)(:same)?])")
HBOT_TOKEN_TEXT = "<b>1) Create a bot using @BotFather\n2) Then you will get a message with bot token\n3) Forward that message to me</b>"
SESSION_STRING_SIZE = 351

async def start_clone_bot(FwdBot, data=None):
    """Start a Pyrogram Client and attach custom iter_messages method."""
    try:
        await FwdBot.start()
        me = await FwdBot.get_me()
        logger.info(f"Started client: @{me.username or me.id} (ID: {me.id})")
        
        async def iter_messages(
            self,
            chat_id: Union[int, str],
            limit: int,
            offset: int = 0,
            search: str = None,
            filter: "types.TypeMessagesFilter" = None,
        ) -> Optional[AsyncGenerator["types.Message", None]]:
            """Iterate through a chat sequentially."""
            current = offset
            while True:
                new_diff = min(200, limit - current)
                if new_diff <= 0:
                    return
                messages = await self.get_messages(chat_id, list(range(current, current + new_diff + 1)))
                for message in messages:
                    yield message
                    current += 1
        
        FwdBot.iter_messages = iter_messages
        return FwdBot
    except Exception as e:
        logger.error(f"Error starting client: {e}")
        raise

class CLIENT:
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    def client(self, data, user=None):
        """Initialize a Pyrogram Client with a unique name for a bot or userbot."""
        try:
            if user is None and data.get('is_bot') is False:
                # Userbot from hdatabase (forwarding task)
                client_name = f"userbot_{data['id']}"
                logger.info(f"Initializing userbot: {client_name}")
                return Client(
                    name=client_name,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    session_string=data.get('session')
                )
            elif user is True:
                # Userbot from user input (adding session)
                client_name = f"userbot_{hash(data) % 1000000}"  # Unique hash-based name
                logger.info(f"Initializing userbot: {client_name}")
                return Client(
                    name=client_name,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    session_string=data
                )
            else:
                # Bot with token (from hdatabase or adding bot)
                bot_id = data.get('id', 'temp')  # Use 'temp' if ID not yet available
                client_name = f"bot_{bot_id}"
                logger.info(f"Initializing bot: {client_name}")
                return Client(
                    name=client_name,
                    api_id=self.api_id,
                    api_hash=self.api_hash,
                    HBOT_TOKEN=data.get('token'),
                    in_memory=True
                )
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise

    async def add_bot(self, bot, message):
        """Add a bot by parsing a forwarded token from @BotFather."""
        user_id = int(message.from_user.id)
        msg = await bot.ask(chat_id=user_id, text=HBOT_TOKEN_TEXT)
        if msg.text == '/cancel':
            return await msg.reply('<b>Process cancelled!</b>')
        elif not msg.forward_date:
            return await msg.reply_text("<b>This is not a forwarded message</b>")
        
        HBOT_TOKEN = re.findall(r'\d[0-9]{8,10}:[0-9A-Za-z_-]{35}', msg.text, re.IGNORECASE)
        HBOT_TOKEN = HBOT_TOKEN[0] if HBOT_TOKEN else None
        if not HBOT_TOKEN:
            return await msg.reply_text("<b>There is no bot token in that message</b>")
        
        try:
            _client = await start_clone_bot(self.client({'token': HBOT_TOKEN}, False))
            _bot = await _client.get_me()
            details = {
                'id': _bot.id,
                'is_bot': True,
                'user_id': user_id,
                'name': _bot.first_name,
                'token': HBOT_TOKEN,
                'username': _bot.username
            }
            await db.add_bot(details)
            await msg.reply_text(f"<b>Bot added successfully: @{_bot.username}</b>")
            return True
        except Exception as e:
            await msg.reply_text(f"<b>BOT ERROR:</b> `{e}`")
            return False

    async def add_session(self, bot, message):
        """Add a userbot by accepting a session string."""
        user_id = int(message.from_user.id)
        text = "<b>⚠️ DISCLAIMER ⚠️</b>\n\n<code>You can use your session for forwarding messages from private chats. Please add your Pyrogram session at your own risk. There is a chance your account could be banned. The developer is not responsible if your account gets banned.</code>"
        await bot.send_message(user_id, text=text)
        msg = await bot.ask(chat_id=user_id, text="<b>Send your Pyrogram session.\nGet it from trusted sources.\n\n/cancel - Cancel the process</b>")
        
        if msg.text == '/cancel':
            return await msg.reply('<b>Process cancelled!</b>')
        elif len(msg.text) < SESSION_STRING_SIZE:
            return await msg.reply('<b>Invalid session string</b>')
        
        try:
            client = await start_clone_bot(self.client(msg.text, True))
            user = await client.get_me()
            details = {
                'id': user.id,
                'is_bot': False,
                'user_id': user_id,
                'name': user.first_name,
                'session': msg.text,
                'username': user.username
            }
            await db.add_bot(details)
            await msg.reply_text(f"<b>Userbot added successfully: @{(user.username or user.id)}</b>")
            return True
        except Exception as e:
            await msg.reply_text(f"<b>USERBOT ERROR:</b> `{e}`")
            return False

@Client.on_message(filters.private & filters.command('reset'))
async def forward_tag(bot, m):
    default = await db.get_configs("01")
    temp.CONFIGS[m.from_user.id] = default
    await db.update_configs(m.from_user.id, default)
    await m.reply("Successfully reset settings ✔️")

@Client.on_message(filters.command('resetall') & filters.user(Config.BOT_OWNER_ID))
async def resetall(bot, message):
    users = await db.get_all_users()
    sts = await message.reply("**Processing**")
    TEXT = "total: {}\nsuccess: {}\nfailed: {}\nexcept: {}"
    total = success = failed = already = 0
    ERRORS = []
    async for user in users:
        user_id = user['id']
        default = await get_configs(user_id)
        default['db_uri'] = None
        total += 1
        if total % 10 == 0:
            await sts.edit(TEXT.format(total, success, failed, already))
        try:
            await db.update_configs(user_id, default)
            success += 1
        except Exception as e:
            ERRORS.append(e)
            failed += 1
    if ERRORS:
        await message.reply(ERRORS[:100])
    await sts.edit("Completed\n" + TEXT.format(total, success, failed, already))

async def get_configs(user_id):
    configs = await db.get_configs(user_id)
    return configs

async def update_configs(user_id, key, value):
    current = await db.get_configs(user_id)
    if key in ['caption', 'duplicate', 'db_uri', 'forward_tag', 'protect', 'file_size', 'size_limit', 'extension', 'keywords', 'button']:
        current[key] = value
    else:
        current['filters'][key] = value
    await db.update_configs(user_id, current)

def parse_buttons(text, markup=True):
    buttons = []
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            if bool(match.group(4)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(3).replace(" ", "")))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(3).replace(" ", ""))])
    if markup and buttons:
        buttons = InlineKeyboardMarkup(buttons)
    return buttons if buttons else None