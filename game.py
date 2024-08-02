
import asyncio
import json
import random
from datetime import date, datetime, timedelta
from operator import itemgetter

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


from config import API_HASH, API_ID, BOT_TOKEN_HANGMAN, BOT_TOKEN_TEST
from word_list import WORDS
  

app = Client("hangman_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN_HANGMAN)

games = {}
player_stats = {}
daily_challenges = {}
leaderboard = {}
game_activity = {}

last_pressed_button = None


def load_user_configs():
    try:
        with open('users_config.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_user_configs(configs):
    with open('users_config.json', 'w') as f:
        json.dump(configs, f, indent=4)

user_configs = load_user_configs()


default_emoji_sets = {
    "lives": ["💚", "❤️", "💔"],
    "keyboard": ["🎯", "🚫"],
    "difficulty": ["😊", "😐", "😈"]
}

KEYBOARD_EMOJI_SETS = [
    ("🎯", "🚫"), ("✅", "❌"), ("🟢", "🔴"),
    ("👍", "👎"), ("💚", "💔"), ("😊", "😞"),
    ("🌟", "💨"), ("✓", "✗")
]

LIVES_EMOJI_SETS = [
    ("💚", "❤️", "💔"),
    ("🧔‍♂️", "💀", "⚰️"),
    ("🌱", "🍃", "🍂"),
    ("🍜", "🥢", "🥣")
]


DIFFICULTY_EMOJI_SETS = [
    ("😊", "😐", "😈"),
    ("😃", "😑", "😠"),
    ("🤡", "😕", "😡"),
    ("😁", "😶", "😤"),
    ("😌", "🤔", "💪"),
    ("😇", "🙄", "😎")
]

emoji_options = {
    "keyboard": [pair for pair in KEYBOARD_EMOJI_SETS],
    "lives": [trio for trio in LIVES_EMOJI_SETS],
    "difficulty": [trio for trio in DIFFICULTY_EMOJI_SETS]
}



def load_daily_challenges():
    try:
        with open('daily_challenges.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_daily_challenges(daily_challenges):
    with open('daily_challenges.json', 'w') as f:
        json.dump(daily_challenges, f, indent=4)

def can_play_daily_challenge(user_id):
    daily_challenges = load_daily_challenges()
    today = date.today().isoformat()
    
    if user_id not in daily_challenges or daily_challenges[user_id]['last_played'] != today:
        daily_challenges[user_id] = {'last_played': today, 'score': 0}
        save_daily_challenges(daily_challenges)
        return True
    return False

def update_daily_challenge_score(user_id, score):
    daily_challenges = load_daily_challenges()
    today = date.today().isoformat()
    
    if user_id in daily_challenges and daily_challenges[user_id]['last_played'] == today:
        if score > daily_challenges[user_id]['score']:
            daily_challenges[user_id]['score'] = score
            save_daily_challenges(daily_challenges)
        return daily_challenges[user_id]['score']
    return score

def get_daily_challenge_leaderboard():
    daily_challenges = load_daily_challenges()
    today = date.today().isoformat()
    
    leaderboard = [(user_id, data['score']) for user_id, data in daily_challenges.items() if data['last_played'] == today]
    return sorted(leaderboard, key=lambda x: x[1], reverse=True)[:10]



def save_player_stats():
    with open('player_stats.json', 'w') as f:
        serializable_stats = {
            user_id: {
                **stats,
                "achievements": list(stats["achievements"]),
                "last_played": stats["last_played"].isoformat() if stats["last_played"] else None
            }
            for user_id, stats in player_stats.items()
        }
        json.dump(serializable_stats, f, indent=4)

def update_player_name(user_id, new_name):
    if user_id in player_stats:
        player_stats[user_id]["name"] = new_name
        save_player_stats()
        


def load_player_stats():
    global player_stats
    try:
        with open('player_stats.json', 'r') as f:
            loaded_stats = json.load(f)
            player_stats = {}
            for user_id, stats in loaded_stats.items():
                player_stats[user_id] = {
                    **stats,
                    "achievements": set(stats.get("achievements", [])),
                    "last_played": datetime.fromisoformat(stats["last_played"]).date() if stats.get("last_played") else None
                }
    except (FileNotFoundError, json.JSONDecodeError):
        player_stats = {}

    for user_id, stats in player_stats.items():
        initialize_player_stats(user_id, stats.get("name", ""))

    save_player_stats()

def initialize_player_stats(user_id, user_name):
    if user_id not in player_stats or player_stats[user_id] is None:
        player_stats[user_id] = {
            "games_played": 0,
            "games_won": 0,
            "total_score": 0,
            "guessed_letters": 0,
            "solved_words": 0,
            "name": user_name,
            "streak": 0,
            "last_played": None,
            "achievements": set(),
            "scores": []
        }
    else:
        stats = player_stats[user_id]
        stats.setdefault("games_played", 0)
        stats.setdefault("games_won", 0)
        stats.setdefault("total_score", 0)
        stats.setdefault("guessed_letters", 0)
        stats.setdefault("solved_words", 0)
        stats.setdefault("name", user_name)
        stats.setdefault("streak", 0)
        stats.setdefault("last_played", None)
        stats.setdefault("achievements", set())
        stats.setdefault("scores", [])

    return player_stats[user_id]

async def check_inactive_games():
    while True:
        current_time = datetime.now()
        inactive_users = []
        for user_id, last_activity in list(game_activity.items()):
            if (current_time - last_activity) > timedelta(minutes=2): 
                inactive_users.append(user_id)
        
        for user_id in inactive_users:
            if user_id in games:
                game = games[user_id]
                try:
                    await app.delete_messages(
                        chat_id=game["chat_id"],
                        message_ids=game["message_ids"]
                    )
                    print(f"Deleted {len(game['message_ids'])} inactive game messages for user {user_id}")
                except Exception as e:
                    print(f"Error deleting messages for user {user_id}: {e}")
                del games[user_id]
            if user_id in game_activity:
                del game_activity[user_id]
        
        await asyncio.sleep(60)
 

def track_game_setup(user_id, stage, chat_id, message_id):
    if user_id not in games:
        games[user_id] = {
            "message_ids": [],
            "chat_id": chat_id
        }
    games[user_id].update({
        "setup_stage": stage,
        "chat_id": chat_id,
    })
    games[user_id]["message_ids"].append(message_id)
    game_activity[user_id] = datetime.now()

def create_new_game(user_id, word, category, difficulty, chat_id, message_id):
    keyboard_letters = generate_keyboard(word, set())
    attempts = calculate_attempts(len(word))
    
    if user_id not in games:
        games[user_id] = {
            "message_ids": [],
            "chat_id": chat_id
        }
    
    games[user_id].update({
        "word": word,
        "guessed_letters": set(),
        "attempts": attempts,
        "category": category,
        "difficulty": difficulty,
        "score": 0,
        "keyboard_letters": keyboard_letters,
        "user_name": player_stats[user_id]["name"] if user_id in player_stats else "Unknown Player",
        "setup_stage": "game_started"
    })
    games[user_id]["message_ids"].append(message_id)
    game_activity[user_id] = datetime.now()

    
def update_player_stats(user_id, user_name, won, score, guessed_letter_count=0, solved_word=False):
    initialize_player_stats(user_id, user_name)

    player_stats[user_id]["games_played"] += 1
    if won:
        player_stats[user_id]["games_won"] += 1
    if solved_word:
        player_stats[user_id]["solved_words"] += 1
    player_stats[user_id]["total_score"] += score
    player_stats[user_id]["guessed_letters"] += guessed_letter_count

    if "scores" not in player_stats[user_id]:
        player_stats[user_id]["scores"] = []
    player_stats[user_id]["scores"].append(score)
    player_stats[user_id]["scores"] = sorted(player_stats[user_id]["scores"], reverse=True)[:5]

    current_date = datetime.now().date()
    last_played = player_stats[user_id]["last_played"]
    if last_played is None:
        player_stats[user_id]["streak"] = 1
    elif last_played == current_date - timedelta(days=1):
        player_stats[user_id]["streak"] += 1
    elif last_played != current_date:
        player_stats[user_id]["streak"] = 1
    player_stats[user_id]["last_played"] = current_date

    save_player_stats()

def get_player_stats(user_id):
    initialize_player_stats(user_id, "")
    stats = player_stats[user_id]
    games_played = stats["games_played"]
    win_rate = (stats["games_won"] / games_played * 100) if games_played > 0 else 0
    avg_score = stats["total_score"] / games_played if games_played > 0 else 0
    return (f"Games Played: {games_played}\n"
            f"Win Rate: {win_rate:.2f}%\n"
            f"Average Score: {avg_score:.2f}\n"
            f"Current Streak: {stats['streak']} days\n"
            f"Achievements: {', '.join(stats['achievements']) if stats['achievements'] else 'None'}")

def get_random_word(category, difficulty):
    return random.choice(WORDS[category][difficulty])

def calculate_attempts(word_length, base_attempts=5, length_factor=2):
    return base_attempts + word_length // length_factor

def create_hangman_display(word, guessed_letters):
    return " ".join(letter if letter in guessed_letters else "▢" for letter in word)

def calculate_score(word, attempts_left, difficulty):
    difficulty_multiplier = {"easy": 1, "medium": 2, "hard": 3}
    return len(set(word)) * attempts_left * difficulty_multiplier[difficulty.lower()]

def get_user_emoji_set(user_id, emoji_type):
    return user_configs.get(user_id, {}).get(emoji_type, default_emoji_sets[emoji_type])

def is_original_user(callback_query, original_user_id):
    if str(callback_query.from_user.id) != original_user_id:
        return False
    return True

def format_message(word, guessed_letters, attempts, category, difficulty, score, user_id):
    max_attempts = calculate_attempts(len(word))
    attempts_left = max(0, min(attempts, max_attempts))

    hangman_display = create_hangman_display(word, guessed_letters)

    lives_emojis = get_user_emoji_set(user_id, "lives")
    live_emoji, dead_emoji, last_attempt_emoji = lives_emojis

    if attempts_left == 1:
        lives_display = last_attempt_emoji * max_attempts
    else:
        lives_display = live_emoji * attempts_left + dead_emoji * (max_attempts - attempts_left)

    difficulty_emojis = get_user_emoji_set(user_id, "difficulty")
    difficulty_emoji = difficulty_emojis[["easy", "medium", "hard"].index(difficulty.lower())]

    message = f"🎮 Hangman Game - {category.capitalize()} ({difficulty.capitalize()} {difficulty_emoji})\n"
    message += f"Word: `{hangman_display}`\n\n"
    message += f"Attempts left: {lives_display}\n"
    message += f"Guessed letters: {', '.join(sorted(guessed_letters)) if guessed_letters else 'None'}\n"
    message += f"Current Score: `{score}` \n\n"
    message += "Guess a letter!"
    return message

def generate_keyboard(word, guessed_letters):
    all_letters = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    word_letters = set(word.upper())
    remaining_letters = all_letters - guessed_letters - word_letters

    num_additional_letters = max(10, len(word) * 2)
    num_additional_letters = min(num_additional_letters, len(remaining_letters))

    remaining_letters_list = list(remaining_letters)

    random_sample = random.sample(remaining_letters_list, num_additional_letters)

    keyboard_letters = list(word_letters.union(random_sample))

    keyboard_letters = sorted(keyboard_letters)

    return keyboard_letters

def create_keyboard_markup(keyboard_letters, guessed_letters, word, user_id):
    keyboard_emojis = get_user_emoji_set(user_id, "keyboard")
    correct_emoji, incorrect_emoji = keyboard_emojis

    buttons = []
    for i in range(0, len(keyboard_letters), 5):
        row = []
        for letter in keyboard_letters[i:i+5]:
            if letter in guessed_letters:
                if letter in word:
                    row.append(InlineKeyboardButton(correct_emoji, callback_data=f"used_{user_id}"))
                else:
                    row.append(InlineKeyboardButton(incorrect_emoji, callback_data=f"used_{user_id}"))
            else:
                row.append(InlineKeyboardButton(letter, callback_data=f"guess_{letter}_{user_id}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("💡 Hint", callback_data=f"hint_{user_id}")])

    return InlineKeyboardMarkup(buttons)

def generate_daily_challenge():
    category = random.choice(list(WORDS.keys()))
    difficulty = random.choice(["easy", "medium", "hard"])
    word = get_random_word(category, difficulty)
    daily_challenges["word"] = word
    daily_challenges["category"] = category
    daily_challenges["difficulty"] = difficulty
    daily_challenges["date"] = datetime.now().date()

def update_leaderboard(user_id, score):
    if user_id not in leaderboard:
        leaderboard[user_id] = 0
    leaderboard[user_id] += score

    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:10]
    leaderboard.clear()
    leaderboard.update(dict(sorted_leaderboard))

def update_streak(user_id):
    stats = player_stats.get(user_id)
    if stats:
        current_date = datetime.now().date()
        if stats["last_played"] == current_date - timedelta(days=1):
            stats["streak"] += 1
        elif stats["last_played"] != current_date:
            stats["streak"] = 1
        stats["last_played"] = current_date
        save_player_stats()

def check_achievements(user_id):
    stats = player_stats.get(user_id)
    if not stats:
        return []

    new_achievements = []
    all_achievements = {
        "first_win": "🏆 First Win",
        "streak_7": "🔥 7-Day Streak",
        "games_50": "🎮 50 Games Played",
        "words_20": "📚 20 Words Solved",
        "perfect_game": "💯 Perfect Game"
    }

    if stats["games_won"] == 1 and "first_win" not in stats["achievements"]:
        new_achievements.append(all_achievements["first_win"])
        stats["achievements"].add("first_win")

    if stats["streak"] >= 7 and "streak_7" not in stats["achievements"]:
        new_achievements.append(all_achievements["streak_7"])
        stats["achievements"].add("streak_7")

    if stats["games_played"] >= 50 and "games_50" not in stats["achievements"]:
        new_achievements.append(all_achievements["games_50"])
        stats["achievements"].add("games_50")

    if stats["solved_words"] >= 20 and "words_20" not in stats["achievements"]:
        new_achievements.append(all_achievements["words_20"])
        stats["achievements"].add("words_20")

    game = games.get(user_id)
    if game and "perfect_game" not in stats["achievements"]:
        word_length = len(game["word"])
        max_attempts = calculate_attempts(word_length)
        if game["attempts"] == max_attempts and set(game["word"]) <= game["guessed_letters"]:
            new_achievements.append(all_achievements["perfect_game"])
            stats["achievements"].add("perfect_game")

    save_player_stats()
    return new_achievements

@app.on_message(filters.command("hangman"))
async def start_command(client, message):
    welcome_text = (
        "🎮 **Welcome to Hangman!** 🎉\n\n"
        "Guess the word before the man gets hanged! ☠️\n\n"
        "**Available Commands:**\n"
        "🔹 /play - Start a new game. 🕹️\n"
        "🔹 /stats - View your statistics. 📊\n"
        "🔹 /ranking - Check the leaderboard. 🏆\n"
        "🔹 /config - Customize your game experience. ⚙️\n\n"
        "Good luck and have fun! 🍀"
    )
    await message.reply_text(welcome_text)


@app.on_message(filters.command("stats"))
async def stats_command(client, message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    if user_id in player_stats and player_stats[user_id]["name"] != user_name:
        update_player_name(user_id, user_name)

    stats = player_stats.get(user_id, {
        "games_played": 0,
        "games_won": 0,
        "total_score": 0,
        "guessed_letters": 0,
        "solved_words": 0,
        "name": user_name,
        "achievements": set()
    })
    games_played = stats["games_played"]
    win_rate = (stats["games_won"] / games_played * 100) if games_played > 0 else 0
    avg_score = stats["total_score"] / games_played if games_played > 0 else 0

    performance_text = (
        f"**👤 Name:** {stats['name']}\n\n"
        f"**🎮 Games Played:** {games_played}\n"
        f"**🏆 Games Won:** {stats['games_won']}\n"
        f"**📊 Win Rate:** {win_rate:.2f}%\n"
        f"**⭐ Total Score:** {stats['total_score']}\n"
        f"**🔢 Average Score:** {avg_score:.2f}\n"
        f"**🔠 Correct Guessed Letters:** {stats['guessed_letters']}\n"
        f"**📝 Solved Words:** {stats['solved_words']}\n"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🆔 General Info", callback_data=f"stats_general_{user_id}")],
        [InlineKeyboardButton("📈 Game Performance", callback_data=f"stats_performance_{user_id}")],
        [InlineKeyboardButton("🏅 Achievements", callback_data=f"stats_achievements_{user_id}")]
    ])

    await message.reply_text(f"📊 **Your Hangman Statistics**\n\n{performance_text}", reply_markup=keyboard)

@app.on_message(filters.command("play"))
async def play_command(client, message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    if user_id in player_stats and player_stats[user_id]["name"] != user_name:
        update_player_name(user_id, user_name)

    difficulty_emojis = user_configs.get(user_id, {}).get("difficulty", default_emoji_sets["difficulty"])

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Daily Challenge 📅", callback_data=f"daily_challenge_{user_id}")],
        [InlineKeyboardButton("Animals 🐾", callback_data=f"category_animals_{user_id}")],
        [InlineKeyboardButton("Countries 🌎", callback_data=f"category_countries_{user_id}")],
        [InlineKeyboardButton("Foods 🍔", callback_data=f"category_foods_{user_id}")],
        [InlineKeyboardButton("Fruits 🍎", callback_data=f"category_fruits_{user_id}")],
        [InlineKeyboardButton("Vegetables 🥕", callback_data=f"category_vegetables_{user_id}")],
        [InlineKeyboardButton("Colors 🎨", callback_data=f"category_colors_{user_id}")],
        [InlineKeyboardButton("Sports ⚽️", callback_data=f"category_sports_{user_id}")],
        [InlineKeyboardButton("Occupations 🧑‍💼", callback_data=f"category_occupations_{user_id}")],
        [InlineKeyboardButton("Actions 🏃", callback_data=f"category_actions_{user_id}")],
        [InlineKeyboardButton("Adjectives ✨", callback_data=f"category_adjectives_{user_id}")]
    ])
    sent_message = await message.reply_text("🎮 **Hangman Game!** 🎉\n\n"
        "Select a category or try the daily challenge! 📚", reply_markup=keyboard)
    
    track_game_setup(user_id, "category_selection", message.chat.id, sent_message.id)

@app.on_callback_query(filters.regex(r"^daily_challenge"))
async def daily_challenge_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    original_user_id = callback_query.data.split("_")[-1]

    if user_id != original_user_id:
        await callback_query.answer("Oops! 🚫 This is not your game. Start your own with /play!", show_alert=True)
        return

    if not can_play_daily_challenge(user_id):
        await callback_query.answer("You've already played today's challenge. Come back tomorrow!", show_alert=True)
        return

    current_date = datetime.now().date()
    if "date" not in daily_challenges or daily_challenges["date"] != current_date:
        generate_daily_challenge()

    word = daily_challenges["word"]
    category = daily_challenges["category"]
    difficulty = daily_challenges["difficulty"]

    sent_message = await callback_query.message.edit_text(
        "🎮 Setting up your daily challenge...",
    )

    create_new_game(user_id, word, category, difficulty, callback_query.message.chat.id, sent_message.id)
    
    game = games[user_id]
    game["is_daily_challenge"] = True

    initial_message = format_message(word, set(), game["attempts"], category, difficulty, 0, user_id)
    initial_message = "🌟 Daily Challenge 🌟\n\n" + initial_message
    
    try:
        await client.edit_message_text(
            chat_id=game["chat_id"],
            message_id=game["message_ids"][-1], 
            text=initial_message,
            reply_markup=create_keyboard_markup(game["keyboard_letters"], set(), word, user_id)
        )
    except Exception as e:
        print(f"Error in daily_challenge_callback: {e}")
        if user_id in games:
            del games[user_id]
        if user_id in game_activity:
            del game_activity[user_id]
        await callback_query.answer("An error occurred. Please try again.", show_alert=True)
        return

    game_activity[user_id] = datetime.now()
    await callback_query.answer("Daily challenge started!")

@app.on_callback_query(filters.regex(r"^guess_"))
async def guess_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    game_user_id = callback_query.data.split("_")[-1]

    if user_id != game_user_id:
        await callback_query.answer("Oops! 🚫 This is not your game. Start your own with /play!", show_alert=True)
        return

    if game_user_id not in games:
        await callback_query.answer("🚫 No active game found. Please start a new game with /play.", show_alert=True)
        return

    game = games[game_user_id]
    letter = callback_query.data.split("_")[1]

    game_activity[game_user_id] = datetime.now()  

    if letter in game["guessed_letters"]:
        await callback_query.answer("You've already guessed this letter!", show_alert=True)
        return

    game["guessed_letters"].add(letter)

    if letter not in game["word"]:
        game["attempts"] -= 1

    game["score"] = calculate_score(game["word"], game["attempts"], game["difficulty"])

    if set(game["word"]) <= game["guessed_letters"]:
        await end_game(client, callback_query.message, game_user_id, won=True)
    elif game["attempts"] == 0:
        await end_game(client, callback_query.message, game_user_id, won=False)
    else:
        try:
            await client.edit_message_text(
                chat_id=game["chat_id"],
                message_id=game["message_ids"][-1],  
                text=format_message(game["word"], game["guessed_letters"], game["attempts"], game["category"], game["difficulty"], game["score"], game_user_id),
                reply_markup=create_keyboard_markup(game["keyboard_letters"], game["guessed_letters"], game["word"], game_user_id)
            )
        except MessageNotModified:
            pass
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.edit_message_text(
                chat_id=game["chat_id"],
                message_id=game["message_ids"][-1], 
                text=format_message(game["word"], game["guessed_letters"], game["attempts"], game["category"], game["difficulty"], game["score"], game_user_id),
                reply_markup=create_keyboard_markup(game["keyboard_letters"], game["guessed_letters"], game["word"], game_user_id)
            )

    await callback_query.answer()


@app.on_callback_query(filters.regex(r"^hint_"))
async def hint_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    game_user_id = callback_query.data.split("_")[-1]

    if user_id != game_user_id:
        await callback_query.answer("Oops! 🚫 This is not your game. Start your own with /play!", show_alert=True)
        return

    if game_user_id not in games:
        await callback_query.answer("🚫 No active game found. Please start a new game with /play.", show_alert=True)
        return

    game = games[game_user_id]
    unguessed_letters = set(game["word"]) - game["guessed_letters"]
    if not unguessed_letters:
        await callback_query.answer("No more hints available!", show_alert=True)
        return

    hint = random.choice(list(unguessed_letters))
    game["guessed_letters"].add(hint)
    game["attempts"] -= 1
    game["score"] = calculate_score(game["word"], game["attempts"], game["difficulty"])

    game_activity[game_user_id] = datetime.now()

    if set(game["word"]) <= game["guessed_letters"]:
        await end_game(client, callback_query.message, game_user_id, won=True)
    elif game["attempts"] == 0:
        await end_game(client, callback_query.message, game_user_id, won=False)
    else:
        formatted_message = format_message(game["word"], game["guessed_letters"], game["attempts"], game["category"], game["difficulty"], game["score"], game_user_id)
        try:
            await client.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=game["message_ids"][-1], 
                text=formatted_message,
                reply_markup=create_keyboard_markup(game["keyboard_letters"], game["guessed_letters"], game["word"], game_user_id)
            )
        except MessageNotModified:
            pass
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=game["message_ids"][-1], 
                text=formatted_message,
                reply_markup=create_keyboard_markup(game["keyboard_letters"], game["guessed_letters"], game["word"], game_user_id)
            )

    await callback_query.answer(f"Hint: The word contains the letter '{hint}'")


@app.on_callback_query(filters.regex(r"^category_"))
async def category_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    category, original_user_id = callback_query.data.split("_")[1:]

    if user_id != original_user_id:
        await callback_query.answer("Oops! 🚫 This is not your game. Start your own with /play!", show_alert=True)
        return

    difficulty_emojis = user_configs.get(user_id, {}).get("difficulty", default_emoji_sets["difficulty"])
    easy_emoji, medium_emoji, hard_emoji = difficulty_emojis

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Easy {easy_emoji}", callback_data=f"difficulty_{category}_easy_{user_id}")],
        [InlineKeyboardButton(f"Medium {medium_emoji}", callback_data=f"difficulty_{category}_medium_{user_id}")],
        [InlineKeyboardButton(f"Hard {hard_emoji}", callback_data=f"difficulty_{category}_hard_{user_id}")]
    ])
    edited_message = await callback_query.message.edit_text(f"Choose difficulty for {category}:", reply_markup=keyboard)
    
    track_game_setup(user_id, "difficulty_selection", edited_message.chat.id, edited_message.id)


