# 🎮 Telegram Hangman Bot

A feature-rich, interactive Hangman game bot for Telegram with customizable emojis, daily challenges, achievements, and leaderboards!

## ✨ Features

- 🎯 Multiple Word Categories:
  - 🐾 Animals
  - 🌎 Countries
  - 🍔 Foods
  - 🍎 Fruits
  - 🥕 Vegetables
  - 🎨 Colors
  - ⚽️ Sports
  - 🧑‍💼 Occupations
  - 🏃 Actions
  - ✨ Adjectives

- 📅 Daily Challenges:
  - New word every day
  - Special scoring system
  - Daily leaderboard
  - Streak tracking

- 🎨 Customizable Experience:
  - 💖 Lives display emojis
  - ⌨️ Keyboard button emojis
  - 🔥 Difficulty level emojis

- 🏆 Achievement System:
  - 🏆 First Win
  - 🔥 7-Day Streak
  - 🎮 50 Games Played
  - 📚 20 Words Solved
  - 💯 Perfect Game

- 📊 Comprehensive Statistics:
  - Games played and won
  - Win rate
  - Total score
  - Guessed letters
  - Solved words
  - Current streak

- 🏅 Multiple Leaderboards:
  - 📅 Daily Challenge rankings
  - 🏆 Most Wins
  - 🔥 Highest Scores

## 🎯 Commands

- `/hangman` - Start the bot and see available commands
- `/play` - Start a new game
- `/stats` - View your game statistics
- `/ranking` - Check the leaderboards
- `/config` - Customize game emojis

## 🎲 Gameplay Features

- 3️⃣ Difficulty Levels:
  - 😊 Easy
  - 😐 Medium
  - 😈 Hard

- 💡 Hint System
- ⏱️ Auto-cleanup of inactive games
- 🔄 Play Again option
- 📝 Word progress display
- 🎯 Dynamic keyboard generation

## 🛠️ Setup Requirements

1. Python
2. Required packages:
   ```
   hydrogram
   asyncio
   ```

3. Environment variables:
   ```
   API_ID - Telegram API ID
   API_HASH - Telegram API Hash
   BOT_TOKEN_HANGMAN - Your bot token from @BotFather
   ```

## 💾 Data Storage

The bot maintains several JSON files for persistent storage:
- `users_config.json` - User emoji preferences
- `player_stats.json` - Player statistics and achievements
- `daily_challenges.json` - Daily challenge data

## 🔒 Security Features

- User verification for game interactions
- Flood control handling
- Error handling and graceful degradation

## 🎨 Customization Options

### Lives Emojis
- 💚 ❤️ 💔
- 🧔‍♂️ 💀 ⚰️
- 🌱 🍃 🍂
- 🍜 🥢 🥣

### Keyboard Emojis
- 🎯 🚫
- ✅ ❌
- 🟢 🔴
- 👍 👎
- And more!

### Difficulty Emojis
- 😊 😐 😈
- 😃 😑 😠
- 🤡 😕 😡
- And more!

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📝 License

This project is open source and available under the MIT License.

---
Made with ❤️ for Telegram gamers 