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
from common.utils import is_python3


_PROTOCOL = "wss://"
_HOST = "tts.cloud.tencent.com"
_PATH = "/stream_ws_podcast"
_ACTION = "TextToPodcastStreamAudioWS"


class SpeechSynthesisListener(object):
    '''
    '''
    def on_synthesis_start(self, session_id):
        logger.info("on_synthesis_start: session_id={}".format(session_id))

    def on_synthesis_end(self):
        logger.info("on_synthesis_end: -")

    def on_audio_result(self, audio_bytes):
        logger.info("on_audio_result: recv audio bytes, len={}".format(len(audio_bytes)))

    def on_text_result(self, response):
        session_id = response["session_id"]
        request_id = response["request_id"]
        message_id = response["message_id"]
        result = response['result']
        if "context_id" in result:
            context_id = result["context_id"]
        scripts = []
        if "scripts" in result and len(result["scripts"]) > 0:
            scripts = result["scripts"]
            # logger.info("on_text_result: session_id={} request_id={} message_id={}\ncontext_id={}\nscripts={}".format(
            #     session_id, request_id, message_id, context_id, scripts))

        if "usage_tokens" in result and len(result["usage_tokens"]) >= 2:
            input_token = result["usage_tokens"][0]
            output_token = result["usage_tokens"][1]
            # logger.info("on_text_result: input_token={} output_token={}".format(input_token, output_token))

    def on_synthesis_fail(self, response):
        logger.error("on_synthesis_fail: code={} msg={}".format(
            response['code'], response['message']
        ))


NOTOPEN = 0
STARTED = 1
OPENED = 2
FINAL = 3
ERROR = 4
CLOSED = 5

MAX_INPUT_OBJECT_NUM = 10

INPUT_OBJECT_TYPE_TEXT = "TYPE_TEXT"
INPUT_OBJECT_TYPE_URL = "TYPE_URL"
INPUT_OBJECT_TYPE_FILE = "TYPE_FILE"

SUPPORT_FILE_FORMAT = ["txt", "md", "pdf", "docx"]

class InputObject:
    def __init__(self):
        self.object_type = ""
        self.text = ""
        self.url = ""
        self.file_data = ""
        self.file_format = ""
    
    def set_text(self, text):
        self.object_type = INPUT_OBJECT_TYPE_TEXT
        self.text = text

    def set_url(self, url):
        self.object_type = INPUT_OBJECT_TYPE_URL
        self.url = url

    def set_file(self, file_format, file_data):
        self.object_type = INPUT_OBJECT_TYPE_FILE
        self.file_format = file_format
        self.file_data = file_data

    def set_file_url(self, file_format, file_url):
        self.object_type = INPUT_OBJECT_TYPE_FILE
        self.file_format = file_format
        self.url = file_url

    def to_dict(self):
        return {
            "ObjectType": self.object_type,
            "Text": self.text,
            "Url": self.url,
            "FileFormat": self.file_format,
            "FileData": self.file_data
        }

SpeechSynthesizer_ACTION_SYNTHESIS = "ACTION_SYNTHESIS"
SpeechSynthesizer_ACTION_COMPLETE = "ACTION_COMPLETE"
SpeechSynthesizer_ACTION_CANCEL = "ACTION_CANCEL"


