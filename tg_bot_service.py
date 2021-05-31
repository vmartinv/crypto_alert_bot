import traceback
import math, time, requests, pickle, traceback
from datetime import datetime
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import logger_config
import config
from repository.market import MarketRepository
from formating import format_price
from api.binance_rest import CandleInterval
from command_handler import CommandHandler
from custom_handler import CustomHandler
from tg_api import TgApi

class TgBotService(object):
    def processMessage(self, message):
        if "text" not in message:
            print(F"IGNORING [NO TEXT] {message}")
            return
        if('entities' in message and message['entities'][0]['type'] == 'bot_command'):
            self.command_handler.dispatch(message)
        else:
            print(F"IGNORING [NON-COMMAND] {message}")

    def processUpdates(self, updates):
        for update in updates:
            self.last_update = self.db['last_update'] = update['update_id']
            if 'message' in update:
                message = update['message']
            elif "edited_message" in update['edited_message']:
                message = update['edited_message']
            else:
                self.log.error(f"no message in update: {update}")
                return

            try:
                self.processMessage(message)
            except:
                self.log.exception(f"error processing update: {update}")


    def persist_db(self):
        with open(config.DB_FILENAME, 'wb') as fp:
            pickle.dump(self.db, fp)

    def run(self):
        self.log = logger_config.instance
        try:
            with open(config.DB_FILENAME, 'rb') as fp:
                self.db = pickle.load(fp)
        except:
            self.log.error("error loading db, defaulting to empty db")
            self.db = {}
        self.api = TgApi(self.log)
        self.repository = MarketRepository(self.log)
        self.customHandler = CustomHandler(self.db, self.repository)
        self.command_handler = CommandHandler(self.api, self.repository, self.db, self.log, self.customHandler)

        self.log.debug("db at start: {}".format(self.db))
        self.last_update = self.db['last_update'] if 'last_update' in self.db else 0
        # main loop
        loop = True
        while loop:
            try:
                updates = self.api.getUpdates(self.last_update)
                if updates is None:
                    self.log.error('get update request failed')
                else:
                    self.processUpdates(updates)
                try:
                    self.customHandler.process()
                except:
                    self.log.exception("exception at processing alerts")
                time.sleep(1)
            except KeyboardInterrupt:
                self.log.info("interrupt received, stopping…")
                loop = False
            except:
                self.log.exception("exception at processing updates")
                loop = False

            self.persist_db()

if __name__ == "__main__":
    service = TgBotService()
    service.run()
