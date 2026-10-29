# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.parse
import uuid

import websocket

logger = logging.getLogger("rsi_sdk")


class Credential:
    def __init__(self, secret_id, secret_key):
        self.secret_id = secret_id
        self.secret_key = secret_key


# 实时语音同传使用
class SpeechInterpretListener:
    '''
    response:
    on_session_start 的返回只有 voice_id 字段。
    on_fail、on_warn 只有 code、message、voice_id、final 字段。
    on_audio_data 的参数为译音 PCM 二进制数据，采样率与 input_sample_rate 一致。
    其余消息按 message_type 携带对应字段。
    code Integer
    message String
    voice_id String
    message_type String
    final Integer
    sentence_id String
    language String
    text String
    start_ts Integer
    end_ts Integer
    end_reason String
    reason String
    session Session

    Session 的结构体格式为:
    target String
    voice String
    '''

    def on_session_start(self, response):
        pass

    def on_session_ready(self, response):
        pass

    def on_subtitle_start(self, response):
        pass

    def on_subtitle_response(self, response):
        pass

    def on_subtitle_end(self, response):
        pass

    def on_tts_sentence_start(self, response):
        pass

    def on_sentence_skipped(self, response):
        pass

    def on_audio_data(self, data):
        pass

    def on_session_updated(self, response):
        pass

    def on_interpret_complete(self, response):
        pass

    def on_fail(self, response):
        pass

    def on_warn(self, response):
        pass


NOTOPEN = 0
STARTED = 1
OPENED = 2
FINAL = 3
ERROR = 4
CLOSED = 5

SIGN_EXPIRED_SEC = 24 * 60 * 60
STOP_TIMEOUT_SEC = 20
MESSAGE_TYPE_SUBTITLE_START = "TranslationSubtitleStart"
MESSAGE_TYPE_SUBTITLE_RESPONSE = "TranslationSubtitleResponse"
MESSAGE_TYPE_SUBTITLE_END = "TranslationSubtitleEnd"
MESSAGE_TYPE_TTS_SENTENCE_START = "TTSSentenceStart"
MESSAGE_TYPE_SENTENCE_SKIPPED = "TranslationSentenceSkipped"
MESSAGE_TYPE_SESSION_UPDATED = "session_updated"
END_REASON_SENSITIVE = "sensitive"


