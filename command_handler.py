import config
import logger_config


class CommandHandler:

    def __init__(self, api, db, alertHandler):
        self.db = db
        self.api = api
        self.log = logger_config.get_logger(__name__)
        self.alertHandler = alertHandler
        with open(config.HELP_FILENAME, 'r') as fp:
            self.help_file = fp.read()
        self.cmd_map = [
            ('start', self.help),
            ('help', self.help),
            ('list', self.list),
            ('remove', self.remove),
            ('create', self.create),
            ('eval', self.eval),
        ]

    def dispatch(self, message):
            text = message['text']
            chatId = message['chat']['id']
            command = text.partition('/')[2].strip()
            self.log.info('handling command "{}"...'.format(command))
            for word, fun in self.cmd_map:
                if command.startswith(word):
                    fun(chatId, command[len(word):])
                    return
            self.api.sendMessage('Unknown command', chatId)

    def remove(self, chatId, command):
        self.api.sendMessage(self.alertHandler.remove(chatId, command), chatId)

    def create(self, chatId, command):
        self.api.sendMessage(self.alertHandler.create(chatId, command), chatId)

    def eval(self, chatId, command):
        self.api.sendMessage(self.alertHandler.eval(chatId, command), chatId)

    def help(self, chatId, command):
        self.api.sendMessage(self.help_file, chatId, "Markdown")

    def list(self, chatId, command):
        self.api.sendMessage(self.alertHandler.list(chatId), chatId)
