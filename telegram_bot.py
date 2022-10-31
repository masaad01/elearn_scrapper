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
        self.app.add_handler(CommandHandler("admin", self._admin))

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
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Commands:\n/start - Start the bot.\n/email - Get or Set your email address.\n   example: /email myemail@just.edu.jo\n/password - Get or Set your password.\n   example: /password mypassword\n/toggle_notifications - Toggle notifications on or off.\n/next_update - Get the time remaining until the next update.")

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

    ## Admin command

    async def _admin(self, update: Update, context: ContextTypes):
        if update.effective_chat.id != self.admin_chat_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Unknown command.")
            return
        if len(context.args) == 0 or context.args[0] == "help":
            await TelegramBot.send_message_to_admin("Admin commands:\n/admin help - Show help message.\n/admin start - Start the notifier.\n/admin stop - Stop the notifier.\n/admin update - Force an update.\n/admin current_interval - show the current update interval.\n/admin change_interval [minutes] - change the update interval.\n/admin users - Show the list of users.\n/admin user [chat_id/email] [value] - show user info.\n/admin block [chat_id/email] [value] - block user.\n/admin unblock [chat_id/email] [value] - unblock user.\n/admin broadcast [message] - broadcast a message to all users.\n/admin send [chat_id/email] [value] [message] - send a message to a user.")
        
        elif context.args[0] == "start":
            if TelegramBot.notifier_is_running:
                await TelegramBot.send_message_to_admin("Notifier already running.")
                return
            TelegramBot.notifier_is_running = True
            await TelegramBot.send_message_to_admin("Notifications started.")

        elif context.args[0] == "stop":
            if not TelegramBot.notifier_is_running:
                await TelegramBot.send_message_to_admin("Notifier already stopped.")
                return
            TelegramBot.notifier_is_running = False
            TelegramBot.update_timer["remaining"] = 0
            await TelegramBot.send_message_to_admin("Notifications stopped.")

        elif context.args[0] == "update":
            if not TelegramBot.notifier_is_running:
                await TelegramBot.send_message_to_admin("Notifier is not running. Use /admin start to start the notifier.")
                return
            if TelegramBot.update_timer["remaining"] == 0:
                await TelegramBot.send_message_to_admin("Currently updating.")
                return
            TelegramBot.update_timer["remaining"] = 0
            await TelegramBot.send_message_to_admin("Updating now...")

        elif context.args[0] == "current_interval":
            await TelegramBot.send_message_to_admin(f"Current interval: {TelegramBot.update_timer['interval']} minutes.")
            
        elif context.args[0] == "change_interval":
            if len(context.args) > 1:
                try:
                    if int(context.args[1]) < 5:
                        raise ValueError
                    self.update_timer["interval"] = int(context.args[1])
                    if self.update_timer["remaining"] > self.update_timer["interval"]:
                        self.update_timer["remaining"] = self.update_timer["interval"]
                    await TelegramBot.send_message_to_admin(f"Update interval changed to {self.update_timer['interval']} minutes.")
                except ValueError:
                    await TelegramBot.send_message_to_admin("Invalid interval.\nInterval must be an integer greater than 5 minutes.")
            else:
                await context.bot.send_message(chat_id=self.admin_chat_id, text="Please specify an interval. (in minutes) (e.g. /admin change_interval 10)")
                        
        elif context.args[0] == "users":
            if len(context.args) == 1 or context.args[1] == "all":
                users = User.get_all_users()
                try:
                    if len(context.args) > 3:
                        end = min(int(context.args[3]), len(users))
                        start = min(int(context.args[2]), end)
                    elif len(context.args) > 2:
                        start = 0
                        end = min(int(context.args[2]), len(users)) - 1
                    else:
                        start = 0
                        end = len(users)
                    users = users[start:end]
                except ValueError:
                    await TelegramBot.send_message_to_admin("Invalid index.")
                    return
                text = f"Users:\n"
                total_users = len(users)
                active_users = 0
                blocked_users = 0
                for user in users:
                    if user.get_is_active():
                        active_users += 1
                    if user.get_is_blocked():
                        blocked_users += 1
                    if user.get_password() is not None:
                        password = "Set"
                    else:
                        password = "Not set"
                    text += f"ID: {user.get_chat_id()}\nEmail: {user.get_email()}\nPassword: {password}\nActive: {user.get_is_active()}\nBlocked: {user.get_is_blocked()}\n{'='*20}\n"
                
                text += f"Total users: {total_users}\nActive users: {active_users}\nBlocked users: {blocked_users}"
                await TelegramBot.send_message_to_admin(text)
            elif context.args[1] == "active":
                users = User.get_users_by("active", True)
                try:
                    if len(context.args) > 3:
                        end = min(int(context.args[3]), len(users))
                        start = min(int(context.args[2]), end)
                    elif len(context.args) > 2:
                        start = 0
                        end = min(int(context.args[2]), len(users)) - 1
                    else:
                        start = 0
                        end = len(users)
                    users = users[start:end]
                except ValueError:
                    await TelegramBot.send_message_to_admin("Invalid index.")
                    return
                text = f"Active users:\n"
                for user in users:
                    text += f"ID: {user.get_chat_id()}\nEmail: {user.get_email()}\nPassword: {password}\nActive: {user.get_is_active()}\nBlocked: {user.get_is_blocked()}\n{'='*20}\n"
                text += f"Total active users: {len(users)}"
                await TelegramBot.send_message_to_admin(text)
            elif context.args[1] == "inactive":
                users = User.get_users_by("active", False)
                try:
                    if len(context.args) > 3:
                        end = min(int(context.args[3]), len(users))
                        start = min(int(context.args[2]), end)
                    elif len(context.args) > 2:
                        start = 0
                        end = min(int(context.args[2]), len(users)) - 1
                    else:
                        start = 0
                        end = len(users)
                    users = users[start:end]
                except ValueError:
                    await TelegramBot.send_message_to_admin("Invalid index.")
                    return
                text = f"Inactive users:\n"
                for user in users:
                    text += f"ID: {user.get_chat_id()}\nEmail: {user.get_email()}\nPassword: {password}\nActive: {user.get_is_active()}\nBlocked: {user.get_is_blocked()}\n{'='*20}\n"
                text += f"Total inactive users: {len(users)}"
                await TelegramBot.send_message_to_admin(text)
            elif context.args[1] == "blocked":
                users = User.get_users_by("blocked", True)
                try:
                    if len(context.args) > 3:
                        end = min(int(context.args[3]), len(users))
                        start = min(int(context.args[2]), end)
                    elif len(context.args) > 2:
                        start = 0
                        end = min(int(context.args[2]), len(users)) - 1
                    else:
                        start = 0
                        end = len(users)
                    users = users[start:end]
                except ValueError:
                    await TelegramBot.send_message_to_admin("Invalid index.")
                    return
                text = f"Blocked users:\n"
                for user in users:
                    text += f"ID: {user.get_chat_id()}\nEmail: {user.get_email()}\nPassword: {password}\nActive: {user.get_is_active()}\nBlocked: {user.get_is_blocked()}\n{'='*20}\n"
                text += f"Total blocked users: {len(users)}"
                await TelegramBot.send_message_to_admin(text)
            elif context.args[1] == "unblocked":
                users = User.get_users_by("blocked", False)
                try:
                    if len(context.args) > 3:
                        end = min(int(context.args[3]), len(users))
                        start = min(int(context.args[2]), end)
                    elif len(context.args) > 2:
                        start = 0
                        end = min(int(context.args[2]), len(users)) - 1
                    else:
                        start = 0
                        end = len(users)
                    users = users[start:end]
                except ValueError:
                    await TelegramBot.send_message_to_admin("Invalid index.")
                    return
                text = f"Unblocked users:\n"
                for user in users:
                    text += f"ID: {user.get_chat_id()}\nEmail: {user.get_email()}\nPassword: {password}\nActive: {user.get_is_active()}\nBlocked: {user.get_is_blocked()}\n{'='*20}\n"
                text += f"Total unblocked users: {len(users)}"
                await TelegramBot.send_message_to_admin(text)
            else:
                await TelegramBot.send_message_to_admin("Invalid argument. Use /admin users [all/active/inactive/blocked/unblocked] [start/length] [end]")
        
        elif context.args[0] == "user":
            if len(context.args) < 3:
                await TelegramBot.send_message_to_admin("Invalid argument. Use /admin user [chat_id/email] [value]")
            else:
                key = context.args[1]
                value = context.args[2]
                if key == "chat_id":
                    try:
                        value = int(value)
                    except ValueError:
                        await TelegramBot.send_message_to_admin("Invalid chat_id.")
                        return
                res = User.get_user_by(key, value)
                if res is None or len(res) == 0:
                    await TelegramBot.send_message_to_admin("User not found.")
                    return
                user = res[0]
                if user.get_password() is None:
                    password = "Not set"
                else:
                    password = "Set"
                text = f"ID: {user.get_chat_id()}\nEmail: {user.get_email()}\nPassword: {password}\nActive: {user.get_is_active()}\nBlocked: {user.get_is_blocked()}\n{'='*20}\n"
                await TelegramBot.send_message_to_admin(text)

        elif context.args[0] == "block":
            if len(context.args) > 2:
                key = context.args[1]
                value = context.args[2]
                if key not in ["chat_id", "email"]:
                    await TelegramBot.send_message_to_admin("Invalid key. Use /admin block [chat_id/email] [value]")
                    return
                if key == "chat_id":
                    try:
                        value = int(value)
                    except ValueError:
                        await TelegramBot.send_message_to_admin("Invalid chat_id.")
                        return
                try:
                    res = User.get_users_by(key, value)
                    if res is None or len(res) == 0:
                        await TelegramBot.send_message_to_admin("User not found.")
                        return
                    user = res[0]
                    if user.get_is_blocked():
                        await TelegramBot.send_message_to_admin("User is already blocked.")
                        return
                    user.set_is_blocked(True)
                    User.update_user(user)
                    await TelegramBot.send_message_to_admin(f"User {value} blocked.")
                except Exception as e:
                    await TelegramBot.send_message_to_admin(f"Invalid user ID.\n{e}")
            else:
                await TelegramBot.send_message_to_admin("Please specify a user ID. Use /admin block [chat_id/email] [value]")
        
        elif context.args[0] == "unblock":
            if len(context.args) > 2:
                key = context.args[1]
                value = context.args[2]
                if key not in ["chat_id", "email"]:
                    await TelegramBot.send_message_to_admin("Invalid key. Use /admin unblock [chat_id/email] [value]")
                    return
                if key == "chat_id":
                    try:
                        value = int(value)
                    except ValueError:
                        await TelegramBot.send_message_to_admin("Invalid chat_id.")
                        return
                try:
                    res = User.get_users_by(key, value)
                    if res is None or len(res) == 0:
                        await TelegramBot.send_message_to_admin("User not found.")
                        return
                    user = res[0]
                    if not user.get_is_blocked():
                        await TelegramBot.send_message_to_admin("User is already unblocked.")
                        return
                    user.set_is_blocked(False)
                    User.update_user(user)
                    await TelegramBot.send_message_to_admin(f"User {value} unblocked.")
                except Exception as e:
                    await TelegramBot.send_message_to_admin(f"Invalid user ID.\n{e}")
            else:
                await TelegramBot.send_message_to_admin("Please specify a user ID. Use /admin unblock [chat_id/email] [value]")
        
        elif context.args[0] == "broadcast":
            if len(context.args) > 1:
                text = " ".join(context.args[1:])
                TelegramBot.broadcast(text)
                TelegramBot.send_message_to_admin("Broadcast sent.")
            else:
                await TelegramBot.send_message_to_admin("Please specify a message. Use /admin broadcast [message]")
                
        
        elif context.args[0] == "send":
            if len(context.args) > 2:
                key = context.args[1]
                value = context.args[2]
                if key not in ["chat_id", "email"]:
                    await TelegramBot.send_message_to_admin("Invalid key. Use /admin unblock [chat_id/email] [value]")
                    return
                if key == "chat_id":
                    try:
                        value = int(value)
                    except ValueError:
                        await TelegramBot.send_message_to_admin("Invalid chat_id.")
                        return
                try:
                    res = User.get_users_by(key, value)
                    if res is None or len(res) == 0:
                        await TelegramBot.send_message_to_admin("User not found.")
                        return
                    user = res[0]
                    
                    text = " ".join(context.args[2:])
                    await TelegramBot.send_message(user.get_chat_id(), text)
                    await TelegramBot.send_message_to_admin(f"Message sent to user {user.get_chat_id()}.")
                except Exception as e:
                    await TelegramBot.send_message_to_admin(f"Invalid user ID.\n{e}")
        
        else:
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
                    await TelegramBot.send_message(user.get_chat_id(), f"Login failed. {e}.")
                    continue
                except Exception as e:
                    print(e)
                    print(e.args)
                    await TelegramBot.send_message_to_admin(f"Scrapper Error: {e}")
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
            await asyncio.sleep(30)

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
        TelegramBot.send_message_to_admin(f"Uncaught Error: {e}\nBot stopped.")
        bot.stop()
        exit(1)