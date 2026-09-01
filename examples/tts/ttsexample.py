# -*- coding: utf-8 -*-
# Import the SDK

import sys
sys.path.append("../..")

import wave
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

from common import credential
from tts import speech_synthesizer_ws
from common.log import logger
from common.utils import is_python3


APPID = 0
SECRET_ID = ''
SECRET_KEY = ''
ACCOUNT_AREA = "0"  # Account area: "0" (default, China account), "1" International account

VOICETYPE = 101001 # Voice type
FASTVOICETYPE = ""
CODEC = "pcm" # Audio format: pcm/mp3
SAMPLE_RATE = 16000 # Audio sample rate: 8000/16000
ENABLE_SUBTITLE = True


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
        session_id: request session id, type string
        '''
        super().on_synthesis_start(session_id)
        
        # TODO Synthesis started, add business logic
        if not self.audio_file:
            self.audio_file = "speech_synthesis_output_" + str(self.id) + "." + self.codec
        self.audio_data = bytes()

    def on_synthesis_end(self):
        super().on_synthesis_end()

        # TODO Synthesis ended, add business logic
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
        audio_bytes: binary audio, type bytes
        '''
        super().on_audio_result(audio_bytes)
        
        # TODO Received binary audio data, add real-time playback or save logic
        self.audio_data += audio_bytes

    def on_text_result(self, response):
        '''
        response: text result, type dict, as follows
        Field       Type        Description
        code        int         Error code (no need to handle, already parsed in SpeechSynthesizer, error message is routed to on_synthesis_fail)
        message     string      Error message
        session_id  string      Echo of the session id passed in by the client
        request_id  string      Request id, distinguishes different synthesis requests; this field remains the same within one websocket communication
        message_id  string      Message id, distinguishes different websocket messages
        final       bool        Whether synthesis is completed (no need to handle, already parsed in SpeechSynthesizer)
        result      Result      Text result struct

        Result struct
        Field       Type                Description
        subtitles   array of Subtitle   Timestamp array

        Subtitle struct
        Field       Type    Description
        Text        string  Synthesized text
        BeginTime   int     Begin timestamp
        EndTime     int     End timestamp
        BeginIndex  int     Begin index
        EndIndex    int     End index
        Phoneme     string  Phoneme
        '''
        super().on_text_result(response)

        # TODO Received text data, add business logic
        result = response["result"]
        subtitles = []
        if "subtitles" in result and len(result["subtitles"]) > 0:
            subtitles = result["subtitles"]

    def on_synthesis_fail(self, response):
        '''
        response: text result, type dict, as follows
        Field       Type        Description
        code        int         Error code
        message     string      Error message
        '''
        super().on_synthesis_fail(response)

        # TODO Synthesis failed, add error handling logic
        err_code = response["code"]
        err_msg = response["message"]
        

def process(id, text):
    logger.info("process start: idx={} text={}".format(id, text))
    listener = MySpeechSynthesisListener(id, CODEC, SAMPLE_RATE)
    credential_var = credential.Credential(SECRET_ID, SECRET_KEY)
    synthesizer = speech_synthesizer_ws.SpeechSynthesizer(
        APPID, credential_var, listener)
    synthesizer.set_text(text)
    synthesizer.set_voice_type(VOICETYPE)
    synthesizer.set_codec(CODEC)
    synthesizer.set_sample_rate(SAMPLE_RATE)
    synthesizer.set_enable_subtitle(ENABLE_SUBTITLE)
    synthesizer.set_fast_voice_type(FASTVOICETYPE)
    synthesizer.set_account_area(ACCOUNT_AREA)
    
    synthesizer.start()
    # wait for processing complete
    synthesizer.wait()

    logger.info("process done: idx={} text={}".format(id, text))
    return id

def read_tts_text():
    lines_list = []
    with open('tts_text.txt', 'r', encoding='utf-8') as file:
        for line in file:
            lines_list.append(line.strip())
    # print("total read {} lines".format(len(lines_list)))
    return lines_list

if __name__ == "__main__":
    if not is_python3():
        print("only support python3")
        sys.exit(0)

    # Read example text
    lines = read_tts_text()

    #### Example 1: single-threaded serial invocation ####
    for idx, line in enumerate(lines):
        result = process(idx, line)
        print(f"\nTask {result} completed\n")
    
    #### Example 2: multi-threaded invocation ####
    # thread_concurrency_num = 3 # Maximum number of threads
    # with ThreadPoolExecutor(max_workers=thread_concurrency_num) as executor:
    #     futures = [executor.submit(process, idx, line) for idx, line in enumerate(lines)]
    #     for future in as_completed(futures):
    #         result = future.result()
    #         print(f"\nTask {result} completed\n")

    #### Example 3: multi-process invocation (suitable for high concurrency scenarios) ####
    # process_concurrency_num = 3 # Maximum number of processes
    # with ProcessPoolExecutor(max_workers=process_concurrency_num) as executor:
    #     futures = [executor.submit(process, idx, line) for idx, line in enumerate(lines)]
    #     for future in as_completed(futures):
    #         result = future.result()
    #         print(f"\nTask {result} completed\n")
