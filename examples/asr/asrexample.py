# -*- coding: utf-8 -*-
# 引用 SDK

import time
import sys
import threading
from datetime import datetime
import json
sys.path.append("../..")
from common import credential
from asr import speech_recognizer

APPID = ""
SECRET_ID = ""
SECRET_KEY = ""
ENGINE_MODEL_TYPE = "16k_zh"
SLICE_SIZE = 6400


class MySpeechRecognitionListener(speech_recognizer.SpeechRecognitionListener):
    def __init__(self, id):
        self.id = id

    def on_recognition_start(self, response):
        print("%s|%s|OnRecognitionStart\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id']))

    def on_sentence_begin(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnRecognitionSentenceBegin, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_recognition_result_change(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnResultChange, rsp %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_sentence_end(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSentenceEnd, rsp %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_recognition_complete(self, response):
        print("%s|%s|OnRecognitionComplete\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id']))

    def on_fail(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnFail,message %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))


def process(id):
    audio = "test.wav"
    listener = MySpeechRecognitionListener(id)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    recognizer = speech_recognizer.SpeechRecognizer(
        APPID, credential_var, ENGINE_MODEL_TYPE,  listener)
    recognizer.set_filter_modal(1)
    recognizer.set_filter_punc(1)
    recognizer.set_filter_dirty(1)
    recognizer.set_need_vad(1)
    #recognizer.set_vad_silence_time(600)
    recognizer.set_voice_format(1)
    recognizer.set_word_info(1)
    #recognizer.set_nonce("12345678")
    recognizer.set_convert_num_mode(1)
    try:
        recognizer.start()
        with open(audio, 'rb') as f:
            content = f.read(SLICE_SIZE)
            while content:
                recognizer.write(content)
                content = f.read(SLICE_SIZE)
                #sleep模拟实际实时语音发送间隔
                time.sleep(0.02)
    except Exception as e:
        print(e)
    finally:
        recognizer.stop()


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
    # process_multithread(20)
