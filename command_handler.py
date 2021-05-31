import math, time, requests, pickle, traceback
from datetime import datetime

from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from repository.market import MarketRepository
import config
from formating import format_price
from api.binance_rest import CandleInterval


class CommandHandler:

    def __init__(self, api, repository, db, log, customHandler):
        self.repository = repository
        self.db = db
        self.api = api
        self.log = log
        self.customHandler = customHandler

    def dispatch(self, message):
            text = message['text']
            chatId = message['chat']['id']
            command = text.partition('/')[2]
            self.log.info('handling command "{}"...'.format(command))

            if command == 'start' or command == 'help':
                self.help(chatId, command)
            elif command == 'list':
                self.list(chatId, command)
            elif command=='remove':
                self.remove(chatId, command)
            elif command.startswith('new'):
                self.create(chatId, command)
            else:
                self.api.sendMessage('Unknown command', chatId)

    def remove(self, chatId, command):
        command = command[len("remove"):]
        self.api.sendMessage(self.customHandler.remove(chatId, command), chatId)

    def create(self, chatId, command):
        command = command[len("new"):]
        self.api.sendMessage(self.customHandler.create(chatId, command), chatId)

    def help(self, chatId, command):
        self.log.info("reading help file")
        with open(config.HELP_FILENAME, 'rb') as fp:
            resp = fp.read()
        self.api.sendMessage(resp, chatId, "Markdown")

    def list(self, chatId, command):
        self.api.sendMessage(self.customHandler.list(chatId), chatId)
