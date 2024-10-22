import logging
import os
import unicodedata

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from chatgpt import ChatGPT
from moodle import Moodle


class MoodleBot:
    def __init__(self) -> None:
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)

        load_dotenv()
        self.logger = logging.getLogger(__name__)
        self.logger.info('Starting the app')
        self.moodle = Moodle(self.logger)
        self.chatgpt = ChatGPT(self.logger)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data['is_logged'] = False
        await update.message.reply_text("¡Bienvenido! Soy tu asistente virtual de Moodle.\n"
                                        "Para comenzar, proporciona tu nombre de usuario en Moodle.")

    async def options(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.show_user_options(update, '¿Qué deseas saber sobre tu aula virtual?')

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Soy un bot conversacional creado para proporcionarte información sobre tus " +
                                        "cursos del aula virtual alojado en Moodle." +
                                        "\nLa información que puedo responder actualmente es la siguiente:" +
                                        "\n* Tareas pendientes" +
                                        "\n* Notas tareas" +
                                        "\n* Notas asignaturas" +
                                        "\n* Cuestionarios pendientes" +
                                        "\n* Mensajes pendientes" +
                                        "\n* Notificaciones pendientes" +
                                        "\n* Eventos en los próximos 7 días")
        await self.show_user_options(update, '¿Qué deseas saber sobre tu aula virtual?')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if 'is_logged' not in context.user_data or not context.user_data['is_logged']:
            await self.handle_login(update, context)
        else:
            await self.handle_user_options(update, context)

    async def handle_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_input = update.message.text
        self.logger.info('Trying  to log in "' + user_input + '" into Moodle')

        if self.moodle.login(user_input, context):
            self.logger.info('User "' + update.message.text + '" logged')
            context.user_data['is_logged'] = True

            self.moodle.prepare_user_info(context)
            text = f"Bienvenido, {context.user_data['user_name']}. ¿Qué deseas saber sobre tu aula virtual?"
            await self.show_user_options(update, text)
        else:
            self.logger.error('User "' + user_input + '" not found')
            await update.message.reply_text(
                "Lo siento, no he podido validar tu usuario. ¿Puedes proporcionarme tu nombre de usuario del aula " +
                "virtual?")

    async def show_user_options(self, update: Update, text: str) -> None:
        reply_keyboard = [
            ["Tareas pendientes", "Calificaciones tareas"],
            ["Calificaciones asignaturas", "Cuestionarios pendientes"],
            ["Mensajes pendientes", "Notificaciones pendientes"],
            ["Eventos de la próxima semana"]
        ]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

        await update.message.reply_text(text, reply_markup=markup)

    async def handle_user_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_input = self.clean_text(update.message.text)

        self.logger.info('Handling "' + user_input + '" request from "' + context.user_data['user_name'] + '"')
        if user_input == 'tareas pendientes':
            response = self.moodle.pending_assignments(context)
            await self.send_message(update, user_input, response)
        elif user_input == 'calificaciones tareas':
            response = self.moodle.assignment_grades(context)
            await self.send_message(update, user_input, response)
        elif user_input == 'calificaciones asignaturas':
            response = self.moodle.course_grades(context)
            await self.send_message(update, user_input, response)
        elif user_input == 'cuestionarios pendientes':
            response = self.moodle.pending_quizzes(context)
            await self.send_message(update, user_input, response)
        elif user_input == 'mensajes pendientes':
            response = self.moodle.user_pending_messages(context)
            await self.send_message(update, user_input, response)
        elif user_input == 'notificaciones pendientes':
            response = self.moodle.user_pending_notifications(context)
            await self.send_message(update, user_input, response)
        elif user_input == 'eventos de la proxima semana':
            response = self.moodle.next_week_events(context)
            await self.send_message(update, user_input, response)
        else:
            response = self.chatgpt.get_response(update.message.text)

            if response:
                await update.message.reply_text(response)
                await self.show_user_options(update, "¿En qué más te puedo ayudar?")
            else:
                self.logger.error('No response given to "' + user_input + '"')
                await self.show_user_options(update, "Lo siento, no te he entendido. ¿En qué más te puedo ayudar?")

    async def send_message(self, update: Update, user_input: str, bot_output: str) -> None:
        if bot_output:
            self.logger.info('Anwser given to input "' + user_input + '"')
            self.chatgpt.save_chat_gpt_context(user_input, bot_output)
            await update.message.reply_text(bot_output)
            await self.show_user_options(update, "¿En qué más te puedo ayudar?")
        else:
            await self.show_user_options(update, "Lo siento, no te he entendido. ¿En qué más te puedo ayudar?")

    def clean_text(self, text: str) -> str:
        normalized_text = unicodedata.normalize('NFD', text.lower())
        return ''.join(c for c in normalized_text if unicodedata.category(c) != 'Mn')

    def main(self) -> None:
        application = Application.builder().token(os.getenv('TELEGRAM_API_KEY')).build()

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("options", self.options))
        application.add_handler(CommandHandler("help", self.help))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    telegramBot = MoodleBot()
    telegramBot.main()
