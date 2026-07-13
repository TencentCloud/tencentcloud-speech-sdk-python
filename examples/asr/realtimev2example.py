# -*- coding: utf-8 -*-
import time
import sys
import threading
from datetime import datetime
import json

sys.path.append("../..")
from common import credential
from asr import realtime_recognizer_v2

APPID = ""
SECRET_ID = ""
SECRET_KEY = ""
ENGINE_MODEL_TYPE = ""
SLICE_SIZE = 6400


class MyRealtimeRecognitionListenerV2(realtime_recognizer_v2.RealtimeRecognitionListenerV2):
    def __init__(self, id):
        self.id = id

    def on_recognition_start(self, response):
        print("%s|%s|OnRecognitionStart speaker_context_id=%s" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response['voice_id'],
            response.get('speaker_context_id', '')))

    def on_recognition_sentences(self, response):
        sentences = response.get('sentences', {})
        if not sentences:
            return
        for i, s in enumerate(sentences.get('sentence_list', [])):
            print("%s|%s|OnRecognitionSentences [%d] sentence_id=%d speaker=%d type=%d text=%s" % (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                response['voice_id'],
                i,
                s.get('sentence_id', 0),
                s.get('speaker_id', -1),
                s.get('sentence_type', 0),
                s.get('sentence', '')))

    def on_sentence_end(self, response):
        print("%s|%s|OnSentenceEnd code=%d message=%s" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response['voice_id'],
            response.get('code', 0),
            response.get('message', '')))

    def on_fail(self, response):
        print("%s|%s|OnFail code=%d message=%s" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response.get('voice_id', ''),
            response.get('code', -1),
            response.get('message', '')))


def process(id):
    audio = "test.pcm"
    listener = MyRealtimeRecognitionListenerV2(id)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    recognizer = realtime_recognizer_v2.RealtimeRecognizerV2(
        APPID, credential_var, ENGINE_MODEL_TYPE, listener)
    recognizer.set_voice_format(1)  # PCM
    recognizer.set_need_vad(1)
    # 话者分离默认关闭；如需开启：
    #   recognizer.set_speaker_diarization(1)
    #   recognizer.set_enable_speaker_context(1)
    #   首次不设 speaker_context_id，start() 后从 on_recognition_start 回调拿到，
    #   后续可设置：recognizer.set_speaker_context_id("之前拿到的id")

    # 演示扩展参数能力：通过 extra_params 动态追加 SDK 未显式定义的参数。

    try:
        recognizer.start()
        with open(audio, 'rb') as f:
            content = f.read(SLICE_SIZE)
            while content:
                recognizer.write(content)
                content = f.read(SLICE_SIZE)
                time.sleep(0.2)
    except Exception as e:
        print("error: %s" % e)
    finally:
        recognizer.stop()


def process_multithread(number):
    thread_list = []
    for i in range(number):
        t = threading.Thread(target=process, args=(i,))
        thread_list.append(t)
        t.start()
    for t in thread_list:
        t.join()


if __name__ == "__main__":
    process(0)
