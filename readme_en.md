# Introduction

Welcome to the Tencent Cloud Speech SDK. The Tencent Cloud Speech SDK provides developers with a set of tools for accessing Tencent Cloud speech services such as Automatic Speech Recognition (ASR) and Text-to-Speech (TTS), simplifying the integration process with Tencent Cloud speech services.

This project is the Python version of the Tencent Cloud Speech SDK.

# Requirements

1. Python environment
2. Install `websocket`, `websocket-client`, and `requests` via pip.
   Note: `websocket-client` must be version 0.48.
3. Get your account APPID from the [Account Info](https://console.cloud.tencent.com/developer) page in the Tencent Cloud console, and obtain your SecretID and SecretKey from the [CAM (Cloud Access Management)](https://console.cloud.tencent.com/cam/capi) page.

Note: TTS WebSocket only supports Python 3. You need to install the `websocket-client` package before using it, as shown below:
```
pip3 install websocket-client
```

# Examples

See the [examples](https://github.com/TencentCloud/tencentcloud-speech-sdk-python/tree/master/examples) directory, which contains sample code for each speech service.
