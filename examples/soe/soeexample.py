# -*- coding: utf-8 -*-
# 引用 SDK

import time
import sys
import threading
from datetime import datetime
import json
sys.path.append("../..")
from common import credential
from soe import speaking_assessment

#TODO 补充账号信息
APPID = ""
SECRET_ID = ""
SECRET_KEY = ""
# 只有临时秘钥鉴权需要
TOKEN = ""
ENGINE_MODEL_TYPE = "16k_en"
SLICE_SIZE = 3200


class MySpeechRecognitionListener(speaking_assessment.SpeakingAssessmentListener):
    def __init__(self, id):
        self.id = id

    def on_recognition_start(self, response):
        print("%s|%s|OnRecognitionStart\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id']))

    def on_intermediate_result(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnIntermediateResults｜%s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_recognition_complete(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnRecognitionComplete| %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))

    def on_fail(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnFail,message %s\n" % (datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"), response['voice_id'], rsp_str))


def process(id):
    audio = "english.wav"
    listener = MySpeechRecognitionListener(id)
    # 临时秘钥鉴权使用带token的方式 credential_var = credential.Credential(SECRET_ID, SECRET_KEY, TOKEN)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    recognizer = speaking_assessment.SpeakingAssessment(
        APPID, credential_var, ENGINE_MODEL_TYPE,  listener)
    recognizer.set_text_mode(0)
    recognizer.set_ref_text("beautiful")
    recognizer.set_eval_mode(0)
    recognizer.set_keyword("")
    recognizer.set_sentence_info_enabled(0)
    recognizer.set_voice_format(1)
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