@app.on_callback_query(filters.regex(r"^difficulty_"))
async def difficulty_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    _, category, difficulty, game_user_id = callback_query.data.split("_")

    if user_id != game_user_id:
        await callback_query.answer("Oops! 🚫 This is not your game. Start your own with /play!", show_alert=True)
        return

    word = get_random_word(category, difficulty)
    
    sent_message = await callback_query.message.edit_text(
        "🎮 Setting up your game...",
    )
    
    create_new_game(user_id, word, category, difficulty, callback_query.message.chat.id, sent_message.id)
    
    game = games[user_id]
    initial_message = format_message(word, set(), game["attempts"], category, difficulty, 0, user_id)
    
    game_message = await client.edit_message_text(
        chat_id=game["chat_id"],
        message_id=sent_message.id,
        text=initial_message,
        reply_markup=create_keyboard_markup(game["keyboard_letters"], set(), word, user_id)
    )
    
    track_game_setup(user_id, "game_started", game_message.chat.id, game_message.id)
    
@app.on_callback_query(filters.regex(r"^stats_"))
async def stats_section_callback(client, callback_query):
    global last_pressed_section

    user_id = str(callback_query.from_user.id)
    stats_user_id = callback_query.data.split("_")[-1]

    if user_id != stats_user_id:
        await callback_query.answer("🚫 These are not your stats! Please view your own stats with /stats.", show_alert=True)
        return

    stats = player_stats.get(user_id, {
        "games_played": 0,
        "games_won": 0,
        "total_score": 0,
        "guessed_letters": 0,
        "solved_words": 0,
        "name": callback_query.from_user.first_name,
        "achievements": set()
    })
    games_played = stats["games_played"]
    win_rate = (stats["games_won"] / games_played * 100) if games_played > 0 else 0
    avg_score = stats["total_score"] / games_played if games_played > 0 else 0

    section = callback_query.data.split("_")[1]
    last_pressed_section = section

    if section == "general":
        section_text = (
            f"**👤 Name:** {stats['name']}\n\n"
            f"**🆔 User ID:** `{user_id}`\n"
        )
    elif section == "performance":
        section_text = (
            f"**👤 Name:** {stats['name']}\n\n"
            f"**🎮 Games Played:** {games_played}\n"
            f"**🏆 Games Won:** {stats['games_won']}\n"
            f"**📊 Win Rate:** {win_rate:.2f}%\n"
            f"**⭐ Total Score:** {stats['total_score']}\n"
            f"**🔢 Average Score:** {avg_score:.2f}\n"
            f"**🔠 Correct Guessed Letters:** {stats['guessed_letters']}\n"
            f"**📝 Solved Words:** {stats['solved_words']}\n"
        )
    elif section == "achievements":
        achievements = stats.get("achievements", set())
        all_achievements = {
            "first_win": "🏆 First Win",
            "streak_7": "🔥 7-Day Streak",
            "games_50": "🎮 50 Games Played",
            "words_20": "📚 20 Words Solved",
            "perfect_game": "💯 Perfect Game"
        }
        if achievements:
            section_text = "**🏅 Your Achievements:**\n\n"
            for achievement in sorted(achievements):
                section_text += f"{all_achievements.get(achievement, achievement)}\n"
        else:
            section_text = "You haven't earned any achievements yet. Keep playing to unlock them!"

        locked_achievements = set(all_achievements.keys()) - achievements
        if locked_achievements:
            section_text += "\n**🔒 Locked Achievements:**\n\n"
            for achievement in sorted(locked_achievements):
                section_text += f"{all_achievements[achievement]} (Locked)\n"

    general_button_text = "🆔 General Info"
    performance_button_text = "📈 Game Performance"
    achievements_button_text = "🏅 Achievements"

    if last_pressed_section == "general":
        general_button_text = "○ " + general_button_text + " ○"
    elif last_pressed_section == "performance":
        performance_button_text = "○ " + performance_button_text + " ○"
    elif last_pressed_section == "achievements":
        achievements_button_text = "○ " + achievements_button_text + " ○"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(general_button_text, callback_data=f"stats_general_{user_id}")],
        [InlineKeyboardButton(performance_button_text, callback_data=f"stats_performance_{user_id}")],
        [InlineKeyboardButton(achievements_button_text, callback_data=f"stats_achievements_{user_id}")]
    ])

    try:
        await callback_query.message.edit_text(section_text, reply_markup=keyboard)
    except MessageNotModified:
        pass

    await callback_query.answer()