class SpeechSynthesizer:

    def __init__(self, appid, credential, listener):
        self.appid = appid
        self.credential = credential
        self.status = NOTOPEN
        self.ws = None
        self.wst = None
        self.listener = listener

        self.ready = False

        self.codec = "pcm"
        self.sample_rate = 16000
        self.speaker_number = 0
        self.speaker1_voice = ""
        self.speaker2_voice = ""
        self.input_object_list = []
        self.session_id = ""
        self.context_id = ""
        self.enable_web_search = True

        self.resp_code = 0
        self.resp_message = ""

    def set_codec(self, codec):
        self.codec = codec

    def set_sample_rate(self, sample_rate):
        self.sample_rate = sample_rate
    
    def set_speaker_number(self, speaker_number, speaker1_voice="", speaker2_voice=""):
        self.speaker_number = speaker_number
        if speaker_number == 1:
            if not speaker1_voice:
                return False, "speaker1 voice is empty"
            self.speaker1_voice = speaker1_voice
        elif speaker_number == 2:
            if not speaker1_voice:
                return False, "speaker1 voice is empty"
            if not speaker2_voice:
                return False, "speaker2 voice is empty"
            self.speaker1_voice = speaker1_voice
            self.speaker2_voice = speaker2_voice
        return True, ""
    
    def set_context_id(self, context_id):
        self.context_id = context_id
    
    def set_enable_web_search(self, enable_web_search):
        self.enable_web_search = enable_web_search
    
    def _add_input_object(self, input_object):
        self.input_object_list.append(input_object)
        return True, ""
    
    def add_text(self, text):
        input_object = InputObject()
        input_object.set_text(text)
        return self._add_input_object(input_object)
    
    def add_url(self, url):
        input_object = InputObject()
        input_object.set_url(url)
        return self._add_input_object(input_object)
    
    def add_file_url(self, file_format, file_url):
        if file_format not in SUPPORT_FILE_FORMAT:
            return False, "unsupported file format"
        
        input_object = InputObject()
        input_object.set_file_url(file_format, file_url)
        return self._add_input_object(input_object)

    def get_resp(self):
        return self.resp_code, self.resp_message

    def __gen_signature(self, params):
        sort_dict = sorted(params.keys())
        sign_str = "GET" + _HOST + _PATH + "?"
        for key in sort_dict:
            sign_str = sign_str + key + "=" + str(params[key]) + '&'
        sign_str = sign_str[:-1]
        print(sign_str)
        if is_python3():
            secret_key = self.credential.secret_key.encode('utf-8')
            sign_str = sign_str.encode('utf-8')
        else:
            secret_key = self.credential.secret_key
        hmacstr = hmac.new(secret_key, sign_str, hashlib.sha1).digest()
        s = base64.b64encode(hmacstr)
        s = s.decode('utf-8')
        return s

    def __gen_params(self, session_id, is_cam=False):
        self.session_id = session_id

        params = dict()
        params['Action'] = _ACTION
        params['AppId'] = int(self.appid)
        params['SecretId'] = self.credential.secret_id
        params['Codec'] = self.codec
        params['SampleRate'] = self.sample_rate

        if self.speaker_number == 1:
            params['SpeakerNumber'] = self.speaker_number
            params['Speaker1Voice'] = self.speaker1_voice
        elif self.speaker_number == 2:
            params['SpeakerNumber'] = self.speaker_number
            params['Speaker1Voice'] = self.speaker1_voice
            params['Speaker2Voice'] = self.speaker2_voice
        
        if self.context_id != "":
            params['ContextId'] = self.context_id
        
        if self.enable_web_search is False:
            params['EnableWebSearch'] = False
        
        params['SessionId'] = self.session_id
        
        timestamp = int(time.time())
        params['Timestamp'] = timestamp
        params['Expired'] = timestamp + 24 * 60 * 60
        return params

    def __create_query_string(self, param):
        param = sorted(param.items(), key=lambda d: d[0])

        url = _PROTOCOL + _HOST + _PATH

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

    def __new_ws_request_message(self, action, data):
        return {
            "session_id": self.session_id,
            "message_id": str(uuid.uuid1()),

            "action": action,
            "data": data,
        }
    
    def __do_send(self, action, text):
        self.wait_ready()
        WSRequestMessage = self.__new_ws_request_message(action, text)
        data = json.dumps(WSRequestMessage)
        opcode = websocket.ABNF.OPCODE_TEXT
        logger.info("ws send opcode={} data={}".format(opcode, data))
        self.ws.send(data, opcode)

    def send_input_object_list(self, action=SpeechSynthesizer_ACTION_SYNTHESIS):
        idx = 0
        for input_object in self.input_object_list:
            input_object_str = json.dumps(input_object.to_dict())
            logger.info("process[{}]: action={} data={}".format(idx, action, input_object_str))
            self.__do_send(action, input_object_str)
            idx += 1

    def complete(self, action = SpeechSynthesizer_ACTION_COMPLETE):
        logger.info("complete: action={}".format(action))
        self.__do_send(action, "")

    def cancel(self, action = SpeechSynthesizer_ACTION_CANCEL):
        logger.info("cancel: action={}".format(action))
        self.__do_send(action, "")

    def process(self, action=SpeechSynthesizer_ACTION_SYNTHESIS):
        # NOTE: 等待服务器ready
        self.wait_ready()
        # NOTE: 发送输入对象列表
        self.send_input_object_list()
        # NOTE: 发送complete事件通知服务端启动合成，否则服务端会一直等待
        self.complete()

    def wait_ready(self, timeout_ms=0):
        timeout_start = int(time.time() * 1000)
        while True:
            if self.ready:
                return True
            if timeout_ms!=0 and int(time.time() * 1000) - timeout_start > timeout_ms:
                break
            time.sleep(0.01)
        return False

    def start(self):
        logger.info("synthesizer start: begin")

        def _close_conn(reason):
            ta = time.time()
            self.ws.close()
            tb = time.time()
            logger.info("client has closed connection ({}), cost {} ms".format(reason, int((tb-ta)*1000)))

        def _on_data(ws, data, opcode, flag):
            logger.debug("data={} opcode={} flag={}".format(data, opcode, flag))
            if opcode == websocket.ABNF.OPCODE_BINARY:
                self.listener.on_audio_result(data) # <class 'bytes'>
                pass
            elif opcode == websocket.ABNF.OPCODE_TEXT:
                logger.info("data={} opcode={} flag={}".format(data, opcode, flag))
                resp = json.loads(data) # WSResponseMessage
                if resp['code'] != 0:
                    logger.error("server synthesis fail request_id={} code={} msg={}".format(
                        resp['request_id'], resp['code'], resp['message']
                    ))
                    self.resp_code = resp['code']
                    self.resp_message = resp['message']
                    self.listener.on_synthesis_fail(resp)
                    return
                if "final" in resp and resp['final'] == 1:
                    logger.info("recv FINAL frame")
                    self.status = FINAL
                    _close_conn("after recv final")
                    self.listener.on_synthesis_end()
                    return
                if "ready" in resp and resp['ready'] == 1:
                    logger.info("recv READY frame")
                    self.ready = True
                    return
                if "ping" in resp and resp['ping'] == 1:
                    logger.info("recv PING frame")
                    return
                if "result" in resp:
                    self.listener.on_text_result(resp)
                    return
            else:
                logger.error("invalid on_data code, opcode=".format(opcode))

        def _on_error(ws, error):
            if self.status == FINAL or self.status == CLOSED:
                return
            self.status = ERROR
            logger.error("error={}, session_id={}".format(error, self.session_id))
            _close_conn("after recv error")

        def _on_close(ws, close_status_code, close_msg):
            logger.info("conn closed, close_status_code={} close_msg={}".format(close_status_code, close_msg))
            self.status = CLOSED

        def _on_open(ws):
            logger.info("conn opened")
            self.status = OPENED
            
        session_id = str(uuid.uuid1())
        params_cam = self.__gen_params(session_id, True)
        signature = self.__gen_signature(params_cam)
        params_query = self.__gen_params(session_id, False)
        requrl = self.__create_query_string(params_query)

        if is_python3():
            autho = urllib.parse.quote(signature)
        else:
            autho = urllib.quote(signature)
        requrl += "&Signature=%s" % autho
        print(requrl)

        self.ws = websocket.WebSocketApp(requrl, None,# header=headers,
            on_error=_on_error, on_close=_on_close,
            on_data=_on_data)
        self.ws.on_open = _on_open

        self.status = STARTED
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()
        self.listener.on_synthesis_start(session_id)
        
        logger.info("synthesizer start: end")

    def wait(self):
        logger.info("synthesizer wait: begin")
        if self.ws:
            if self.wst and self.wst.is_alive():
                self.wst.join()
        logger.info("synthesizer wait: end")