# 实时语音同传使用
class SpeechInterpreter:

    def __init__(self, appid, credential, target, input_sample_rate, listener):
        self.appid = appid
        self.credential = credential
        self.target = target
        # 音频采样率(Hz)，上行音频与下行译音共用
        self.input_sample_rate = input_sample_rate
        self.listener = listener

        self.status = NOTOPEN
        self.ws = None
        self.wst = None
        self.voice_id = ""
        self.voice = ""
        self.region = ""
        self.token = ""
        self.nonce = 0
        # 扩展参数：用于支持未公开参数或后续新增参数，无需升级 SDK。
        # key/value 会拼接到 ws URL 上并参与签名计算，同名 key 会覆盖 SDK 默认填充的字段。
        # 布尔值请传小写字符串 "true"/"false"。
        self.extra_params = {}
        self._write_dropped = False

    def set_voice(self, voice):
        """设置输出音色: clone、male、female，为空时使用服务端默认值"""
        self.voice = voice

    def set_region(self, region):
        self.region = region

    def set_token(self, token):
        self.token = token

    def set_voice_id(self, voice_id):
        self.voice_id = voice_id

    def set_nonce(self, nonce):
        self.nonce = nonce

    def set_extra_param(self, key, value):
        """设置单个扩展参数，同名 key 会覆盖 SDK 默认填充的字段"""
        if not key:
            return
        self.extra_params[key] = value

    def set_extra_params(self, params):
        """批量设置扩展参数，会与已有的 extra_params 合并（同名覆盖）"""
        if not params:
            return
        for k, v in params.items():
            if not k:
                continue
            self.extra_params[k] = v

    def format_sign_string(self, param):
        signstr = "asr.cloud.tencent.com/asr/si/%s?" % self.appid
        parts = []
        for k, v in param:
            if k in ("appid", "signature"):
                continue
            parts.append("%s=%s" % (k, v))
        signstr += "&".join(parts)
        return signstr

    def create_query_string(self, param):
        query = ["%s=%s" % (k, urllib.parse.quote(str(v), safe=""))
                 for k, v in param if k != "appid"]
        appid = urllib.parse.quote(str(self.appid), safe="")
        return "wss://asr.cloud.tencent.com/asr/si/%s?%s" % (
            appid, "&".join(query))

    def sign(self, signstr, secret_key):
        hmacstr = hmac.new(secret_key.encode("utf-8"),
                           signstr.encode("utf-8"), hashlib.sha1).digest()
        return base64.b64encode(hmacstr).decode("utf-8")

    def create_query_arr(self):
        query_arr = dict()
        query_arr["appid"] = self.appid
        query_arr["secretid"] = self.credential.secret_id
        query_arr["timestamp"] = int(time.time())
        query_arr["expired"] = int(time.time()) + SIGN_EXPIRED_SEC
        if self.nonce > 0:
            query_arr["nonce"] = self.nonce
        else:
            query_arr["nonce"] = query_arr["timestamp"]
        if self.voice_id == "":
            self.voice_id = str(uuid.uuid1())
        query_arr["voice_id"] = self.voice_id
        query_arr["target"] = self.target
        query_arr["input_sample_rate"] = self.input_sample_rate
        if self.voice != "":
            query_arr["voice"] = self.voice
        if self.region != "":
            query_arr["region"] = self.region
        if self.token != "":
            query_arr["token"] = self.token
        # 合并扩展参数：放在最后，允许覆盖 SDK 默认填充的字段；空 key 直接忽略
        for k, v in self.extra_params.items():
            if not k:
                continue
            query_arr[k] = v
        return query_arr

    def write(self, data):
        '''
        发送一块音频数据。返回 False 表示会话已终止或未就绪，调用方须停止推流。
        '''
        while self.status == STARTED:
            time.sleep(0.1)
        if self.status == OPENED:
            try:
                self.ws.sock.send_binary(data)
                return True
            except Exception as e:
                logger.error("%s write fail %s" % (self.voice_id, e))
                self.status = ERROR
                return False
        if not self._write_dropped:
            self._write_dropped = True
            logger.warning("%s write dropped, status %d" %
                           (self.voice_id, self.status))
        return False

    def update_session(self, target, voice=""):
        '''
        运行中变更目标语种与输出音色。

        约束与注意事项:
        1. 必须在 start() 之后、stop() 之前调用；
        2. voice 为空表示沿用当前音色；
        3. 取值不合法时服务端返回 code=6001 的 on_warn 回调并沿用原配置，不中断会话；
        4. 返回 True 只代表控制帧已发出，是否生效以 on_session_updated 回调为准。

        返回: True 表示控制帧已发送；False 表示本地校验未通过或连接未就绪。
        '''
        if not target:
            logger.error("%s update session fail, empty target" %
                         self.voice_id)
            return False
        while self.status == STARTED:
            time.sleep(0.1)
        if self.status != OPENED:
            logger.error("%s update session fail, status %d" %
                         (self.voice_id, self.status))
            return False
        msg = {"type": "update", "target": target}
        if voice:
            msg["voice"] = voice
        try:
            self.ws.sock.send(json.dumps(msg))
        except Exception as e:
            logger.error("%s update session fail %s" % (self.voice_id, e))
            self.status = ERROR
            return False
        self.target = target
        if voice:
            self.voice = voice
        logger.info("%s update session to target %s voice %s" %
                    (self.voice_id, target, voice))
        return True

    def stop(self, timeout=STOP_TIMEOUT_SEC):
        if self.status == OPENED:
            try:
                self.ws.sock.send(json.dumps({"type": "end"}))
            except Exception as e:
                logger.error("%s send end frame fail %s" % (self.voice_id, e))
        if self.ws:
            if self.wst and self.wst.is_alive():
                self.wst.join(timeout)
                if self.wst.is_alive():
                    logger.warning("%s wait final result timeout in %ds, "
                                   "status %d" % (self.voice_id, timeout,
                                                  self.status))
            self.ws.close()

    def start(self):
        def on_message(ws, message):
            if isinstance(message, bytes):
                self.listener.on_audio_data(message)
                return
            response = json.loads(message)
            if "voice_id" not in response:
                response["voice_id"] = self.voice_id
            if response.get("code", 0) != 0:
                if response.get("final", 0) == 1:
                    logger.error("%s server interpret fail %s" % (
                        response["voice_id"], response.get("message")))
                    self.status = ERROR
                    self.listener.on_fail(response)
                    self.ws.close()
                else:
                    logger.warning("%s server interpret warn %s" % (
                        response["voice_id"], response.get("message")))
                    self.listener.on_warn(response)
                return
            if response.get("final", 0) == 1:
                self.status = FINAL
                self.listener.on_interpret_complete(response)
                logger.info("%s interpret complete" % response["voice_id"])
                self.ws.close()
                return
            msg_type = response.get("message_type")
            if msg_type == MESSAGE_TYPE_SUBTITLE_START:
                self.listener.on_subtitle_start(response)
                return
            if msg_type == MESSAGE_TYPE_SUBTITLE_RESPONSE:
                self.listener.on_subtitle_response(response)
                return
            if msg_type == MESSAGE_TYPE_SUBTITLE_END:
                self.listener.on_subtitle_end(response)
                return
            if msg_type == MESSAGE_TYPE_TTS_SENTENCE_START:
                self.listener.on_tts_sentence_start(response)
                return
            if msg_type == MESSAGE_TYPE_SENTENCE_SKIPPED:
                self.listener.on_sentence_skipped(response)
                return
            if msg_type == MESSAGE_TYPE_SESSION_UPDATED:
                self.listener.on_session_updated(response)
                return
            self.listener.on_session_ready(response)

        def on_error(ws, error):
            if self.status in (FINAL, ERROR):
                return
            logger.error("websocket error %s voice id %s" %
                         (format(error), self.voice_id))
            self.status = ERROR

        def on_close(ws, *args):
            self.status = CLOSED
            logger.info("websocket closed voice id %s" % self.voice_id)

        def on_open(ws):
            self.status = OPENED

        query_arr = self.create_query_arr()
        query = sorted(query_arr.items(), key=lambda d: d[0])
        signstr = self.format_sign_string(query)
        autho = urllib.parse.quote(self.sign(signstr,
                                             self.credential.secret_key))
        requrl = self.create_query_string(query)
        requrl += "&signature=%s" % autho

        self.ws = websocket.WebSocketApp(requrl, None,
                                         on_error=on_error,
                                         on_close=on_close,
                                         on_message=on_message)
        self.ws.on_open = on_open
        self.status = STARTED
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()
        response = {"voice_id": self.voice_id}
        self.listener.on_session_start(response)
        logger.info("%s interpret start" % self.voice_id)