tips = [
    "💡 Tip: Keep playing to improve your rank!",
    "🏅 You're on fire! Keep it up to climb even higher!",
    "🚀 Great job! Push further to reach the top!",
    "⭐ Awesome effort! Continue to shine and rise!",
    "📈 You're doing great! Keep playing to boost your rank!",
    "🌟 Fantastic work! Keep going to see your name at the top!",
    "🏆 Excellent performance! Stay persistent and you'll get to the top!",
    "🎯 Impressive score! Keep aiming higher!",
    "👏 Well done! Keep playing to dominate the leaderboard!",
    "🎉 Great progress! Keep the momentum to improve your ranking!"
]

@app.on_message(filters.command("config"))
async def config_command(client, message):
    user_id = str(message.from_user.id)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎭 Customize Emojis", callback_data=f"config_emoji_{user_id}")],
        [InlineKeyboardButton("🔄 Reset to Default", callback_data=f"config_reset_{user_id}")],
        [InlineKeyboardButton("❌ Close Configuration", callback_data=f"config_close_{user_id}")]
    ])
    await message.reply_text("⚙️ **Hangman Configuration**\n\nCustomize your game experience:", reply_markup=keyboard)


@app.on_callback_query(filters.regex(r"^config_"))
async def config_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    data_parts = callback_query.data.split("_")
    config_type = data_parts[1]
    original_user_id = data_parts[2] if len(data_parts) > 2 else user_id

    if not is_original_user(callback_query, original_user_id):
        await callback_query.answer("bad boy 🤡.", show_alert=True)
        return

    if config_type == "emoji":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❤️ Lives Emojis", callback_data=f"config_lives_{user_id}")],
            [InlineKeyboardButton("⌨️ Keyboard Emojis", callback_data=f"config_keyboard_{user_id}")],
            [InlineKeyboardButton("🔥 Difficulty Emojis", callback_data=f"config_difficulty_{user_id}")],
            [InlineKeyboardButton("« Back", callback_data=f"config_back_{user_id}")]
        ])
        await callback_query.message.edit_text("🎨 **Emoji Customization**\n\nChoose which emojis to customize:", reply_markup=keyboard)
    elif config_type == "reset":
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, reset", callback_data=f"confirm_reset_{user_id}")],
            [InlineKeyboardButton("❌ No, cancel", callback_data=f"config_back_{user_id}")]
        ])
        await callback_query.message.edit_text("🔄 **Reset Configuration**\n\nAre you sure you want to reset your configuration to default?", reply_markup=confirm_keyboard)
    elif config_type == "close":
        await callback_query.message.edit_text("⚙️ Configuration closed. Use /play to start a new game!")
    elif config_type in ["lives", "keyboard", "difficulty"]:
        current_emojis = user_configs.get(user_id, {}).get(config_type, default_emoji_sets[config_type])
        options = emoji_options[config_type]

        keyboard = []
        for option in options:
            if config_type == "keyboard":
                row = [
                    InlineKeyboardButton(f"{option[0]} {'✓' if option[0] == current_emojis[0] else ''}", callback_data=f"set_{config_type}_0_{option[0]}_{user_id}"),
                    InlineKeyboardButton(f"{option[1]} {'✓' if option[1] == current_emojis[1] else ''}", callback_data=f"set_{config_type}_1_{option[1]}_{user_id}")
                ]
            else:
                row = [
                    InlineKeyboardButton(f"{emoji} {'✓' if emoji == current_emojis[i] else ''}", callback_data=f"set_{config_type}_{i}_{emoji}_{user_id}")
                    for i, emoji in enumerate(option)
                ]
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("« Back", callback_data=f"config_emoji_{user_id}")])

        title = {
            "lives": "❤️ Lives Emojis",
            "keyboard": "⌨️ Keyboard Emojis",
            "difficulty": "🔥 Difficulty Emojis"
        }[config_type]

        await callback_query.message.edit_text(
            f"🎨 **{title} Customization**\n\nTap an emoji to select it:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif config_type == "back":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎭 Customize Emojis", callback_data=f"config_emoji_{user_id}")],
            [InlineKeyboardButton("🔄 Reset to Default", callback_data=f"config_reset_{user_id}")],
            [InlineKeyboardButton("❌ Close Configuration", callback_data=f"config_close_{user_id}")]
        ])
        await callback_query.message.edit_text("⚙️ **Hangman Configuration**\n\nCustomize your game experience:", reply_markup=keyboard)

    await callback_query.answer()

