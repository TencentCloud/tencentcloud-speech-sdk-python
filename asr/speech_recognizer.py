# -*- coding: utf-8 -*-
import sys
import hmac
import hashlib
import base64
import time
import json
import threading
import websocket
import uuid
import urllib
from common.log import logger


def is_python3():
    if sys.version > '3':
        return True
    return False


#实时识别语音使用
class SpeechRecognitionListener():
    '''
    reponse:  
    on_recognition_start的返回只有voice_id字段。
    on_fail 只有voice_id、code、message字段。
    on_recognition_complete没有result字段。
    其余消息包含所有字段。
    字段名	类型	
    code	Integer	
    message	String	
    voice_id	String
    message_id	String
    result	Result	
    final	Integer	

    Result的结构体格式为:
    slice_type	Integer	
    index	Integer	
    start_time	Integer	
    end_time	Integer	
    voice_text_str	String	
    word_size	Integer	
    word_list	Word Array

    Word的类型为:
    word    String 
    start_time Integer 
    end_time Integer 
    stable_flag：Integer 
    '''

    def on_recognition_start(self, response):
        pass

    def on_sentence_begin(self, response):
        pass

    def on_recognition_result_change(self, response):
        pass

    def on_sentence_end(self, response):
        pass

    def on_recognition_complete(self, response):
        pass

    def on_fail(self, response):
        pass


NOTOPEN = 0
STARTED = 1
OPENED = 2
FINAL = 3
ERROR = 4
CLOSED = 5

