# -*- coding: utf-8 -*-
import sys
import hmac
import hashlib
import base64
import time
import json
import threading
import urllib

import websocket
import uuid
from urllib.parse import quote
from common.log import logger


def is_python3():
    if sys.version > '3':
        return True
    return False


# 实时识别语音使用
class SpeakingAssessmentListener():
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
    result
    final	Integer	

    # Result的结构体格式为:
    # slice_type	Integer
    # index	Integer
    # start_time	Integer
    # end_time	Integer
    # voice_text_str	String
    # word_size	Integer
    # word_list	Word Array
    #
    # Word的类型为:
    # word    String
    # start_time Integer
    # end_time Integer
    # stable_flag：Integer
    '''

    def on_recognition_start(self, response):
        pass

    def on_intermediate_result(self, response):
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


def quote_autho(autho):
    if sys.version_info >= (3, 0):
        import urllib.parse as urlparse
        return urlparse.quote(autho)
    else:
        return urllib.quote(autho)


# 实时识别使用
class SpeakingAssessment:

    def __init__(self, appid, credential, engine_model_type, listener):
        self.result = ""
        self.credential = credential
        self.appid = appid
        self.server_engine_type = engine_model_type
        self.status = NOTOPEN
        self.ws = None
        self.wst = None
        self.voice_id = ""
        self.new_start = 0
        self.listener = listener
        self.text_mode = 0
        self.ref_text = ""
        self.keyword = ""
        self.eval_mode = 0
        self.score_coeff = 1.0
        self.sentence_info_enabled = 0
        self.voice_format = 0
        self.nonce = ""
        self.rec_mode = 0

    def set_text_mode(self, text_mode):
        self.text_mode = text_mode
    
    def set_rec_mode(self, rec_mode):
        self.rec_mode = rec_mode

    def set_ref_text(self, ref_text):
        self.ref_text = ref_text

    def set_keyword(self, keyword):
        self.keyword = keyword

    def set_eval_mode(self, eval_mode):
        self.eval_mode = eval_mode

    def set_sentence_info_enabled(self, sentence_info_enabled):
        self.sentence_info_enabled = sentence_info_enabled

    def set_voice_format(self, voice_format):
        self.voice_format = voice_format

    def set_nonce(self, nonce):
        self.nonce = nonce

    def format_sign_string(self, param):
        signstr = "soe.cloud.tencent.com/soe/api/"
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
        signstr = ""
        for key, value in param.items():
            if key == 'appid':
                signstr += str(value)
                break
        signstr += "?"
        for key, value in param.items():
            if key == 'appid':
                continue
            value = quote_autho(str(value))
            signstr += str(key) + "=" + str(value) + "&"
        signstr = signstr[:-1]
        return "wss://soe.cloud.tencent.com/soe/api/" + signstr

    def sign(self, signstr, secret_key):
        hmacstr = hmac.new(secret_key.encode('utf-8'),
                           signstr.encode('utf-8'), hashlib.sha1).digest()
        s = base64.b64encode(hmacstr)
        s = s.decode('utf-8')
        return s

    def create_query_arr(self):
        query_arr = dict()

        query_arr['appid'] = self.appid
        query_arr['server_engine_type'] = self.server_engine_type
        query_arr['text_mode'] = self.text_mode
        query_arr['rec_mode'] = self.rec_mode
        query_arr['ref_text'] = self.ref_text
        query_arr['keyword'] = self.keyword
        query_arr['eval_mode'] = self.eval_mode
        query_arr['score_coeff'] = self.score_coeff
        query_arr['sentence_info_enabled'] = self.sentence_info_enabled
        query_arr['secretid'] = self.credential.secret_id
        if self.credential.token != "":
            query_arr['token'] = self.credential.token
        query_arr['voice_format'] = self.voice_format
        query_arr['voice_id'] = self.voice_id
        query_arr['timestamp'] = str(int(time.time()))
        if self.nonce != "":
            query_arr['nonce'] = self.nonce
        else:
            query_arr['nonce'] = query_arr['timestamp']
        query_arr['expired'] = int(time.time()) + 24 * 60 * 60
        return query_arr

    def stop(self):
        if self.status == OPENED:
            msg = {'type': "end"}
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
            # print(message)
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
                self.ws.close()
                return
            else:
                if response["result"] is not None:
                    self.listener.on_intermediate_result(response)
                    logger.info("%s recognition doing" % response['voice_id'])
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
        requrl = self.create_query_string(query_arr)
        print(requrl)
        if is_python3():
            autho = urllib.parse.quote(autho)
        else:
            autho = urllib.quote(autho)
        requrl += "&signature=%s" % autho
        print(requrl)
        self.ws = websocket.WebSocketApp(requrl, None,
                                         on_error=on_error, on_close=on_close, on_message=on_message)
        self.ws.on_open = on_open
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()
        self.status = STARTED
        response = {'voice_id': self.voice_id}
        self.listener.on_recognition_start(response)
        logger.info("%s recognition start" % response['voice_id'])
