# -*- coding: utf-8 -*-
# 引用 SDK

import sys
sys.path.append("../..")

from datetime import datetime
import wave
import time
import threading
import json
from common import credential
from tts import speech_synthesizer


APPID = ""
SECRET_ID = ""
SECRET_KEY = ""


class MySpeechSynthesisListener(speech_synthesizer.SpeechSynthesisListener):
    def __init__(self, id):
        self.start_time = time.time()
        self.id = id

    def on_message(self, response):
        cost = (time.time() - self.start_time) * 1000
        print("%s|%s|on_message, size %d, cost %d\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['session_id'], len(response['data']), cost))

    def on_complete(self, response):
        cost = (time.time() - self.start_time) * 1000
        print("%s|%s|on_complete, size %d, cost %d\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['session_id'], len(response['data']), cost))
        wavfile = wave.open('speech_synthesizer_output.wav', 'wb')
        wavfile.setparams((1, 2, 16000, 0, 'NONE', 'NONE'))
        wavfile.writeframes(response["data"])
        wavfile.close()

    def on_fail(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|on_fail, rsp %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['session_id'], rsp_str))


def process(id):
    listener = MySpeechSynthesisListener(id)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    text = "语音合成可自定义音量和语速，让发音更自然、更专业、更符合场景需求。满足将文本转化成拟人化语音的需求，打通人机交互闭环。支持多种音色选择，语音合成可广泛应用于语音导航、有声读物、机器人、语音助手、自动新闻播报等场景，提升人机交互体验，提高语音类应用构建效率。"
    synthesizer = speech_synthesizer.SpeechSynthesizer(
        APPID, credential_var, 1002, listener)
    synthesizer.synthesis(text)


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
