# -*- coding: utf-8 -*-
# Import the SDK

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
ACCOUNT_AREA = "0"  # Account area: "0" (default, China account), "1" International account

VOICETYPE = 101001 # Voice type
CODEC = "mp3" # Audio format: pcm/mp3
SAMPLE_RATE = 16000 # Audio sample rate: 8000/16000
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
        session_id: request session id, type string
        '''
        if is_python3():
            super().on_synthesis_start(session_id)
        else:
            super(MySpeechSynthesisListener, self).on_synthesis_start(session_id)
        
        # TODO Synthesis started, add business logic
        if not self.audio_file:
            self.audio_file = "speech_synthesis_output." + self.codec
        self.audio_data = bytes()

    def on_synthesis_end(self):
        if is_python3():
            super().on_synthesis_end()
        else:
            super(MySpeechSynthesisListener, self).on_synthesis_end()

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
        if is_python3():
            super().on_audio_result(audio_bytes)
        else:
            super(MySpeechSynthesisListener, self).on_audio_result(audio_bytes)
        
        # TODO Received binary audio data, add real-time playback or save logic
        self.audio_data += audio_bytes

    def on_text_result(self, response):
        '''
        response: text result, type dict, as follows
        Field       Type        Description
        code        int         Error code (no need to handle, already parsed in FlowingSpeechSynthesizer, error message is routed to on_synthesis_fail)
        message     string      Error message
        session_id  string      Echo of the session id passed in by the client
        request_id  string      Request id, distinguishes different synthesis requests; this field remains the same within one websocket communication
        message_id  string      Message id, distinguishes different websocket messages
        final       bool        Whether synthesis is completed (no need to handle, already parsed in FlowingSpeechSynthesizer)
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
        if is_python3():
            super().on_text_result(response)
        else:
            super(MySpeechSynthesisListener, self).on_text_result(response)

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
        if is_python3():
            super().on_synthesis_fail(response)
        else:
            super(MySpeechSynthesisListener, self).on_synthesis_fail(response)

        # TODO Synthesis failed, add error handling logic
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
    synthesizer.set_account_area(ACCOUNT_AREA)
   
    synthesizer.start()
    ready = synthesizer.wait_ready(5000)
    if not ready:
        logger.error("wait ready timeout")
        return
    
    texts = [
        "On the Mountain of Flowers and Fruit there was ",
        "a magic stone that had absorbed the essence of ",
        "Heaven and Earth for countless ages. One day ",
        "the stone split open and a stone monkey leaped ",
        "forth, bowing to the four quarters. He became ",
        "the Handsome Monkey King, ruler of all apes. ",
        "Seeking immortality, he crossed the seas and ",
        "learned the Seventy-Two Transformations, and the ",
        "somersault cloud that carried him a hundred and ",
        "eight thousand li in a single leap. Wielding the ",
        "Golden-Hooped Rod, he made havoc in Heaven, until ",
        "the Buddha pressed him beneath the Five Elements Mountain. ",
    ]

    while True:
        for text in texts:
            synthesizer.process(text)
            time.sleep(5) # Simulate streaming text generation
        break
    synthesizer.complete() # Send synthesis completion command

    synthesizer.wait() # Wait for the server-side synthesis to complete

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
