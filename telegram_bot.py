import asyncio
import json
import logging
import threading
from telegram import Update
from telegram import Bot as BotAPI
from telegram.ext import (ApplicationBuilder, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from users import User
from scrapper import ElearnScrapper, LoginError


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, encoding="utf-8",
                        filename="./logs/bot.log", format=f"%(levelname)s   %(asctime)s  \n%(message)s \n{'='*100}\n", filemode="w")


class TelegramBot:
    with open("config.json", "r") as f:
        config = json.load(f)
        token, admin_chat_id = config["telegram_bot"].values()
        admin_chat_id = int(admin_chat_id["id"])
        del config
    botapi = BotAPI(token=token)
    update_timer = {"remaining": 0, "interval": 15} #in minutes

    notifier_is_running = True

    def __init__(self, **kwargs):

        self.app = ApplicationBuilder().token(self.token).build()

        self.attach_handlers()
        self.app.add_handler(MessageHandler(filters.COMMAND, self._unknown))

    def attach_handlers(self):
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("email", self._email))
        self.app.add_handler(CommandHandler("password", self._password))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler(
            "toggle_notifications", self._toggle_active))
        self.app.add_handler(CommandHandler("next_update", self._remaining_time))

    async def _start(self, update: Update, context: ContextTypes):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Welcome to Elearning Bot.\nThis bot will notify you when new content is available on elearning.\nType /help for a list of commands.")
        user = TelegramBot.get_user(update.effective_chat.id)
        if user.get_email() is None:
            await context.bot.send_message(chat_id=user.get_chat_id(), text="Please set your email address using the /email command.")
        if user.get_password() is None:
            await context.bot.send_message(chat_id=user.get_chat_id(), text="Please set your password using the /password command.")

    ## User related commands

    async def _email(self, update: Update, context: ContextTypes):
        user = TelegramBot.get_user(update.effective_chat.id)

        if len(context.args) > 0:
            try:
                user.set_email(context.args[0])
                if user.get_password() is not None:
                    user.set_is_active(True)
                User.update_user(user)
            except ValueError or TypeError as e:
                await context.bot.send_message(chat_id=user.get_chat_id(), text=f"Invalid email address. {e}")
                return
            await context.bot.send_message(chat_id=user.get_chat_id(), text=f"Email updated to {user.get_email()}")
        elif user.get_email() is None:
            await context.bot.send_message(chat_id=user.get_chat_id(), text="No email address set.")
        else:
            await context.bot.send_message(chat_id=user.get_chat_id(), text=f"Email address: {user.get_email()}")

    async def _password(self, update: Update, context: ContextTypes):
        user = TelegramBot.get_user(update.effective_chat.id)
        if len(context.args) > 0:
            try:
                user.set_password(context.args[0])
                if user.get_email() is not None:
                    user.set_is_active(True)
                User.update_user(user)
            except ValueError or TypeError as e:
                await context.bot.send_message(chat_id=user.get_chat_id(), text=f"Invalid password: {e}")
                return
            await context.bot.send_message(chat_id=user.get_chat_id(), text="Password updated.\n For your security, please delete the password from the chat.")
        elif user.get_password() is None:
            await context.bot.send_message(chat_id=user.get_chat_id(), text="No password set.")
        else:
            await context.bot.send_message(chat_id=user.get_chat_id(), text="Password set.")

    async def _toggle_active(self, update: Update, context: ContextTypes):
        user = TelegramBot.get_user(update.effective_chat.id)
        user.set_is_active(not user.get_is_active())
        User.update_user(user)
        if user.get_is_active():
            text = "You are now active. You will receive notifications from the bot."
        else:
            text = "You are now inactive. You will not receive notifications from the bot."
        await context.bot.send_message(chat_id=user.get_chat_id(), text=text)

    ## General commands

    async def _help(self, update: Update, context: ContextTypes):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Commands:\n/start - Start the bot.\n/email - Get or Set your email address.\n/password - Get or Set your password.\n/toggle_notifications - Toggle notifications on or off.\n/help - Show help message.\n/next_update - Show the time remaining until the next update.")

    async def _remaining_time(self, update: Update, context: ContextTypes):
        if not self.notifier_is_running:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="The notifier is currently inactive.")
            return
        if self.update_timer["remaining"] == 0:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Updating...")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Remaining time to next update: {int(self.update_timer['remaining'])} minutes.")

    async def _unknown(self, update: Update, context: ContextTypes):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown command.")
      
    def run(self):
        self.app.run_polling()

    def stop(self):
        self.app.stop()

    @staticmethod
    async def broadcast(text):
        users = User.get_all_users()
        for user in users:
            await TelegramBot.send_message(user.get_chat_id(), text)

    @staticmethod
    async def send_message(chat_id, text):
        async with TelegramBot.botapi:
            await TelegramBot.botapi.send_message(chat_id=chat_id, text=text)

    @staticmethod
    async def send_photo(chat_id, photo_path):
        with open(photo_path, "rb") as f:
            async with TelegramBot.botapi:
                await TelegramBot.botapi.send_photo(chat_id=chat_id, photo=f)
            
    @staticmethod
    async def send_message_to_admin(text):
        await TelegramBot.send_message(TelegramBot.admin_chat_id, text)

    @staticmethod
    def get_user(chat_id: int) -> User:
        res = User.get_users_by("chat_id", chat_id)
        if res is None or len(res) == 0:
            res = User(chat_id=chat_id, is_active=True)
            User.insert_user(res)
        else:
            res = res[0]
        return res

    @staticmethod
    async def countdown(pretext="", posttext=""):
        count = TelegramBot.update_timer["interval"] * 60
        space_size = len(posttext) + len(str(count))
        space = "".ljust(space_size, " ")
        for i in range(count + 1):
            print(f"{pretext}{count - i}{posttext}{space}", end='\r')
            TelegramBot.update_timer["remaining"] = (count - i)/60
            await asyncio.sleep(1)
            if TelegramBot.update_timer["remaining"] <= 0:
                break
        TelegramBot.update_timer["remaining"] = 0
        print("")
        return None


