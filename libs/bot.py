from telegram import Bot
from telegram.utils.request import Request
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                            TimedOut, ChatMigrated, NetworkError, RetryAfter)


import multiprocessing
import queue
import threading
import time
import logging
import traceback
import re
import sys
import requests

MESSAGE_PER_SECOND_LIMIT = 29
MESSAGE_PER_CHAT_LIMIT = 3
MESSAGE_PER_CHAT_MINUTE_LIMIT = 19

UNAUTHORIZED_ERROR_CODE = 2
BADREQUEST_ERROR_CODE = 3

MAX_MESSAGE_LENGTH = 4096


class AsyncBot(Bot):

    def __init__(self, token, workers=4, request_kwargs=None):
        counter_rlock = threading.RLock()
        self.counter_lock = threading.Condition(counter_rlock)
        self.message_queue = multiprocessing.Queue()
        self.waiting_chats_message_queue = multiprocessing.Queue()
        self.dispatcher = None
        self.processing = True
        self.num_workers = workers
        self.messages_per_second = 0
        self.messages_per_chat = {}
        self.messages_per_chat_per_minute = {}
        self.spam_chats_count = {}

        self.second_reset_queue = multiprocessing.Queue()
        self.minute_reset_queue = multiprocessing.Queue()

        self.workers = []
        self.resending_workers = []
        self.group_workers = []
        if request_kwargs is None:
            request_kwargs = {}
        con_pool_size = workers + 4
        if 'con_pool_size' not in request_kwargs:
            request_kwargs['con_pool_size'] = con_pool_size
        self._request = Request(**request_kwargs)
        super(AsyncBot, self).__init__(token=token, request=self._request)

        self.types_to_methods = {0: self.send_message, 1: self.send_video, 2: self.send_audio, 3: self.send_photo,
                                 4: self.send_document, 5: self.send_sticker, 6: self.send_voice, 7: self.sendVideoNote}
        self.methods_ty_types = {v: k for k, v in list(self.types_to_methods.items())}
        self.types_to_original_methods = {
            -1: super(AsyncBot, self).editMessageText,
            0: super(AsyncBot, self).send_message, 1: super(AsyncBot, self).send_video,
            2: super(AsyncBot, self).send_audio, 3: super(AsyncBot, self).send_photo,
            4: super(AsyncBot, self).send_document, 5: super(AsyncBot, self).send_sticker,
            6: super(AsyncBot, self).send_voice, 7: super(AsyncBot, self).sendVideoNote,
            8: super(AsyncBot, self).answerCallbackQuery
        }

    # @property
    # def base_url(self):
    #     return "https://api.telegram.org/bot{}/".format(self.token)

    def send_message(self, *args, **kwargs):
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def unpin_all_messages(self, chat_id, *args, **kwargs):
        result = requests.get(
            self.base_url + "/unpinAllChatMessages",
            params={
                "chat_id": chat_id,
                **kwargs
            }
        )
        if result.status_code // 100 != 2:
            logging.error("Can not unpin messages: {}".format(result.text))
        return result

    def send_video(self, *args, **kwargs):
        kwargs.update({"message_type": 1})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def send_audio(self, *args, **kwargs):
        kwargs.update({"message_type": 2})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def send_photo(self, *args, **kwargs):
        kwargs.update({"message_type": 3})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def send_document(self, *args, **kwargs):
        kwargs.update({"message_type": 4})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def send_sticker(self, *args, **kwargs):
        kwargs.update({"message_type": 5})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def send_voice(self, *args, **kwargs):
        kwargs.update({"message_type": 6})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def sendVideoNote(self, *args, **kwargs):
        kwargs.update({"message_type": 7})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def answerCallbackQuery(self, *args, **kwargs):
        kwargs.update({"message_type": 8})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def edit_message_text(self, *args, **kwargs):
        self.editMessageText(*args, **kwargs)

    def editMessageTextRestricted(self, *args, **kwargs):
        kwargs.update({"message_type": -1})
        message = MessageInQueue(*args, **kwargs)
        self.message_queue.put(message)
        return 0

    def editMessageText(self, *args, **kwargs):
        return super(AsyncBot, self).editMessageText(*args, **kwargs)

    def sync_send_message(self, *args, **kwargs):
        return super(AsyncBot, self).send_message(*args, **kwargs)

    def actually_send_message(self, *args, **kwargs):
        chat_id = kwargs.get('chat_id')
        if chat_id is None:
            try:
                chat_id = args[0]
            except IndexError:
                chat_id = 0
        message_type = kwargs.get('message_type')
        if message_type is None:
            message_type = 0

        lock = self.counter_lock
        lock.acquire()
        try:
            while True:
                lock.acquire()
                if chat_id in self.spam_chats_count and not kwargs.get("resending"):
                    spam_was = self.spam_chats_count.get(chat_id)
                    if time.time() - spam_was > 30 * 60:
                        self.spam_chats_count.pop(chat_id)
                    else:
                        self.spam_chats_count.update({chat_id: time.time()})
                        self.waiting_chats_message_queue.put(MessageInQueue(*args, **kwargs))
                        lock.release()
                        return None
                messages_per_current_chat = self.messages_per_chat.get(chat_id)
                messages_per_current_chat_per_minute = self.messages_per_chat_per_minute.get(chat_id)
                if messages_per_current_chat is None:
                    messages_per_current_chat = 0
                if messages_per_current_chat_per_minute is None:
                    messages_per_current_chat_per_minute = 0
                if self.messages_per_second < MESSAGE_PER_SECOND_LIMIT and messages_per_current_chat < \
                        MESSAGE_PER_CHAT_LIMIT and messages_per_current_chat_per_minute < MESSAGE_PER_CHAT_MINUTE_LIMIT:
                    self.messages_per_second += 1
                    self.messages_per_chat.update({chat_id: messages_per_current_chat + 1})
                    self.messages_per_chat_per_minute.update({chat_id: messages_per_current_chat_per_minute + 1})
                    lock.release()
                    break
                else:
                    if self.messages_per_second < MESSAGE_PER_SECOND_LIMIT and \
                            (not kwargs.get("resending") or chat_id > 0):
                        # Сообщения в эту секунду ещё можно отправлять
                        if chat_id > 0:
                            # Личка, маленькие чаты -- отправляем любое число сообщений в минуту
                            if messages_per_current_chat < MESSAGE_PER_CHAT_LIMIT:
                                self.messages_per_second += 1
                                self.messages_per_chat.update({chat_id: messages_per_current_chat + 1})
                                self.messages_per_chat_per_minute.update(
                                    {chat_id: messages_per_current_chat_per_minute + 1})
                                lock.release()
                                break
                        if messages_per_current_chat_per_minute >= MESSAGE_PER_CHAT_MINUTE_LIMIT:
                            self.spam_chats_count.update({chat_id: time.time()})
                        if not kwargs.get("message_in_group"):
                            # Кладём в другую очередь, если сообщение не в группе сообщений
                            self.waiting_chats_message_queue.put(MessageInQueue(*args, **kwargs))
                            lock.release()
                            return None
                lock.release()
                lock.wait()
        finally:
            try:
                lock.release()
            except RuntimeError:
                pass
        message = None
        try:
            try:
                method = self.types_to_original_methods.get(message_type)
                if method is None:
                    method = super(AsyncBot, self).send_message
            except Exception:
                logging.error(traceback.format_exc())
                method = super(AsyncBot, self).send_message
            message = method(*args, **kwargs)
            kwargs.pop("message_type", None)
            self._on_method_complete(message_type, message, *args, **kwargs)
        except Unauthorized:
            return UNAUTHORIZED_ERROR_CODE
        except BadRequest:
            logging.error(traceback.format_exc())
            if sys.exc_info()[1].message.startswith('Can\'t parse entities') and "parse_mode" in kwargs:
                logging.error("Resending without parse mode...")
                kwargs.pop("parse_mode")
                kwargs.update({"forbid_entities": True})
                return self.actually_send_message(*args, **kwargs)
            return BADREQUEST_ERROR_CODE
        except (TimedOut, NetworkError):
            logging.error(traceback.format_exc())
            # return None

            # Временно отключена повторная попытка отправить -- уже нет
            # Сообщение отправляется ещё раз, иначе -- отправляется в другую очередь
            retry = kwargs.get('retry')
            if retry is None:
                retry = 0
            if retry >= 1:
                # Кладём в другую очередь
                self.waiting_chats_message_queue.put(MessageInQueue(*args, **kwargs))
                return
            retry += 1
            kwargs.update({"retry": retry})
            time.sleep(0.1)
            try:
                method = self.types_to_original_methods.get(message_type)
                if method is None:
                    method = super(AsyncBot, self).send_message
            except Exception:
                logging.error(traceback.format_exc())
                method = super(AsyncBot, self).send_message
            message = method(*args, **kwargs)
        except RetryAfter:
            time.sleep(1)
            self.waiting_chats_message_queue.put(MessageInQueue(*args, **kwargs))
            return
        except Exception:
            logging.error("Unknown exception in bot worker! {}".format(traceback.format_exc()))
        finally:
            body = {"chat_id": chat_id, "time": time.time()}
            self.second_reset_queue.put(body)
            self.minute_reset_queue.put(body)
        return message

    def _on_method_complete(self, message_type: int, message, *args, **kwargs):
        """
        Метод, который вызовется после выполнения метода апи бота
        """
        if message_type == 0:
            # Сообщение было отправлено
            on_sent = kwargs.get("on_sent")
            if on_sent is not None:
                # Нужно выполнить функцию после отправки сообщения, запускаю в отдельном потоке
                threading.Thread(
                    target=on_sent, args=[message] + kwargs.get("on_sent_args", []), kwargs=kwargs.get("on_sent_kwargs")
                ).start()


    def start(self):
        for i in range(0, self.num_workers):
            worker = threading.Thread(target=self.__work, args=())
            worker.start()
            self.workers.append(worker)
            resending_worker = threading.Thread(target=self.__resend_work, args=())
            resending_worker.start()
            self.resending_workers.append(worker)
        threading.Thread(target=self.__release_monitor, args=(self.second_reset_queue, 1)).start()
        threading.Thread(target=self.__release_monitor, args=(self.minute_reset_queue, 60)).start()

    def set_dispatcher(self, dispatcher):
        self.dispatcher = dispatcher

    def stop(self):
        self.processing = False
        self.second_reset_queue.put(None)
        self.minute_reset_queue.put(None)
        for i in range(0, self.num_workers):
            self.message_queue.put(None)
            self.waiting_chats_message_queue.put(None)
        for i in self.workers:
            i.join()
        for i in self.resending_workers:
            i.join()
        time.sleep(1)
        try:
            while True:
                self.message_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            while True:
                self.waiting_chats_message_queue.get_nowait()
        except queue.Empty:
            pass
        self.message_queue.close()
        self.waiting_chats_message_queue.close()
        self.second_reset_queue.close()
        self.minute_reset_queue.close()

    def __del__(self):
        self.processing = False
        for i in range(0, self.num_workers):
            #self.message_queue.put(None)
            pass
        self.message_queue.close()
        try:
            super(AsyncBot, self).__del__()
        except AttributeError:
            pass


    def __releasing_resourse(self, chat_id):
        with self.counter_lock:
            self.messages_per_second -= 1
            mes_per_chat = self.messages_per_chat.get(chat_id)
            if mes_per_chat is None:
                self.counter_lock.notify_all()
                return
            if mes_per_chat == 1:
                self.messages_per_chat.pop(chat_id)
                self.counter_lock.notify_all()
                return
            mes_per_chat -= 1
            self.messages_per_chat.update({chat_id: mes_per_chat})
            self.counter_lock.notify_all()

    def __release_monitor(self, release_queue, interval):
        data = release_queue.get()
        while self.processing and data is not None:
            chat_id = data.get("chat_id")
            set_time = data.get("time")
            if chat_id is None or time is None:
                data = release_queue.get()
                continue
            remaining_time = interval - (time.time() - set_time)
            if remaining_time > 0:
                while remaining_time > 5:
                    time.sleep(5)
                    remaining_time -= 5
                    if not self.processing:
                        return
                time.sleep(remaining_time)
            if interval == 60:
                self.__releasing_minute_resourse(chat_id)
            else:
                self.__releasing_resourse(chat_id)
            try:
                data = release_queue.get()
            except Exception:
                return

    def __releasing_minute_resourse(self, chat_id):
        with self.counter_lock:
            mes_per_chat = self.messages_per_chat_per_minute.get(chat_id)
            if mes_per_chat is None:
                self.counter_lock.notify_all()
                return
            if mes_per_chat == 1:
                self.messages_per_chat_per_minute.pop(chat_id)
                self.counter_lock.notify_all()
                return
            mes_per_chat -= 1
            self.messages_per_chat_per_minute.update({chat_id: mes_per_chat})
            self.counter_lock.notify_all()

    def __work(self):
        message_in_queue = self.message_queue.get()
        while self.processing and message_in_queue is not None:
            args = message_in_queue.args
            kwargs = message_in_queue.kwargs
            try:
                self.actually_send_message(*args, **kwargs)
            except Exception:
                logging.error("Exception outside workloop: {}".format(traceback.format_exc()))
            message_in_queue = self.message_queue.get()
            if message_in_queue is None:
                return 0
        return 0

    def __resend_work(self):
        message_in_queue = self.waiting_chats_message_queue.get()
        while self.processing and message_in_queue is not None:
            args = message_in_queue.args
            kwargs = message_in_queue.kwargs
            kwargs.update({"resending": True})
            mes = self.actually_send_message(*args, **kwargs)
            if mes is None:
                time.sleep(0.1)
            message_in_queue = self.waiting_chats_message_queue.get()
            if message_in_queue is None:
                return 0
        return 0


class MessageInQueue:

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
