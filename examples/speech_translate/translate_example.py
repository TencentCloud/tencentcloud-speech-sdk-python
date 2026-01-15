# -*- coding: utf-8 -*-
# 引用 SDK

import time
import sys
import threading
from datetime import datetime
import json
sys.path.append("../..")
from common import credential
from asr import speech_translator

APPID = ""
SECRET_ID = ""
SECRET_KEY = ""
SOURCE = "zh"
TARGET = "en"
TRANS_MODEL = "hunyuan-translation-lite"
SLICE_SIZE = 6400


class MySpeechTranslateListener(speech_translator.SpeechTranslateListener):
    def __init__(self, id):
        self.id = id

    def on_translate_start(self, response):
        print("%s|%s|OnTranslateStart\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id']))

    def on_sentence_begin(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSentenceBegin, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_translate_result_change(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnTranslateResultChange, rsp %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_sentence_end(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSentenceEnd, rsp %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_translate_complete(self, response):
        print("%s|%s|OnTranslateComplete\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id']))

    def on_fail(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnFail,message %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))


def process(id):
    audio = "test.wav"
    listener = MySpeechTranslateListener(id)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    translator = speech_translator.SpeechTranslator(
        APPID, credential_var, SOURCE, TARGET, TRANS_MODEL, listener)
    translator.set_voice_format(12)

    try:
        translator.start()
        with open(audio, 'rb') as f:
            content = f.read(SLICE_SIZE)
            while content:
                translator.write(content)
                content = f.read(SLICE_SIZE)
                time.sleep(0.2)
    except Exception as e:
        print(e)
    finally:
        translator.stop()


def process_multithread(number):
    thread_list = []
    for i in range(0, number):
        thread = threading.Thread(target=process, args=(i,))
        thread_list.append(thread)
        thread.start()

    for thread in thread_list:
        thread.join()


if __name__ == "__main__":
    process(0)
    # process_multithread(3)