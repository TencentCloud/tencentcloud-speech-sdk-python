# -*- coding: utf-8 -*-
# 引用 SDK

import sys
sys.path.append("../..")

import wave
import time
import threading
from common import credential
from vc import speech_convertor_ws
from common.log import logger
from common.utils import is_python3


APPID = 0
SECRET_ID = ''
SECRET_KEY = ''

VOICETYPE = 301005 # 音色类型
CODEC = "pcm" # 音频格式：pcm
SAMPLE_RATE = 16000 # 音频采样率：16000


class MySpeechConvertListener(speech_convertor_ws.SpeechConvertListener):
    
    def __init__(self, id, codec, sample_rate):
        self.start_time = time.time()
        self.id = id
        self.codec = codec.lower()
        self.sample_rate = sample_rate

        self.audio_file = ""
        self.audio_data = bytes()
    
    def set_output_file(self, filename):
        self.audio_file = filename

    def on_convert_start(self, voice_id):
        '''
        voice_id: voice id，类型字符串
        '''
        super().on_convert_start(voice_id)
        
        # TODO 音色变换开始，添加业务逻辑
        if not self.audio_file:
            self.audio_file = "speech_convert_output." + self.codec
        self.audio_data = bytes()

    def on_convert_end(self):
        super().on_convert_end()

        # TODO 音色变换结束，添加业务逻辑
        logger.info("write audio file, path={}, size={}".format(
            self.audio_file, len(self.audio_data)
        ))
        if self.codec == "pcm":
            wav_fp = wave.open(self.audio_file, "wb")
            wav_fp.setnchannels(1)
            wav_fp.setsampwidth(2)
            wav_fp.setframerate(self.sample_rate)
            wav_fp.writeframes(self.audio_data)
            wav_fp.close()
        else:
            logger.info("codec {}: service NOT support")

    def on_audio_result(self, audio_bytes):
        '''
        audio_bytes: 二进制音频，类型 bytes
        '''
        super().on_audio_result(audio_bytes)
        
        # TODO 接收到二进制音频数据，添加实时播放或保存逻辑
        self.audio_data += audio_bytes

    def on_convert_fail(self, response):
        '''
        response:  错误，类型 dict，如下
        字段名 类型
        Code        int         错误码
        Message     string      错误信息
        '''
        super().on_convert_fail(response)

        # TODO 音色变换失败，添加错误处理逻辑
        err_code = response["Code"]
        err_msg = response["Message"]
        

def process(id, input_audio_file):
    # 初始化音色变换监听器 MySpeechConvertListener 与变换服务 SpeechConvertor
    listener = MySpeechConvertListener(id, CODEC, SAMPLE_RATE)
    listener.set_output_file(
        '.'.join(input_audio_file.split('.')[:-1])+'_output_{}.wav'.format(id)) # set output file
    
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    convertor = speech_convertor_ws.SpeechConvertor(
        APPID, credential_var, listener)
    convertor.set_voice_type(VOICETYPE)
    convertor.set_codec(CODEC)
    convertor.set_sample_rate(SAMPLE_RATE)
    convertor.start()

    # 等待连接成功
    if not convertor.wait_to_send():
        logger.error("wait to send failed")
        return

    # 音频要求：16k采样率，单声道，16bit
    wavfile = wave.open(input_audio_file, "rb")
    sample_rate = wavfile.getframerate()
    if sample_rate != 16000:
        logger.error("sample rate is not 16000, please resample to 16000")
        return
    channel_num = wavfile.getnchannels()
    if channel_num != 1:
        logger.error("channel num is not 1, please convert to mono")
        return
    sample_width = wavfile.getsampwidth()
    if sample_width != 2:
        logger.error("sample width is not 2, please convert to 16bit")
        return
    
    # 发送音频：每100ms发送100ms时长（即1:1实时率）的数据包，对应 pcm 大小为 16k采样率3200字节
    nframe_per_chunk = sample_rate // 10 # 100ms per chunk
    total_frame_num = wavfile.getnframes()
    chunk_num = total_frame_num // nframe_per_chunk
    logger.info("process send start: chunk_size={}, nframe_per_chunk={}, chunk_num={}".format(
        nframe_per_chunk*sample_width, nframe_per_chunk, chunk_num))
    is_end = False
    for i in range(0, chunk_num):
        if i == chunk_num - 1:
            is_end = True

        data = wavfile.readframes(nframe_per_chunk)
        if not convertor.send(data, is_end):
            logger.error("process send failed, break")
            break
        time.sleep(0.1) # sleep 100ms
    wavfile.close()
    logger.info("process send done")
    
    # 等待接收音色变换完成
    convertor.wait()
    logger.info("process recv done")

def process_multithread(number, input_audio_file):
    thread_list = []
    for i in range(0, number):
        thread = threading.Thread(target=process, args=(i,input_audio_file,))
        thread_list.append(thread)
        thread.start()
        print(i)

    for thread in thread_list:
        thread.join()


if __name__ == "__main__":
    if not is_python3():
        print("only support python3")
        sys.exit(0)
    input_audio_file = "test.wav"
    process_multithread(1, input_audio_file)