#实时识别语音使用
class SpeechRecognizer:

    def __init__(self, appid, credential, engine_model_type, listener):
        self.result = ""
        self.credential = credential
        self.appid = appid
        self.engine_model_type = engine_model_type
        self.status = NOTOPEN
        self.ws = None
        self.wst = None
        self.voice_id = ""
        self.new_start = 0
        self.listener = listener
        self.filter_dirty = 0
        self.filter_modal = 0
        self.filter_punc = 0
        self.convert_num_mode = 0
        self.word_info = 0
        self.need_vad = 0
        self.vad_silence_time = 0
        self.hotword_id = ""
        self.reinforce_hotword = 0
        self.voice_format = 4
        self.nonce = ""

    def set_filter_dirty(self, filter_dirty):
        self.filter_dirty = filter_dirty

    def set_filter_modal(self, filter_modal):
        self.filter_modal = filter_modal

    def set_filter_punc(self, filter_punc):
        self.filter_punc = filter_punc

    def set_convert_num_mode(self, convert_num_mode):
        self.convert_num_mode = convert_num_mode

    def set_word_info(self, word_info):
        self.word_info = word_info

    def set_need_vad(self, need_vad):
        self.need_vad = need_vad

    def set_vad_silence_time(self, vad_silence_time):
        self.vad_silence_time = vad_silence_time

    def set_hotword_id(self, hotword_id):
        self.hotword_id = hotword_id

    def set_voice_format(self, voice_format):
        self.voice_format = voice_format

    def set_nonce(self, nonce):
        self.nonce = nonce

    def set_reinforce_hotword(self, reinforce_hotword):
        self.reinforce_hotword = reinforce_hotword

    def format_sign_string(self, param):
        signstr = "asr.cloud.tencent.com/asr/v2/"
        for t in param:
            if 'appid' in t:
                signstr += str(t[1])
                break
        signstr += "?"
        for x in param:
            tmp = x
            if 'appid' in x:
                continue
            for t in tmp:
                signstr += str(t)
                signstr += "="
            signstr = signstr[:-1]
            signstr += "&"
        signstr = signstr[:-1]
        return signstr

    def create_query_string(self, param):
        signstr = "wss://asr.cloud.tencent.com/asr/v2/"
        for t in param:
            if 'appid' in t:
                signstr += str(t[1])
                break
        signstr += "?"
        for x in param:
            tmp = x
            if 'appid' in x:
                continue
            for t in tmp:
                signstr += str(t)
                signstr += "="
            signstr = signstr[:-1]
            signstr += "&"
        signstr = signstr[:-1]
        return signstr

    def sign(self, signstr, secret_key):
        hmacstr = hmac.new(secret_key.encode('utf-8'),
                           signstr.encode('utf-8'), hashlib.sha1).digest()
        s = base64.b64encode(hmacstr)
        s = s.decode('utf-8')
        return s

    def create_query_arr(self):
        query_arr = dict()

        query_arr['appid'] = self.appid
        query_arr['sub_service_type'] = 1
        query_arr['engine_model_type'] = self.engine_model_type
        query_arr['filter_dirty'] = self.filter_dirty
        query_arr['filter_modal'] = self.filter_modal
        query_arr['filter_punc'] = self.filter_punc
        query_arr['needvad'] = self.need_vad
        query_arr['convert_num_mode'] = self.convert_num_mode
        query_arr['word_info'] = self.word_info
        if self.vad_silence_time != 0:
            query_arr['vad_silence_time'] = self.vad_silence_time
        if self.hotword_id != "":
            query_arr['hotword_id'] = self.hotword_id

        query_arr['secretid'] = self.credential.secret_id
        query_arr['voice_format'] = self.voice_format
        query_arr['voice_id'] = self.voice_id
        query_arr['timestamp'] = str(int(time.time()))
        if self.nonce != "":
            query_arr['nonce'] = self.nonce
        else:
            query_arr['nonce'] = query_arr['timestamp']
        query_arr['expired'] = int(time.time()) + 24 * 60 * 60
        query_arr['reinforce_hotword'] = self.reinforce_hotword
        return query_arr

    def stop(self):
        if self.status == OPENED: 
            msg = {}
            msg['type'] = "end"
            text_str = json.dumps(msg)
            self.ws.sock.send(text_str)
        if self.ws:
            if self.wst and self.wst.is_alive():
                self.wst.join()
        self.ws.close()
        

    def write(self, data):
        while self.status == STARTED:
            time.sleep(0.1)
        if self.status == OPENED: 
            self.ws.sock.send_binary(data)

    def start(self):
        def on_message(ws, message):
            response = json.loads(message)
            response['voice_id'] = self.voice_id
            if response['code'] != 0:
                logger.error("%s server recognition fail %s" %
                             (response['voice_id'], response['message']))
                self.listener.on_fail(response)
                return
            if "final" in response and response["final"] == 1:
                self.status = FINAL
                self.result = message
                self.listener.on_recognition_complete(response)
                logger.info("%s recognition complete" % response['voice_id'])
                return
            if "result" in response.keys():
                if response["result"]['slice_type'] == 0:
                    self.listener.on_sentence_begin(response)
                    return
                elif response["result"]["slice_type"] == 2:
                    self.listener.on_sentence_end(response)
                    return
                elif response["result"]["slice_type"] == 1:
                    self.listener.on_recognition_result_change(response)
                    return

        def on_error(ws, error):
            if self.status == FINAL :
                return
            logger.error("websocket error %s  voice id %s" %
                         (format(error), self.voice_id))
            self.status = ERROR

        def on_close(ws):
            self.status = CLOSED
            logger.info("websocket closed  voice id %s" %
                          self.voice_id)

        def on_open(ws):
            self.status = OPENED

        query_arr = self.create_query_arr()
        if self.voice_id == "":
            query_arr['voice_id'] = str(uuid.uuid1())
            self.voice_id = query_arr['voice_id']
        query = sorted(query_arr.items(), key=lambda d: d[0])
        signstr = self.format_sign_string(query)

        autho = self.sign(signstr, self.credential.secret_key)
        requrl = self.create_query_string(query)
        if is_python3():
            autho = urllib.parse.quote(autho)
        else:
            autho = urllib.quote(autho)
        requrl += "&signature=%s" % autho
        self.ws = websocket.WebSocketApp(requrl,  None,
                on_error=on_error, on_close=on_close, on_message=on_message)
        self.ws.on_open = on_open
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()
        self.status = STARTED
        response = {}
        response['voice_id'] = self.voice_id
        self.listener.on_recognition_start(response)
        logger.info("%s recognition start" % response['voice_id'])
