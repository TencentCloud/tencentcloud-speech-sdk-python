# -*- coding: utf-8 -*-
# 引用 SDK

import json
import os
import sys
import threading
import time
from datetime import datetime

sys.path.append("../..")
from common import credential
from asr import speech_interpreter

APPID = ""
SECRET_ID = ""
SECRET_KEY = ""

TARGET = "en"
VOICE = ""
INPUT_SAMPLE_RATE = 16000
BYTES_PER_MS = INPUT_SAMPLE_RATE // 1000 * 2 * 1
SLICE_SIZE = BYTES_PER_MS * 200
ENABLE_SWITCH = False
# SWITCH_TARGET 演示动态变更的目标语种，须与音频源语种不同
SWITCH_TARGET = "zh"
# SWITCH_AFTER_SLICE 发送多少个音频分片后插入 update 控制帧变更目标语种
SWITCH_AFTER_SLICE = 10


class MySpeechInterpretListener(speech_interpreter.SpeechInterpretListener):
    def __init__(self, id, audio_out):
        self.id = id
        self.audio_out = audio_out

    def on_session_start(self, response):
        print("%s|%s|OnSessionStart\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"]))

    def on_session_ready(self, response):
        print("%s|%s|OnSessionReady\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"]))

    def on_subtitle_start(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSubtitleStart, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            response["voice_id"], rsp_str))

    def on_subtitle_response(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSubtitleResponse, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            response["voice_id"], rsp_str))

    def on_subtitle_end(self, response):
        # end_reason 为 sensitive 时应以本条整体替换同 sentence_id 的增量字幕
        if response.get("end_reason") == speech_interpreter.END_REASON_SENSITIVE:
            print("%s|%s|sentence %s blocked by security audit\n" % (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                response["voice_id"], response.get("sentence_id")))
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSubtitleEnd, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"], rsp_str))

    def on_tts_sentence_start(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnTtsSentenceStart, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"], rsp_str))

    def on_sentence_skipped(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSentenceSkipped, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"], rsp_str))

    def on_audio_data(self, data):
        self.audio_out.write(data)

    def on_session_updated(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnSessionUpdated, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"], rsp_str))

    def on_interpret_complete(self, response):
        print("%s|%s|OnInterpretComplete\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"]))

    def on_fail(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnFail, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"], rsp_str))

    def on_warn(self, response):
        rsp_str = json.dumps(response, ensure_ascii=False)
        print("%s|%s|OnWarn, rsp %s\n" % (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            response["voice_id"], rsp_str))


def check_audio(audio):
    if not os.path.isfile(audio):
        raise RuntimeError("audio file not found: %s" % audio)
    size = os.path.getsize(audio)
    if size < BYTES_PER_MS:
        raise RuntimeError("audio file too small: %s, %d bytes" % (audio, size))
    print("audio %s size %d bytes, duration %dms" % (
        audio, size, size // BYTES_PER_MS))


def process(id):
    audio = "test.pcm"
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    with open("interpret_%d.pcm" % id, "wb") as audio_out:
        listener = MySpeechInterpretListener(id, audio_out)
        interpreter = speech_interpreter.SpeechInterpreter(
            APPID, credential_var, TARGET, INPUT_SAMPLE_RATE, listener)
        interpreter.set_voice(VOICE)
        slice_index = 0
        sent_bytes = 0
        try:
            check_audio(audio)
            interpreter.start()
            with open(audio, "rb") as f:
                content = f.read(SLICE_SIZE)
                while content:
                    if not interpreter.write(content):
                        print("stop sending, session terminated")
                        break
                    slice_index += 1
                    sent_bytes += len(content)
                    if ENABLE_SWITCH and slice_index == SWITCH_AFTER_SLICE:
                        interpreter.update_session(SWITCH_TARGET)
                    content = f.read(SLICE_SIZE)
                    time.sleep(0.2)
        except Exception as e:
            print("process fail: %r" % e)
        finally:
            interpreter.stop()
            print("%s|%s|summary sent_slices=%d sent_bytes=%d sent_ms=%d "
                  "status=%d\n" % (
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      interpreter.voice_id, slice_index, sent_bytes,
                      sent_bytes // BYTES_PER_MS,
                      interpreter.status))


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