@app.on_callback_query(filters.regex(r"^confirm_reset_"))
async def confirm_reset_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    original_user_id = callback_query.data.split("_")[-1]

    if not is_original_user(callback_query, original_user_id):
        await callback_query.answer("bad boy 🤡.", show_alert=True)
        return

    if user_id in user_configs:
        del user_configs[user_id]
        save_user_configs(user_configs)
    await callback_query.answer("Configuration reset to default", show_alert=True)
    await callback_query.message.edit_text("Configuration reset to default. Use /play to start a new game!")

@app.on_callback_query(filters.regex(r"^set_"))
async def set_emoji_callback(client, callback_query):
    data_parts = callback_query.data.split("_")
    config_type = data_parts[1]
    index = int(data_parts[2])
    new_emoji = data_parts[3]
    user_id = data_parts[4]

    if not is_original_user(callback_query, user_id):
        await callback_query.answer("bad boy 🤡.", show_alert=True)
        return

    if user_id not in user_configs:
        user_configs[user_id] = {}
    if config_type not in user_configs[user_id]:
        user_configs[user_id][config_type] = default_emoji_sets[config_type].copy()

    user_configs[user_id][config_type][index] = new_emoji
    save_user_configs(user_configs)

    await callback_query.answer(f"{config_type.capitalize()} emoji at position {index + 1} updated to {new_emoji}")

    current_emojis = user_configs[user_id][config_type]
    options = emoji_options[config_type]

    keyboard = []
    for option in options:
        if config_type == "keyboard":
            row = [
                InlineKeyboardButton(f"{option[0]} {'✓' if option[0] == current_emojis[0] else ''}",
                                     callback_data=f"set_{config_type}_0_{option[0]}_{user_id}"),
                InlineKeyboardButton(f"{option[1]} {'✓' if option[1] == current_emojis[1] else ''}",
                                     callback_data=f"set_{config_type}_1_{option[1]}_{user_id}")
            ]
        else:
            row = [
                InlineKeyboardButton(f"{emoji} {'✓' if emoji == current_emojis[i] else ''}",
                                     callback_data=f"set_{config_type}_{i}_{emoji}_{user_id}")
                for i, emoji in enumerate(option)
            ]
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("« Back", callback_data=f"config_emoji_{user_id}")])

    title = {
        "lives": "❤️ Lives Emojis",
        "keyboard": "⌨️ Keyboard Emojis",
        "difficulty": "🔥 Difficulty Emojis"
    }[config_type]

    await callback_query.message.edit_text(
        f"🎨 **{title} Customization**\n\nTap an emoji to select it:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@app.on_callback_query(filters.regex(r"^leaderboard_"))
async def leaderboard_callback(client, callback_query):
    global last_pressed_button

    user_id = str(callback_query.from_user.id)
    user_name = callback_query.from_user.first_name
    
    if user_id in player_stats and player_stats[user_id]["name"] != user_name:
        update_player_name(user_id, user_name)

    leaderboard_type = callback_query.data.split("_")[1]
    last_pressed_button = leaderboard_type

    if leaderboard_type == "daily":
        title = "📅 **Daily Challenge Leaderboard**"
        sorted_data = get_daily_challenge_leaderboard()
        format_entry = lambda rank, name, value: f"{rank_emoji(rank)} **{name}**: {value} points"
    elif leaderboard_type == "wins":
        title = "🏆 **Most Wins Leaderboard**"
        sorted_data = sorted(
            [(uid, stats["games_won"]) for uid, stats in player_stats.items() if "games_won" in stats],
            key=itemgetter(1),
            reverse=True
        )[:10]
        format_entry = lambda rank, name, value: f"{rank_emoji(rank)} **{name}**: {value} wins"
    elif leaderboard_type == "scores":
        title = "🔥 **Highest Scores Leaderboard**"
        sorted_data = sorted(
            [(uid, max(stats.get("scores", [0]))) for uid, stats in player_stats.items()],
            key=itemgetter(1),
            reverse=True
        )[:10]
        format_entry = lambda rank, name, value: f"{rank_emoji(rank)} **{name}**: {value} points"
    else:
        await callback_query.answer("Invalid leaderboard type", show_alert=True)
        return

    leaderboard_text = f"{title}\n\n"
    for rank, (uid, value) in enumerate(sorted_data, start=1):
        player_name = player_stats[uid].get("name", "Unknown Player")
        leaderboard_text += format_entry(rank, player_name, value) + "\n"

        if rank <= 3:
            extra_info = get_player_extra_info(uid, leaderboard_type)
            leaderboard_text += f"  {extra_info}\n"

        leaderboard_text += "\n"

    if not sorted_data:
        leaderboard_text += "No data available yet. Start playing to climb the leaderboard!\n"

    leaderboard_text += "\n" + random.choice(tips)

    daily_button_text = "📅 Daily Challenge"
    wins_button_text = "🏆 Most Wins"
    scores_button_text = "🔥 Highest Scores"

    if last_pressed_button == "daily":
        daily_button_text = "○ " + daily_button_text + " ○"
    elif last_pressed_button == "wins":
        wins_button_text = "○ " + wins_button_text + " ○"
    elif last_pressed_button == "scores":
        scores_button_text = "○ " + scores_button_text + " ○"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(daily_button_text, callback_data="leaderboard_daily")],
        [InlineKeyboardButton(wins_button_text, callback_data="leaderboard_wins")],
        [InlineKeyboardButton(scores_button_text, callback_data="leaderboard_scores")]
    ])

    try:
        await callback_query.message.edit_text(leaderboard_text, reply_markup=keyboard)
    except MessageNotModified:
        pass

    await callback_query.answer()

