# -*- coding: utf-8 -*-
import requests
import hmac
import hashlib
import base64
import time
import random
import os
import json
from common import credential

class FlashRecognizer:
    '''
    reponse:  
    字段名	            类型	
    request_id        string
    status 	          Integer	
    message	          String	
    audio_duration    Integer
    flash_result      Result Array

    Result的结构体格式为:
    text              String
    channel_id        Integer
    sentence_list     Sentence Array

    Sentence的结构体格式为:
    text              String
    start_time	      Integer	
    end_time	      Integer	
    speaker_id        Integer	
    word_list         Word Array

    Word的类型为:
    word              String 
    start_time        Integer 
    end_time          Integer 
    stable_flag：     Integer 
    '''

    def __init__(self, appid, credential, engine_type):
        self.credential = credential
        self.appid = appid
        self.engine_type = engine_type
        self.speaker_diarization = 0
        self.filter_dirty = 0
        self.filter_modal = 0
        self.filter_punc = 0
        self.convert_num_mode = 1
        self.word_info = 0
        self.hotword_id = ""
        self.voice_format = ""
        self.first_channel_only = 1

    def set_first_channel_only(self, first_channel_only):
        self.first_channel_only = first_channel_only

    def set_speaker_diarization(self, speaker_diarization):
        self.speaker_diarization = speaker_diarization

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

    def set_hotword_id(self, hotword_id):
        self.hotword_id = hotword_id

    def set_voice_format(self, voice_format):
        self.voice_format = voice_format

    def _format_sign_string(self, param):
        signstr = "POSTasr.cloud.tencent.com/asr/flash/v1/"
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

    def _build_header(self):
        header = dict()
        header["Host"] = "asr.cloud.tencent.com"
        return header

    def _sign(self, signstr, secret_key):
        hmacstr = hmac.new(secret_key.encode('utf-8'),
                           signstr.encode('utf-8'), hashlib.sha1).digest()
        s = base64.b64encode(hmacstr)
        s = s.decode('utf-8')
        return s

    def _build_req_with_signature(self, secret_key, params, header):
        query = sorted(params.items(), key=lambda d: d[0])
        signstr = self._format_sign_string(query)
        signature = self._sign(signstr, secret_key)
        header["Authorization"] = signature
        requrl = "https://"
        requrl += signstr[4::]
        return requrl

    def _create_query_arr(self):
        query_arr = dict()
        query_arr['appid'] = self.appid
        query_arr['secretid'] = self.credential.secret_id
        query_arr['timestamp'] = str(int(time.time()))
        query_arr['engine_type'] = self.engine_type
        query_arr['voice_format'] = self.voice_format
        query_arr['speaker_diarization'] = self.speaker_diarization
        query_arr['hotword_id'] = self.hotword_id
        query_arr['filter_dirty'] = self.filter_dirty
        query_arr['filter_modal'] = self.filter_modal
        query_arr['filter_punc'] = self.filter_punc
        query_arr['convert_num_mode'] = self.convert_num_mode
        query_arr['word_info'] = self.word_info
        query_arr['first_channel_only'] = self.first_channel_only
        return query_arr

    def do_recognize(self, data):
        header = self._build_header()
        req = self._create_query_arr()
        req_url = self._build_req_with_signature(self.credential.secret_key, req, header)
        r = requests.post(req_url, headers=header, data=data)
        return r.text
