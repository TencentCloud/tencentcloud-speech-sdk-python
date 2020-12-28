# -*- coding: utf-8 -*-

import time
import sys
import threading
from datetime import datetime
import json
sys.path.append("../..")
from common import credential
from asr import flash_recognizer

APPID = ""
SECRET_ID = ""
SECRET_KEY = ""
ENGINE_TYPE = "16k_zh"

if __name__=="__main__":
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    recognizer = flash_recognizer.FlashRecognizer(APPID, credential_var, ENGINE_TYPE)
    recognizer.set_filter_modal(0)
    recognizer.set_filter_punc(0)
    recognizer.set_filter_dirty(0)
    recognizer.set_voice_format("wav")
    recognizer.set_word_info(0)
    recognizer.set_convert_num_mode(1)

    audio = "./test.wav"
    with open(audio, 'rb') as f:
        #读取音频数据
        data = f.read()
        #执行识别
        resultData = recognizer.do_recognize(data)
        resp = json.loads(resultData)
        code = resp["code"]
        if code != 0:
            print("recognize faild! code: ", code, ", message: ", resp["message"])
            exit(0)

        request_id = resp["request_id"]
        print("request_id: ", request_id)
        #一个channl_result对应一个声道的识别结果
        #大多数音频是单声道，对应一个channl_result
        for channl_result in resp["flash_result"]:
            print("channel_id: ", channl_result["channel_id"])
            print(channl_result["text"])
