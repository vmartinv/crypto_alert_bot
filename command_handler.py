import config
import logger_config
import telegram.ext


class CommandHandler:

    def __init__(self, alert_handler, dispatcher):
        self.log = logger_config.get_logger(__name__)
        self.alert_handler = alert_handler
        with open(config.HELP_FILENAME, 'r') as fp:
            self.help_file = fp.read()
        self.cmd_map = [
            ('start', self.help, "Markdown"),
            ('help', self.help, "Markdown"),
            ('list', self.alert_handler.list, None),
            ('remove', self.alert_handler.remove, None),
            ('create', self.alert_handler.create, None),
            ('eval', self.alert_handler.eval, None),
        ]
        self.add_handlers(dispatcher)

    def add_handlers(self, dispatcher):
        for word, fun, parse_mode in self.cmd_map:
            def run_fun(fun, parse_mode, update, context):
                chatId = update.effective_chat.id
                command = ' '.join(context.args)
                context.bot.send_message(
                    text=fun(chatId, command),
                    parse_mode=parse_mode,
                    chat_id=chatId
                )
            handler = telegram.ext.CommandHandler(word, lambda update, context, fun=fun, parse_mode=parse_mode: run_fun(fun, parse_mode, update, context)
            )
            dispatcher.add_handler(handler)
        unknown_handler = telegram.ext.MessageHandler(telegram.ext.Filters.command, self.unknown)
        dispatcher.add_handler(unknown_handler)

    def unknown(self, update, context):
        context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I didn't understand that command.")

    def help(self, chatId, _command):
        return self.help_file
