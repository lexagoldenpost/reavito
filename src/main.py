import logging
from telegram.tg_deep_seek_chat import tg_auth
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    tg_auth()
    logging.debug(f"Старт")

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
