# -*- coding: utf-8 -*-
# 引用 SDK

import sys
sys.path.append("../..")

import wave
import time
import threading
from common import credential
from tts import speech_synthesizer_ws
from common.log import logger
from common.utils import is_python3


APPID = 0
SECRET_ID = ''
SECRET_KEY = ''

TEXT = "欢迎使用腾讯云实时语音合成"
VOICETYPE = 101001 # 音色类型
CODEC = "pcm" # 音频格式：pcm/mp3
SAMPLE_RATE = 16000 # 音频采样率：8000/16000
ENABLE_SUBTITLE = True
EMOTION_CATEGORY = "" # 仅支持多情感音色
EMOTION_INTENSITY = 100


class MySpeechSynthesisListener(speech_synthesizer_ws.SpeechSynthesisListener):
    
    def __init__(self, id, codec, sample_rate):
        self.start_time = time.time()
        self.id = id
        self.codec = codec.lower()
        self.sample_rate = sample_rate

        self.audio_file = ""
        self.audio_data = bytes()
    
    def set_audio_file(self, filename):
        self.audio_file = filename

    def on_synthesis_start(self, session_id):
        '''
        session_id: 请求session id，类型字符串
        '''
        super().on_synthesis_start(session_id)
        
        # TODO 合成开始，添加业务逻辑
        if not self.audio_file:
            self.audio_file = "speech_synthesis_output." + self.codec
        self.audio_data = bytes()

    def on_synthesis_end(self):
        super().on_synthesis_end()

        # TODO 合成结束，添加业务逻辑
        logger.info("write audio file, path={}, size={}".format(
            self.audio_file, len(self.audio_data)
        ))
        if self.codec == "pcm":
            wav_fp = wave.open(self.audio_file + ".wav", "wb")
            wav_fp.setnchannels(1)
            wav_fp.setsampwidth(2)
            wav_fp.setframerate(self.sample_rate)
            wav_fp.writeframes(self.audio_data)
            wav_fp.close()
        elif self.codec == "mp3":
            fp = open(self.audio_file, "wb")
            fp.write(self.audio_data)
            fp.close()
        else:
            logger.info("codec {}: sdk NOT implemented, please save the file yourself".format(
                self.codec
            ))

    def on_audio_result(self, audio_bytes):
        '''
        audio_bytes: 二进制音频，类型 bytes
        '''
        super().on_audio_result(audio_bytes)
        
        # TODO 接收到二进制音频数据，添加实时播放或保存逻辑
        self.audio_data += audio_bytes

    def on_text_result(self, response):
        '''
        response: 文本结果，类型 dict，如下
        字段名       类型         说明
        code        int         错误码（无需处理，SpeechSynthesizer中已解析，错误消息路由至 on_synthesis_fail）
        message     string      错误信息
        session_id  string      回显客户端传入的 session id
        request_id  string      请求 id，区分不同合成请求，一次 websocket 通信中，该字段相同
        message_id  string      消息 id，区分不同 websocket 消息
        final       bool        合成是否完成（无需处理，SpeechSynthesizer中已解析）
        result      Result      文本结果结构体

        Result 结构体
        字段名       类型                说明
        subtitles   array of Subtitle  时间戳数组
        
        Subtitle 结构体
        字段名       类型     说明
        Text        string  合成文本
        BeginTime   int     开始时间戳
        EndTime     int     结束时间戳
        BeginIndex  int     开始索引
        EndIndex    int     结束索引
        Phoneme     string  音素
        '''
        super().on_text_result(response)

        # TODO 接收到文本数据，添加业务逻辑
        result = response["result"]
        subtitles = []
        if "subtitles" in result and len(result["subtitles"]) > 0:
            subtitles = result["subtitles"]

    def on_synthesis_fail(self, response):
        '''
        response: 文本结果，类型 dict，如下
        字段名 类型
        code        int         错误码
        message     string      错误信息
        '''
        super().on_synthesis_fail(response)

        # TODO 合成失败，添加错误处理逻辑
        err_code = response["code"]
        err_msg = response["message"]
        

def process(id):
    listener = MySpeechSynthesisListener(id, CODEC, SAMPLE_RATE)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    synthesizer = speech_synthesizer_ws.SpeechSynthesizer(
        APPID, credential_var, listener)
    synthesizer.set_text(TEXT)
    synthesizer.set_voice_type(VOICETYPE)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)
    synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
    if EMOTION_CATEGORY != "":
        synthesizer.set_emotion_category(EMOTION_CATEGORY)
        if EMOTION_INTENSITY != 0:
            synthesizer.set_emotion_intensity(EMOTION_INTENSITY)
    
    synthesizer.start()
    # wait for processing complete
    synthesizer.wait()

    logger.info("process done")


def process_multithread(number):
    thread_list = []
    for i in range(0, number):
        thread = threading.Thread(target=process, args=(i,))
        thread_list.append(thread)
        thread.start()
        print(i)

    for thread in thread_list:
        thread.join()


if __name__ == "__main__":
    if not is_python3():
        print("only support python3")
        sys.exit(0)
    process_multithread(1)
