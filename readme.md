# 简介

欢迎使用腾讯云语音SDK，腾讯云语音SDK为开发者提供了访问腾讯云语音识别、语音合成等语音服务的配套开发工具，简化腾讯云语音服务的接入流程。

本项目是腾讯云语音SDK的python语言版本。

# 依赖环境

1. python 环境
2. pip命令行安装websocket, websocket-client, requests
   注意:websocket-client必须是0.48版本
3. 在腾讯云控制台[账号信息](https://console.cloud.tencent.com/developer)页面查看账号APPID，[访问管理](https://console.cloud.tencent.com/cam/capi)页面获取 SecretID 和 SecretKey 。

注：TTS websocket，仅支持python3，使用前需安装websocket-client包，如下
```
pip3 install websocket-client
```

# 示例

参见 [examples](https://github.com/TencentCloud/tencentcloud-speech-sdk-python/tree/master/examples) 目录，该目录下包含各语音服务的示例代码。
