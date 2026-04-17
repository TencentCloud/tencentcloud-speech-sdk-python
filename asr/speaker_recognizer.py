# -*- coding: utf-8 -*-
import sys
import hmac
import hashlib
import base64
import time
import json
import threading
import uuid
import urllib

import websocket

from common.log import logger


def _is_python3():
    return sys.version_info[0] >= 3


# ---------------------------------------------------------------------------
# Listener base class – user must subclass and override callbacks
# ---------------------------------------------------------------------------
class SpeakerRecognitionListener:
    """
    response 是 dict，字段说明：
      code             int
      message          str
      voice_id         str
      message_id       str   (可选)
      speaker_context_id str  (可选，仅首包)
      final            int   (可选)
      sentences         dict  (可选)
        └ sentence_list  list[dict]
            ├ sentence       str
            ├ sentence_type  int   (0=中间, 1=最终)
            ├ sentence_id    int
            ├ speaker_id     int
            ├ start_time     int
            └ end_time       int
    """

    def on_recognition_start(self, response):
        pass

    def on_recognition_sentences(self, response):
        pass

    def on_sentence_end(self, response):
        pass

    def on_fail(self, response):
        pass


# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------
_NOTOPEN = 0
_STARTED = 1
_OPENED = 2
_FINAL = 3
_ERROR = 4
_CLOSED = 5


