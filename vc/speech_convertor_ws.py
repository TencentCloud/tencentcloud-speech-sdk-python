# -*- coding: utf-8 -*-
import sys
import hmac
import hashlib
import base64
import time
import json
import threading
from websocket import ABNF, WebSocketApp
import uuid
import urllib
from common.log import logger


_PROTOCOL = "wss://"
_HOST = "tts.cloud.tencent.com"
_PATH = "/vc_stream"


class SpeechConvertListener(object):
    '''
    '''
    def on_convert_start(self, voice_id):
        logger.info("on_convert_start: voice_id={}".format(voice_id))

    def on_convert_end(self):
        logger.info("on_convert_end: -")

    def on_audio_result(self, audio_bytes):
        logger.info("on_audio_result: recv audio bytes, len={}".format(len(audio_bytes)))

    def on_convert_fail(self, response):
        logger.error("on_convert_fail: code={} msg={}".format(
            response['Code'], response['Message']
        ))


NOTOPEN = 0
STARTED = 1
OPENED = 2
FINAL = 3
ERROR = 4
CLOSED = 5

class SpeechConvertor:

    def __init__(self, appid, credential, listener):
        self.appid = appid
        self.credential = credential
        self.status = NOTOPEN
        self.ws = None
        self.wst = None
        self.listener = listener

        self.voice_id = ""
        self.voice_type = 301005
        self.codec = "pcm"
        self.sample_rate = 16000
        self.volume = 0
        self.speed = 0

    def set_voice_type(self, voice_type):
        self.voice_type = voice_type

    def set_codec(self, codec):
        self.codec = codec

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate

    def set_volume(self, volume):
        self.volume = volume

    def __gen_signature(self, params):
        sort_dict = sorted(params.keys())
        sign_str = _HOST + _PATH + '/' + str(self.appid) + "?"
        for key in sort_dict:
            sign_str = sign_str + key + "=" + str(params[key]) + '&'
        sign_str = sign_str[:-1]
        logger.info("sign_url={}".format(sign_str))
        secret_key = self.credential.secret_key.encode('utf-8')
        sign_str = sign_str.encode('utf-8')
        hmacstr = hmac.new(secret_key, sign_str, hashlib.sha1).digest()
        s = base64.b64encode(hmacstr)
        s = s.decode('utf-8')
        return s

    def __gen_params(self, voice_id):
        self.voice_id = voice_id

        params = dict()
        params['SecretId'] = self.credential.secret_id
        params['VoiceType'] = self.voice_type
        params['Codec'] = self.codec
        params['SampleRate'] = self.sample_rate
        params['Volume'] = self.volume
        params['VoiceId'] = self.voice_id
        params['End'] = 0

        timestamp = int(time.time())
        params['Timestamp'] = timestamp
        params['Expired'] = timestamp + 24 * 60 * 60
        return params

    def __create_query_string(self, param):
        param = sorted(param.items(), key=lambda d: d[0])

        url = _PROTOCOL + _HOST + _PATH + '/' + str(self.appid)

        signstr = url + "?"
        for x in param:
            tmp = x
            for t in tmp:
                signstr += str(t)
                signstr += "="
            signstr = signstr[:-1]
            signstr += "&"
        signstr = signstr[:-1]
        return signstr

    def start(self):
        logger.info("convertor start: begin")

        def _close_conn(reason):
            ta = time.time()
            self.ws.close()
            tb = time.time()
            logger.info("client has closed connection ({}), cost {} ms".format(reason, int((tb-ta)*1000)))

        def _on_data(ws, data, opcode, flag):
            # NOTE print all message that client received
            #logger.info("data={} opcode={} flag={}".format(data, opcode, flag))
            
            if opcode == ABNF.OPCODE_BINARY:
                length = int.from_bytes(data[:4], byteorder='big', signed=False)
                json_str = bytes.decode(data[4: length + 4])
                audio_data = data[4 + length:]
                logger.info("recv raw json: {}".format(json_str))
                
                resp = json.loads(json_str)
                if resp['Code'] != 0:
                    logger.error("server convert fail voice_id={} code={} msg_id={} msg={}".format(
                        resp['VoiceId'], resp['Code'], resp['MessageId'], resp['Message']
                    ))
                    self.listener.on_convert_fail(resp)
                    return
                
                # normal recv converted data
                self.listener.on_audio_result(audio_data) # <class 'bytes'>
                if "Final" in resp and resp['Final'] == 1:
                    logger.info("recv FINAL frame")
                    self.status = FINAL
                    _close_conn("after recv final")
                    self.listener.on_convert_end()
            elif opcode == ABNF.OPCODE_TEXT:
                pass
            else:
                logger.error("invalid on_data code, opcode=".format(opcode))

        def _on_error(ws, error):
            if self.status == FINAL or self.status == CLOSED:
                return
            self.status = ERROR
            logger.error("error={}, voice_id={}".format(error, self.voice_id))
            _close_conn("after recv error")

        def _on_close(ws, close_status_code, close_msg):
            logger.info("conn closed, close_status_code={} close_msg={}".format(close_status_code, close_msg))
            self.status = CLOSED

        def _on_open(ws):
            logger.info("conn opened")
            self.status = OPENED
            
        voice_id = str(uuid.uuid1())
        params = self.__gen_params(voice_id)
        signature = self.__gen_signature(params)
        requrl = self.__create_query_string(params)

        autho = urllib.parse.quote(signature)
        requrl += "&Signature=%s" % autho
        logger.info("req_url={}".format(requrl))

        self.ws = WebSocketApp(requrl, None,
            on_error=_on_error, on_close=_on_close,
            on_data=_on_data)
        self.ws.on_open = _on_open
        
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()
        self.status = STARTED
        self.listener.on_convert_start(voice_id)
        
        logger.info("convertor start: end")

    def wait(self):
        logger.info("convertor wait: begin")
        if self.ws:
            if self.wst and self.wst.is_alive():
                self.wst.join()
        logger.info("convertor wait: end")

    def send(self, audio_data, is_end=False):
        logger.info("convertor send: begin")
        if not self.ws:
            logger.error("convertor send: ws is None")
            return False
        if self.status != OPENED:
            logger.error("ws not opened, status={}".format(self.status))
            return False
        
        # message format: HEAD + JSON + AUDIO
        # refer to https://cloud.tencent.com/document/product/1664/85973#edac94f7-2e9d-4e59-aac3-fd1bea693be0
        json_body = json.dumps({
            "End": 1 if is_end else 0,
        })
        json_body_bytes = bytes(json_body, encoding='utf-8')
        json_body_len = len(json_body_bytes)
        
        head = json_body_len.to_bytes(4, byteorder='big')
        message = head + json_body_bytes + audio_data
        logger.info("send json_body_len={} json_body={} audio_len={}".format(
            json_body_len, json_body, len(audio_data)))
        
        self.ws.send(message, ABNF.OPCODE_BINARY)
        logger.info("convertor send: end")
        return True

    def wait_to_send(self):
        while True:
            if self.status < OPENED:
                time.sleep(0.01)
            else:
                break
        logger.info("wait_to_send: status={}".format(self.status))
        return self.status == OPENED