async def notify_users():
    while True:
        if TelegramBot.notifier_is_running:
            active_users = User.get_users_by("active", True)
            for user in active_users:
                scrapper = ElearnScrapper(user)
                try:
                    print(f"Checking for new content for {user.get_chat_id()}")
                    changed_courses = scrapper.get_all_courses_data()
                except LoginError as e:
                    print(e)
                    await TelegramBot.send_message_to_admin(f"Login error for user {user.get_chat_id()}\n{e}")
                    await TelegramBot.send_message(user.get_chat_id(), "Login failed. {e}.")
                    continue
                except Exception as e:
                    print(e)
                    print(e.args)
                    await TelegramBot.send_message_to_admin(f"Error: {e}")
                    continue
                print(f"Found {len(changed_courses)} changed courses for {user.get_chat_id()}")
                for course in changed_courses:
                    if len(course["course_sections"]) == 0:
                        continue
                    await TelegramBot.send_message(user.get_chat_id(), f"New content in {course['course_name']}")
                    for section in course["course_sections"]:
                        for activity in section["activities"]:
                            await TelegramBot.send_message(user.get_chat_id(), f"New activity in ({section['section_name']})")
                            try:
                                await TelegramBot.send_photo(user.get_chat_id(), activity["screen_shot_path"])
                            except FileNotFoundError as e:
                                await TelegramBot.send_message_to_admin(f"FileNotFoundError: {e}")

                del scrapper
            await TelegramBot.countdown("Next check in ", " seconds")
        else:
            await TelegramBot.countdown("Notifications stopped. Next check in ", " seconds")

def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    asyncio.run(notify_users())

if __name__ == "__main__":
    try:
        mythread = threading.Thread(target=run, daemon=True)
        mythread.start()

        bot = TelegramBot()
        bot.run()
    except Exception as e:
        print(e)
        TelegramBot.send_message_to_admin(f"Error: {e}")
        bot.stop()
        exit(1)