# ---------------------------------------------------------------------------
# SpeakerRecognizer  –  sentence-mode ASR with speaker context
# ---------------------------------------------------------------------------
class SpeakerRecognizer:

    def __init__(self, appid, credential, engine_model_type, listener):
        self.appid = appid
        self.credential = credential
        self.engine_model_type = engine_model_type
        self.listener = listener

        # request params (defaults aligned with Go SDK)
        self.voice_format = 1
        self.need_vad = 1
        self.convert_num_mode = 1
        self.reinforce_hotword = 0
        self.vad_silence_time = 0
        self.noise_threshold = 0
        self.hotword_id = ""
        self.hotword_list = ""
        self.customization_id = ""
        self.replace_text_id = ""
        self.sentence_strategy = 1

        # speaker context params
        self.speaker_diarization = 0
        self.enable_speaker_context = 0
        self.speaker_context_id = ""
        self.language_judgment = 0
        self.emotion_recognition = 0

        # internal state
        self.voice_id = ""
        self._status = _NOTOPEN
        self._ws = None
        self._wst = None

    # ---- setters (keep style consistent with existing Python SDK) ---------

    def set_voice_format(self, v):
        self.voice_format = v

    def set_need_vad(self, v):
        self.need_vad = v

    def set_convert_num_mode(self, v):
        self.convert_num_mode = v

    def set_reinforce_hotword(self, v):
        self.reinforce_hotword = v

    def set_vad_silence_time(self, v):
        self.vad_silence_time = v

    def set_noise_threshold(self, v):
        self.noise_threshold = v

    def set_hotword_id(self, v):
        self.hotword_id = v

    def set_hotword_list(self, v):
        self.hotword_list = v

    def set_customization_id(self, v):
        self.customization_id = v

    def set_replace_text_id(self, v):
        self.replace_text_id = v

    def set_sentence_strategy(self, v):
        self.sentence_strategy = v

    def set_speaker_diarization(self, v):
        self.speaker_diarization = v

    def set_enable_speaker_context(self, v):
        self.enable_speaker_context = v

    def set_speaker_context_id(self, v):
        self.speaker_context_id = v

    def set_language_judgment(self, v):
        self.language_judgment = v

    def set_emotion_recognition(self, v):
        self.emotion_recognition = v

    # ---- URL / signature --------------------------------------------------

    def _create_query_arr(self):
        ts = str(int(time.time()))
        q = dict()
        q['appid'] = self.appid
        q['secretid'] = self.credential.secret_id
        q['timestamp'] = ts
        q['nonce'] = ts
        q['expired'] = int(time.time()) + 24 * 60 * 60

        q['engine_model_type'] = self.engine_model_type
        q['voice_id'] = self.voice_id
        q['voice_format'] = self.voice_format
        q['needvad'] = self.need_vad

        # 强制句子模式
        q['result_mod'] = 1
        q['sentence_strategy'] = self.sentence_strategy

        # speaker context
        q['speaker_diarization'] = self.speaker_diarization
        q['enable_speaker_context'] = self.enable_speaker_context
        q['speaker_context_id'] = self.speaker_context_id
        q['language_judgment'] = self.language_judgment
        q['emotion_recognition'] = self.emotion_recognition

        if self.hotword_id:
            q['hotword_id'] = self.hotword_id
        if self.hotword_list:
            q['hotword_list'] = self.hotword_list
        if self.customization_id:
            q['customization_id'] = self.customization_id
        if self.replace_text_id:
            q['replace_text_id'] = self.replace_text_id

        q['convert_num_mode'] = self.convert_num_mode
        q['reinforce_hotword'] = self.reinforce_hotword

        if self.vad_silence_time > 0:
            q['vad_silence_time'] = self.vad_silence_time
        if self.noise_threshold != 0:
            q['noise_threshold'] = self.noise_threshold

        return q

    @staticmethod
    def _format_sign_string(sorted_params):
        """构建待签名字符串（不含 wss:// 前缀）"""
        signstr = "asr.cloud.tencent.com/asr/v2/"
        for k, v in sorted_params:
            if k == 'appid':
                signstr += str(v)
                break
        signstr += "?"
        for k, v in sorted_params:
            if k == 'appid':
                continue
            signstr += "%s=%s&" % (k, v)
        return signstr[:-1]

    @staticmethod
    def _create_query_string(sorted_params):
        """构建完整 wss URL（不含 signature）"""
        url = "wss://asr.cloud.tencent.com/asr/v2/"
        for k, v in sorted_params:
            if k == 'appid':
                url += str(v)
                break
        url += "?"
        for k, v in sorted_params:
            if k == 'appid':
                continue
            url += "%s=%s&" % (k, v)
        return url[:-1]

    @staticmethod
    def _sign(signstr, secret_key):
        hmacstr = hmac.new(
            secret_key.encode('utf-8'),
            signstr.encode('utf-8'),
            hashlib.sha1,
        ).digest()
        return base64.b64encode(hmacstr).decode('utf-8')

    # ---- lifecycle --------------------------------------------------------

    def start(self):
        if self.voice_id == "":
            self.voice_id = str(uuid.uuid1())

        query_arr = self._create_query_arr()
        sorted_params = sorted(query_arr.items(), key=lambda d: d[0])
        signstr = self._format_sign_string(sorted_params)
        signature = self._sign(signstr, self.credential.secret_key)
        requrl = self._create_query_string(sorted_params)

        if _is_python3():
            signature = urllib.parse.quote(signature)
        else:
            signature = urllib.quote(signature)
        requrl += "&signature=%s" % signature

        # ---------- synchronous connect + read first message ---------------
        ws_conn = websocket.create_connection(requrl)
        first_msg = ws_conn.recv()
        first_resp = json.loads(first_msg)

        if first_resp.get('code', -1) != 0:
            ws_conn.close()
            raise RuntimeError(
                "voice_id: %s, code: %d, message: %s"
                % (self.voice_id, first_resp.get('code', -1),
                   first_resp.get('message', ''))
            )

        # 回写服务端返回的 speaker_context_id
        ctx_id = first_resp.get('speaker_context_id', '')
        if ctx_id:
            self.speaker_context_id = ctx_id

        self._ws_conn = ws_conn
        self._status = _OPENED

        # fire on_recognition_start
        start_resp = {
            'code': 0,
            'message': 'success',
            'voice_id': self.voice_id,
            'speaker_context_id': self.speaker_context_id,
        }
        self.listener.on_recognition_start(start_resp)
        logger.info("%s speaker recognition start" % self.voice_id)

        # start receive thread
        self._recv_thread = threading.Thread(target=self._receive_loop)
        self._recv_thread.daemon = True
        self._recv_thread.start()

    def write(self, data):
        if self._status != _OPENED:
            return
        self._ws_conn.send_binary(data)

    def stop(self):
        if self._status == _OPENED:
            try:
                self._ws_conn.send(json.dumps({"type": "end"}))
            except Exception:
                pass
        if hasattr(self, '_recv_thread') and self._recv_thread.is_alive():
            self._recv_thread.join()
        try:
            self._ws_conn.close()
        except Exception:
            pass
        self._status = _CLOSED

    # ---- internal receive loop --------------------------------------------

    def _receive_loop(self):
        try:
            while True:
                data = self._ws_conn.recv()
                if not data:
                    break
                msg = json.loads(data)
                msg['voice_id'] = self.voice_id

                if msg.get('code', 0) != 0:
                    self._status = _ERROR
                    self.listener.on_fail(msg)
                    logger.error(
                        "%s server fail code=%d message=%s"
                        % (self.voice_id, msg['code'], msg.get('message', ''))
                    )
                    break

                if msg.get('final', 0) == 1:
                    self._status = _FINAL
                    self.listener.on_sentence_end(msg)
                    logger.info("%s speaker recognition complete" % self.voice_id)
                    break

                # 句子模式：每条消息都是句子列表
                self.listener.on_recognition_sentences(msg)

        except Exception as e:
            if self._status in (_FINAL, _CLOSED):
                return
            self._status = _ERROR
            fail_resp = {
                'code': -1,
                'message': str(e),
                'voice_id': self.voice_id,
            }
            self.listener.on_fail(fail_resp)
            logger.error(
                "%s receive error: %s" % (self.voice_id, e)
            )
