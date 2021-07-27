# -*- coding: utf-8 -*-

import time
import sys
import threading
from datetime import datetime
import json
sys.path.append("../..")
from common import credential
from asr import flash_recognizer

# 注意：使用前务必先填写APPID、SECRET_ID、SECRET_KEY，否则会无法运行！！！
APPID = ""
SECRET_ID = ""
SECRET_KEY = ""
ENGINE_TYPE = "16k_zh"

if __name__=="__main__":
    if APPID == "":
        print("Please set APPID!")
        exit(0)
    if SECRET_ID == "":
        print("Please set SECRET_ID!")
        exit(0)
    if SECRET_KEY == "":
        print("Please set SECRET_KEY!")
        exit(0)

    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    # 新建FlashRecognizer，一个recognizer可以执行N次识别请求
    recognizer = flash_recognizer.FlashRecognizer(APPID, credential_var)

    # 新建识别请求
    req = flash_recognizer.FlashRecognitionRequest(ENGINE_TYPE)
    req.set_filter_modal(0)
    req.set_filter_punc(0)
    req.set_filter_dirty(0)
    req.set_voice_format("wav")
    req.set_word_info(0)
    req.set_convert_num_mode(1)

    # 音频路径
    audio = "./test.wav"
    with open(audio, 'rb') as f:
        #读取音频数据
        data = f.read()
        #执行识别
        resultData = recognizer.recognize(req, data)
        resp = json.loads(resultData)
        request_id = resp["request_id"]
        code = resp["code"]
        if code != 0:
            print("recognize faild! request_id: ", request_id, " code: ", code, ", message: ", resp["message"])
            exit(0)

        print("request_id: ", request_id)
        #一个channl_result对应一个声道的识别结果
        #大多数音频是单声道，对应一个channl_result
        for channl_result in resp["flash_result"]:
            print("channel_id: ", channl_result["channel_id"])
            print(channl_result["text"])