def rank_emoji(rank):
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    else:
        return f"{rank}."

def get_player_extra_info(user_id, leaderboard_type):
    stats = player_stats[user_id]
    if leaderboard_type == "daily":
        return f"📊 Win Rate: {(stats['games_won'] / stats['games_played'] * 100):.1f}% | 🔥 Streak: {stats['streak']}"
    elif leaderboard_type == "wins":
        return f"🎮 Games Played: {stats['games_played']} | 📊 Win Rate: {(stats['games_won'] / stats['games_played'] * 100):.1f}%"
    elif leaderboard_type == "scores":
        return f"🚀 Total Score: {stats['total_score']} | 📊 Win Rate: {(stats['games_won'] / stats['games_played'] * 100):.1f}%"

hangman_won_graphic = (
    "```\n"
    "   +---+\n"
    "   |   |\n"
    "       |\n"
    "       |\n"
    "  \\O/  |\n"
    "   |   |\n"
    "  / \\  |\n"
    "=========\n"
    "```\n"
)

hangman_lost_graphic = (
    "```\n"
    "   +---+\n"
    "   |   |\n"
    "   O   |\n"
    "  /|\\  |\n"
    "  / \\  |\n"
    "       |\n"
    "=========\n"
    "```\n"
)

async def end_game(client, message, user_id, won):
    game = games[user_id]
    user_name = game["user_name"]

    guessed_letter_count = len(game["guessed_letters"])
    solved_word = set(game["word"]) <= game["guessed_letters"]

    update_player_stats(
        user_id,
        user_name,
        won,
        game["score"],
        guessed_letter_count=guessed_letter_count,
        solved_word=solved_word
    )

    update_streak(user_id)
    new_achievements = check_achievements(user_id)

    if game.get("is_daily_challenge", False):
        final_score = update_daily_challenge_score(user_id, game["score"])
        game["score"] = final_score

    if won:
        end_message = (
        f"🎉 **Congratulations, {user_name}!** 🎊🥳\n\n"
        f"You saved the man by guessing the word: **{game['word']}**\n"
        f"{hangman_won_graphic}\n"
        f"🏷️ **Category:** {game['category']}\n"
        f"⚙️ **Difficulty:** {game['difficulty']}\n"
        f"🏆 **Score:** {game['score']}\n"
        f"🔥 **Streak:** {player_stats[user_id]['streak']} days\n\n"
    )
    else:
        end_message = (
        f"😔 **Oh no, {user_name}!** The man was hanged.\n\n"
        f"The word was: **{game['word']}**\n"
        f"{hangman_lost_graphic}\n"
        f"🏷️ **Category:** {game['category']}\n"
        f"⚙️ **Difficulty:** {game['difficulty']}\n"
        f"🏆 **Score:** {game['score']}\n"
        f"🔥 **Streak:** {player_stats[user_id]['streak']} days\n\n"
    )

    if new_achievements:
        end_message += f"🏅 **New Achievements:**\n" + "\n".join(new_achievements) + "\n\n"

    end_message += f"🌟 **{'Great job! Keep it up!' if won else 'Better luck next time!'}** 🌟"

    if game.get("is_daily_challenge", False):
        end_message += f"\n\n📊 Check /ranking to see your ranking!"

    play_again_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Again", callback_data=f"play_again_{user_id}")]
    ])

    try:
        await client.edit_message_text(
            chat_id=game["chat_id"],
            message_id=game["message_ids"][-1],  
            text=end_message,
            reply_markup=play_again_keyboard
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await client.edit_message_text(
            chat_id=game["chat_id"],
            message_id=game["message_ids"][-1], 
            text=end_message,
            reply_markup=play_again_keyboard
        )

    del games[user_id]
    if user_id in game_activity:
        del game_activity[user_id]


@app.on_callback_query(filters.regex(r"^play_again_"))
async def play_again_callback(client, callback_query):
    user_id = str(callback_query.from_user.id)
    original_user_id = callback_query.data.split("_")[-1]

    if user_id != original_user_id:
        await callback_query.answer("Oops! 🚫 This is not your game. Start your own with /play!", show_alert=True)
        return

    difficulty_emojis = user_configs.get(user_id, {}).get("difficulty", default_emoji_sets["difficulty"])

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Daily Challenge 📅", callback_data=f"daily_challenge_{user_id}")],
        [InlineKeyboardButton("Animals 🐾", callback_data=f"category_animals_{user_id}")],
        [InlineKeyboardButton("Countries 🌎", callback_data=f"category_countries_{user_id}")],
        [InlineKeyboardButton("Foods 🍔", callback_data=f"category_foods_{user_id}")],
        [InlineKeyboardButton("Fruits 🍎", callback_data=f"category_fruits_{user_id}")],
        [InlineKeyboardButton("Vegetables 🥕", callback_data=f"category_vegetables_{user_id}")],
        [InlineKeyboardButton("Colors 🎨", callback_data=f"category_colors_{user_id}")],
        [InlineKeyboardButton("Sports ⚽️", callback_data=f"category_sports_{user_id}")],
        [InlineKeyboardButton("Occupations 🧑‍💼", callback_data=f"category_occupations_{user_id}")],
        [InlineKeyboardButton("Actions 🏃", callback_data=f"category_actions_{user_id}")],
        [InlineKeyboardButton("Adjectives ✨", callback_data=f"category_adjectives_{user_id}")]
    ])

    await callback_query.message.edit_text(
        "🎮 **Hangman Game!** 🎉\n\nSelect a category or try the daily challenge! 📚",
        reply_markup=keyboard
    )
    await callback_query.answer()
    
    
