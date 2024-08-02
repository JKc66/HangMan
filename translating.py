from hydrogram import Client, filters
from hydrogram.types import Message, CallbackQuery
from hydrogram.enums import ParseMode
from googletrans import Translator
from config import API_HASH, API_ID, BOT_TOKEN_TEST

app = Client("translation_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN_TEST)
translator = Translator()

@app.on_message(filters.command("translate") & filters.reply)
async def translate_message(client, message: Message):
    reply = message.reply_to_message
    if not reply or not reply.text:
        await message.reply("Please reply to a text message with /translate")
        return

    source_text = reply.text
    detected_lang = translator.detect(source_text).lang

    if detected_lang == 'en':
        target_lang = 'ar'
        source_lang_name = 'English'
        target_lang_name = 'Arabic'
    elif detected_lang == 'ar':
        target_lang = 'en'
        source_lang_name = 'Arabic'
        target_lang_name = 'English'
    else:
        await message.reply(f"Detected language is {detected_lang}. This bot only supports English and Arabic translation.")
        return

    translation = translator.translate(source_text, src=detected_lang, dest=target_lang)

    response = f"Translation from {source_lang_name} to {target_lang_name}:\n\n{translation.text}"
    
    await message.reply(response, quote=True)

app.run()