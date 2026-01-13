import os
import logging
import aiohttp
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ForwarderType(Enum):
    """转发器类型"""
    WECOM = "wecom"  # 企业微信群机器人
    WECOM_APP = "wecom-app"  # 企业微信应用
    FEISHU = "feishu"  # 飞书
    CUSTOM = "custom"  # 自定义 HTTP API


class BaseForwarder(ABC):
    """转发器基类"""

    @abstractmethod
    async def send(self, content: Dict) -> bool:
        """
        发送消息
        :param content: 消息内容字典
        :return: 是否发送成功
        """
        pass

    async def _post_json(self, url: str, data: Dict, headers: Optional[Dict] = None) -> bool:
        """发送 POST 请求"""
        try:
            default_headers = {'Content-Type': 'application/json'}
            if headers:
                default_headers.update(headers)

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=data, headers=default_headers) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.debug(f"发送成功: {result}")
                        return True
                    else:
                        text = await resp.text()
                        logger.error(f"发送失败，状态码: {resp.status}, 响应: {text}")
                        return False
        except Exception as e:
            logger.error(f"发送请求时出错: {e}")
            return False


class WeComForwarder(BaseForwarder):
    """企业微信群机器人转发器"""

    def __init__(self):
        self.webhook_url = os.getenv('WECOM_WEBHOOK_URL')
        if not self.webhook_url:
            logger.error("未配置 WECOM_WEBHOOK_URL")

    async def send(self, content: Dict) -> bool:
        if not self.webhook_url:
            return False

        # 构建企业微信消息格式
        message = f"**{content['chat_title']}**\n"
        message += f"消息: {content['message']}\n"
        message += f"发送者: {content['sender']}"

        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": message
            }
        }

        return await self._post_json(self.webhook_url, data)


class WeComAppForwarder(BaseForwarder):
    """企业微信应用转发器"""

    def __init__(self):
        self.corpid = os.getenv('WECOM_CORPID')
        self.corpsecret = os.getenv('WECOM_CORPSECRET')
        self.agentid = os.getenv('WECOM_AGENTID')
        self.touser = os.getenv('WECOM_TOUSER', '@all')  # 默认发送给所有人

        # Access token 缓存
        self._access_token = None
        self._token_expires_at = 0

        if not all([self.corpid, self.corpsecret, self.agentid]):
            logger.error("未配置完整的企业微信应用参数 (WECOM_CORPID, WECOM_CORPSECRET, WECOM_AGENTID)")

    async def _get_access_token(self) -> Optional[str]:
        """获取 access_token，带缓存机制"""
        # 如果 token 还有效（提前 5 分钟刷新），直接返回缓存
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        # 获取新 token
        try:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            params = {
                'corpid': self.corpid,
                'corpsecret': self.corpsecret
            }

            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"获取 access_token 失败，状态码: {resp.status}")
                        return None

                    data = await resp.json()
                    if data.get('errcode') != 0:
                        logger.error(f"获取 access_token 失败: {data.get('errmsg')}")
                        return None

                    self._access_token = data['access_token']
                    self._token_expires_at = time.time() + data.get('expires_in', 7200)

                    logger.info(
                        f"成功获取 access_token，有效期至: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._token_expires_at))}")
                    return self._access_token

        except Exception as e:
            logger.error(f"获取 access_token 时出错: {e}")
            return None

    async def send(self, content: Dict) -> bool:
        if not all([self.corpid, self.corpsecret, self.agentid]):
            return False

        # 获取 access_token
        access_token = await self._get_access_token()
        if not access_token:
            return False

        # 构建消息内容
        message_text = f"{content['chat_title']}\n"
        message_text += f"消息: {content['message']}\n"
        message_text += f"发送者: {content['sender']}"

        # 构建发送消息的请求
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
        data = {
            "touser": self.touser,
            "msgtype": "text",
            "agentid": int(self.agentid),
            "text": {
                "content": message_text
            },
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0
        }

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=data) as resp:
                    if resp.status != 200:
                        logger.error(f"发送消息失败，状态码: {resp.status}")
                        return False

                    result = await resp.json()
                    if result.get('errcode') != 0:
                        logger.error(f"发送消息失败: {result.get('errmsg')}")
                        # 如果是 token 过期，清除缓存
                        if result.get('errcode') in [40014, 42001]:
                            self._access_token = None
                            self._token_expires_at = 0
                        return False

                    logger.debug(f"消息发送成功: {result}")
                    return True

        except Exception as e:
            logger.error(f"发送消息时出错: {e}")
            return False


class FeishuForwarder(BaseForwarder):
    """飞书机器人转发器"""

    def __init__(self):
        self.webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
        if not self.webhook_url:
            logger.error("未配置 FEISHU_WEBHOOK_URL")

    async def send(self, content: Dict) -> bool:
        if not self.webhook_url:
            return False

        # 构建飞书消息格式
        message = f"**{content['chat_title']}**\n"
        message += f"消息: {content['message']}\n"
        message += f"发送者: {content['sender']}"

        data = {
            "msg_type": "text",
            "content": {
                "text": message
            }
        }

        return await self._post_json(self.webhook_url, data)


class CustomForwarder(BaseForwarder):
    """自定义 HTTP API 转发器"""

    def __init__(self):
        self.api_url = os.getenv('CUSTOM_API_URL')
        self.api_method = os.getenv('CUSTOM_API_METHOD', 'POST').upper()
        self.api_headers = self._parse_headers(os.getenv('CUSTOM_API_HEADERS', ''))

        if not self.api_url:
            logger.error("未配置 CUSTOM_API_URL")

    @staticmethod
    def _parse_headers(headers_str: str) -> Dict:
        """解析自定义请求头，格式: Key1:Value1,Key2:Value2"""
        headers = {}
        if headers_str:
            for pair in headers_str.split(','):
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    headers[key.strip()] = value.strip()
        return headers

    async def send(self, content: Dict) -> bool:
        if not self.api_url:
            return False

        # 直接发送原始内容，由用户自定义处理
        data = {
            "chat_title": content['chat_title'],
            "sender": content['sender'],
            "message": content['message'],
            "chat_id": content['chat_id'],
            "message_id": content['message_id']
        }

        return await self._post_json(self.api_url, data, self.api_headers)


class ForwarderFactory:
    """转发器工厂"""

    @staticmethod
    def create(forwarder_type: str) -> Optional[BaseForwarder]:
        """
        创建转发器实例
        :param forwarder_type: 转发器类型
        :return: 转发器实例
        """
        forwarder_map = {
            ForwarderType.WECOM.value: WeComForwarder,
            ForwarderType.WECOM_APP.value: WeComAppForwarder,
            ForwarderType.FEISHU.value: FeishuForwarder,
            ForwarderType.CUSTOM.value: CustomForwarder,
        }

        forwarder_class = forwarder_map.get(forwarder_type.lower())
        if forwarder_class:
            logger.info(f"创建转发器: {forwarder_type}")
            return forwarder_class()
        else:
            logger.error(f"不支持的转发器类型: {forwarder_type}")
            return None