@app.on_message(filters.command("ranking"))
async def leaderboard_command(client, message):
    user_id = str(message.from_user.id)
    user_name = message.from_user.first_name
    
    if user_id in player_stats and player_stats[user_id]["name"] != user_name:
        update_player_name(user_id, user_name)

    leaderboard_type = "wins"
    title = "🥇 **Most Wins Leaderboard**"
    sorted_data = sorted(
        [(uid, stats["games_won"]) for uid, stats in player_stats.items() if "games_won" in stats],
        key=itemgetter(1),
        reverse=True
    )[:10]
    format_entry = lambda rank, name, value: f"{rank_emoji(rank)} **{name}**: {value} wins"

    leaderboard_text = f"{title}\n\n"
    for rank, (uid, value) in enumerate(sorted_data, start=1):
        player_name = player_stats[uid].get("name", "Unknown Player")
        leaderboard_text += format_entry(rank, player_name, value) + "\n"

        if rank <= 3:
            extra_info = get_player_extra_info(uid, leaderboard_type)
            leaderboard_text += f"  {extra_info}\n"

        leaderboard_text += "\n"

    if not sorted_data:
        leaderboard_text += "No data available yet. Start playing to climb the leaderboard!\n"

    leaderboard_text += "\n💡 Tip: Keep playing to improve your rank!"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏆 Daily Challenge", callback_data="leaderboard_daily")],
        [InlineKeyboardButton("🥇 Most Wins", callback_data="leaderboard_wins")],
        [InlineKeyboardButton("🌟 Highest Scores", callback_data="leaderboard_scores")]
    ])

    await message.reply_text(leaderboard_text, reply_markup=keyboard)

user_configs = load_user_configs()

load_player_stats()


async def on_startup():
    print("Hangman bot has started!")
    asyncio.create_task(check_inactive_games())

async def main():
    await app.start()
    await on_startup()
    await idle()

if __name__ == "__main__":
    print('Hangman bot is starting...')
    app.run(main())
