import logging
from avito.avito_chat_info import avito_chat_messages
logging.basicConfig(level=logging.DEBUG, filename="py_log.log",filemode="w")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    avito_chat_messages()
    logging.debug(f"Старт")

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
