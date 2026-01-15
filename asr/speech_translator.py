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


# 实时语音翻译使用
class SpeechTranslateListener():
    '''
    response:  
    on_translate_start的返回只有voice_id字段。
    on_fail 只有voice_id、code、message字段。
    on_translate_complete没有result字段。
    其余消息包含所有字段。
    字段名	类型	
    code	Integer	
    message	String	
    voice_id	String
    sentence_id	String
    result	Result	
    final	Integer	

    Result的结构体格式为:
    source	String	
    target	String	
    source_text	String	
    target_text	String	
    start_time	Integer	
    end_time	Integer	
    sentence_end	Boolean
    '''

    def on_translate_start(self, response):
        pass

    def on_sentence_begin(self, response):
        pass

    def on_translate_result_change(self, response):
        pass

    def on_sentence_end(self, response):
        pass

    def on_translate_complete(self, response):
        pass

    def on_fail(self, response):
        pass


NOTOPEN = 0
STARTED = 1
OPENED = 2
FINAL = 3
ERROR = 4
CLOSED = 5


# 实时语音翻译使用
class SpeechTranslator:

    def __init__(self, appid, credential, source, target, trans_model, listener):
        self.result = ""
        self.credential = credential
        self.appid = appid
        self.source = source
        self.target = target
        self.trans_model = trans_model
        self.status = NOTOPEN
        self.ws = None
        self.wst = None
        self.voice_id = ""
        self.listener = listener
        self.voice_format = 1  # PCM格式
        self.nonce = ""
        self._last_sentence_id = ""

    def set_voice_format(self, voice_format):
        self.voice_format = voice_format

    def set_nonce(self, nonce):
        self.nonce = nonce

    def format_sign_string(self, param):
        signstr = "asr.cloud.tencent.com/asr/speech_translate/"
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
        signstr = "wss://asr.cloud.tencent.com/asr/speech_translate/"
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
        query_arr['secretid'] = self.credential.secret_id
        query_arr['voice_format'] = self.voice_format
        query_arr['voice_id'] = self.voice_id
        query_arr['timestamp'] = str(int(time.time()))
        if self.nonce != "":
            query_arr['nonce'] = self.nonce
        else:
            query_arr['nonce'] = query_arr['timestamp']
        query_arr['expired'] = int(time.time()) + 24 * 60 * 60
        query_arr['source'] = self.source
        query_arr['target'] = self.target
        query_arr['trans_model'] = self.trans_model
        return query_arr

    def stop(self):
        if self.status == OPENED: 
            msg = {}
            msg['type'] = 'end'
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
                logger.error("%s server translate fail %s" %
                             (response['voice_id'], response['message']))
                self.listener.on_fail(response)
                return
            if "final" in response and response["final"] == 1:
                self.status = FINAL
                self.result = message
                self.listener.on_translate_complete(response)
                logger.info("%s translate complete" % response['voice_id'])
                self.ws.close()
                return
            if "result" in response and response["result"] is not None:
                sentence_id = response.get("sentence_id", "")
                if sentence_id != self._last_sentence_id and sentence_id:
                    self._last_sentence_id = sentence_id
                    self.listener.on_sentence_begin(response)
                    return
                elif response["result"].get("sentence_end", False):
                    self.listener.on_sentence_end(response)
                    return
                else:
                    self.listener.on_translate_result_change(response)
                    return

        def on_error(ws, error):
            if self.status == FINAL:
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
        self.listener.on_translate_start(response)
        logger.info("%s translate start" % response['voice_id'])