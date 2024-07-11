# -*- coding: utf-8 -*-
# 引用 SDK

import sys
sys.path.append("../..")

import wave
import time
import threading
from common import credential
from tts import flowing_speech_synthesizer
from common.log import logger
from common.utils import is_python3

APPID = 0
SECRET_ID = ''
SECRET_KEY = ''

VOICETYPE = 101001 # 音色类型
CODEC = "mp3" # 音频格式：pcm/mp3
SAMPLE_RATE = 16000 # 音频采样率：8000/16000
ENABLE_SUBTITLE = False


class MySpeechSynthesisListener(flowing_speech_synthesizer.FlowingSpeechSynthesisListener):
    
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
        if is_python3():
            super().on_synthesis_start(session_id)
        else:
            super(MySpeechSynthesisListener, self).on_synthesis_start(session_id)
        
        # TODO 合成开始，添加业务逻辑
        if not self.audio_file:
            self.audio_file = "speech_synthesis_output." + self.codec
        self.audio_data = bytes()

    def on_synthesis_end(self):
        if is_python3():
            super().on_synthesis_end()
        else:
            super(MySpeechSynthesisListener, self).on_synthesis_end()

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
        if is_python3():
            super().on_audio_result(audio_bytes)
        else:
            super(MySpeechSynthesisListener, self).on_audio_result(audio_bytes)
        
        # TODO 接收到二进制音频数据，添加实时播放或保存逻辑
        self.audio_data += audio_bytes

    def on_text_result(self, response):
        '''
        response: 文本结果，类型 dict，如下
        字段名       类型         说明
        code        int         错误码（无需处理，FlowingSpeechSynthesizer中已解析，错误消息路由至 on_synthesis_fail）
        message     string      错误信息
        session_id  string      回显客户端传入的 session id
        request_id  string      请求 id，区分不同合成请求，一次 websocket 通信中，该字段相同
        message_id  string      消息 id，区分不同 websocket 消息
        final       bool        合成是否完成（无需处理，FlowingSpeechSynthesizer中已解析）
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
        if is_python3():
            super().on_text_result(response)
        else:
            super(MySpeechSynthesisListener, self).on_text_result(response)

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
        if is_python3():
            super().on_synthesis_fail(response)
        else:
            super(MySpeechSynthesisListener, self).on_synthesis_fail(response)

        # TODO 合成失败，添加错误处理逻辑
        err_code = response["code"]
        err_msg = response["message"]
        

def process(id):
    listener = MySpeechSynthesisListener(id, CODEC, SAMPLE_RATE)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    synthesizer = flowing_speech_synthesizer.FlowingSpeechSynthesizer(
        APPID, credential_var, listener)
    synthesizer.set_voice_type(VOICETYPE)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)
    synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
   
    synthesizer.start()
    ready = synthesizer.wait_ready(5000)
    if not ready:
        logger.error("wait ready timeout")
        return
    
    texts = [
        "五位壮士一面向顶峰攀登，一面依托大树和",
        "岩石向敌人射击。山路上又留下了许多具敌",
        "人的尸体。到了狼牙山峰顶，五壮士居高临",
        "下，继续向紧跟在身后的敌人射击。不少敌人",
        "坠落山涧，粉身碎骨。班长马宝玉负伤了，子",
        "弹都打完了，只有胡福才手里还剩下一颗手榴",
        "弹，他刚要拧开盖子，马宝玉抢前一步，夺过",
        "手榴弹插在腰间，他猛地举起一块磨盘大的石",
        "头，大声喊道：“同志们！用石头砸！”顿时，",
        "石头像雹子一样，带着五位壮士的决心，带着",
        "中国人民的仇恨，向敌人头上砸去。山坡上传",
        "来一阵叽里呱啦的叫声，敌人纷纷滚落深谷。",
    ]

    while True:
        for text in texts:
            synthesizer.process(text)
            time.sleep(5) # 模拟文本流式生成
        break
    synthesizer.complete() # 发送合成完毕指令

    synthesizer.wait() # 等待服务侧合成完成

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
    process_multithread(1)
