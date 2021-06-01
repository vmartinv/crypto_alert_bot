import math, time, requests, pickle, traceback
from datetime import datetime

from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from repository.market import MarketRepository
import config
import logger_config


class CommandHandler:

    def __init__(self, api, db, customHandler):
        self.db = db
        self.api = api
        self.log = logger_config.get_logger(__name__)
        self.customHandler = customHandler
        with open(config.HELP_FILENAME, 'r') as fp:
            self.help_file = fp.read()

    def dispatch(self, message):
            text = message['text']
            chatId = message['chat']['id']
            command = text.partition('/')[2]
            self.log.info('handling command "{}"...'.format(command))

            if command == 'start' or command == 'help':
                self.help(chatId, command)
            elif command == 'list':
                self.list(chatId, command)
            elif command.startswith('remove'):
                self.remove(chatId, command)
            elif command.startswith('create'):
                self.create(chatId, command)
            elif command.startswith('eval'):
                self.eval(chatId, command)
            else:
                self.api.sendMessage('Unknown command', chatId)

    def remove(self, chatId, command):
        command = command[len("remove"):]
        self.api.sendMessage(self.customHandler.remove(chatId, command), chatId)

    def create(self, chatId, command):
        command = command[len("create"):]
        self.api.sendMessage(self.customHandler.create(chatId, command), chatId)

    def eval(self, chatId, command):
        command = command[len("eval"):]
        self.api.sendMessage(self.customHandler.eval(chatId, command), chatId)

    def help(self, chatId, command):
        self.log.info("reading help file")
        self.api.sendMessage(self.help_file, chatId, "Markdown")

    def list(self, chatId, command):
        self.api.sendMessage(self.customHandler.list(chatId), chatId)
