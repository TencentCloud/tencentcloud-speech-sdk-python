# -*- coding: utf-8 -*-
# 引用 SDK

import sys
sys.path.append("../..")

import wave
import time
import threading
from common import credential
from tts_podcast import speech_synthesizer_ws
from common.log import logger
from common.utils import is_python3

APPID = 0
SECRET_ID = ''
SECRET_KEY = ''

CODEC = "pcm"
SAMPLE_RATE = 24000


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
        code        int         错误码（无需处理，SpeechSynthesizer中已解析，错误消息路由至 on_synthesis_fail）
        message     string      错误信息
        session_id  string      回显客户端传入的 session id
        request_id  string      请求 id，区分不同合成请求，一次 websocket 通信中，该字段相同
        message_id  string      消息 id，区分不同 websocket 消息
        final       bool        合成是否完成（无需处理，SpeechSynthesizer中已解析）
        result      Result      文本结果结构体

        Result 结构体
        字段名       类型                说明
        type      string      结果类型（script：对话脚本）
        scripts   array of Script  时间戳数组
        
        Script 结构体
        Text: String 类型，该段的内容。
        Speaker：String 类型，该段的说话人，如：主持人1、主持人2。
        BeginTime: Integer 类型，该段在整个音频流中的起始时间。
        EndTime: Integer 类型，该段在整个音频流中的结束时间。
        Index: Integer 类型，该段序号，从0开始。

        '''
        if is_python3():
            super().on_text_result(response)
        else:
            super(MySpeechSynthesisListener, self).on_text_result(response)

        # 接收到文本数据，添加业务逻辑
        result = response["result"]

        # TODO 上下文ID（用于交互模式）
        if "context_id" in result:
            context_id = result["context_id"]
            logger.info("context_id={}".format(context_id))
        
        # TODO 脚本时间戳
        if "scripts" in result and len(result["scripts"]) > 0:
            for script in result["scripts"]:
                text = script["Text"]
                speaker = script["Speaker"]
                begin_time = script["BeginTime"]
                end_time = script["EndTime"]
                index = script["Index"]
                logger.info("script[{}]: timestamp=[{},{}] speaker={} text={}".format(index, begin_time, end_time, speaker, text))
        
        # TODO Token消耗量
        if "usage_tokens" in result and len(result["usage_tokens"]) >= 2:
            input_token = result["usage_tokens"][0]
            output_token = result["usage_tokens"][1]
            logger.info("token消耗: input_token={}, output_token={}".format(input_token, output_token))

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
        logger.error("synthesis fail: code={}, message={}".format(err_code, err_msg))
        

def process(id):
    # Step 1: 启动合成器，建立连接
    listener = MySpeechSynthesisListener(id, CODEC, SAMPLE_RATE)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    synthesizer = speech_synthesizer_ws.SpeechSynthesizer(
        APPID, credential_var, listener)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)

    # 设置播客主持人数量与音色
    # a. 单人播客示例
    # synthesizer.set_speaker_number(1, "jingqiangdashu")
    # b. 双人播客示例
    # synthesizer.set_speaker_number(2, "wenrouxuemei", "chenwenqingnian")
    
    # 设置交互模式ContextId
    # synthesizer.set_context_id("")
    # 关闭搜索
    # synthesizer.set_enable_web_search(False)

    synthesizer.start()

    # Step 2: 等待服务端确认
    ready = synthesizer.wait_ready()
    if not ready:
        logger.error("server not ready")
        return
    
    # Step 3: 添加播客资料
    # 文本类型示例
    if True:
        TEXT1 = "生成一个关于 AI Agent 产业现状的播客"
        TEXT2 = "介绍腾讯云ADP的发展"
        TEXT3 = "介绍国外最新进展"
        synthesizer.add_text(TEXT1)
        synthesizer.add_text(TEXT2)
        synthesizer.add_text(TEXT3)
    # 网址类型示例
    if False: 
        URL = "https://news.qq.com/rain/a/20250920A06AL600"
        synthesizer.add_url(URL)
    # 文件类型示例
    if False:
        FILE_URL = "https://justin-dev-1300466766.cos.ap-shanghai.myqcloud.com/public_link/news.pdf"
        synthesizer.add_file_url("pdf", FILE_URL)
    
    # Step 4: 发送资料，开始合成
    synthesizer.process()

    # 测试 CANCEL 取消指令
    # logger.info("sleep for cancel")
    # time.sleep(30) # 模拟等待生成部分播客后，客户取消生成
    # synthesizer.cancel()
    # logger.info("send cancel")
    
    # Step 5: 等待合成结束
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
    #process(0)
    process_multithread(1)
