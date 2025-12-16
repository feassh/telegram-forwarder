import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone

from telethon import TelegramClient, events, functions, types
from telethon.tl.types import Channel, Chat, User, MessageService
from dotenv import load_dotenv

from forwarders import ForwarderFactory

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

PERMANENT_MUTE = 2 ** 31 - 1


class TelegramForwarder:
    """Telegram 消息转发器"""

    def __init__(self):
        # Telegram 配置
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        self.phone = os.getenv('TELEGRAM_PHONE')

        # 转发配置
        forwarder_type = os.getenv('FORWARDER_TYPE', 'wecom').lower()
        self.forwarder = ForwarderFactory.create(forwarder_type)

        # 过滤配置
        self.filter_muted = os.getenv('FILTER_MUTED', 'true').lower() == 'true'
        self.whitelist_chats = self._parse_list(os.getenv('WHITELIST_CHATS', ''))
        self.blacklist_chats = self._parse_list(os.getenv('BLACKLIST_CHATS', ''))

        # 验证配置
        self._validate_config()

        # 创建客户端
        self.client = TelegramClient('sessions/forwarder_session', self.api_id, self.api_hash)

        logger.info(f"初始化完成，转发器类型: {forwarder_type}")

    def _validate_config(self):
        """验证必要配置"""
        if not all([self.api_id, self.api_hash, self.phone]):
            logger.error("缺少必要的 Telegram 配置")
            sys.exit(1)

        if not self.forwarder:
            logger.error("转发器初始化失败")
            sys.exit(1)

    @staticmethod
    def _parse_list(value: str) -> list:
        """解析逗号分隔的列表"""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

    async def is_chat_muted(self, event) -> bool:
        """检查当前消息所属对话是否处于免打扰状态"""
        try:
            peer = event.message.peer_id  # Or event.chat for the entity
            input_peer = await self.client.get_input_entity(peer)

            settings = await self.client(functions.account.GetNotifySettingsRequest(
                peer=types.InputNotifyPeer(input_peer)
            ))

            mute_until = settings.mute_until

            # 不免打扰
            if not mute_until:
                return False

            # 兼容 datetime / int 两种情况
            now = datetime.now(timezone.utc)

            # 永久静音（int 版本）
            if isinstance(mute_until, int):
                # mute_until = 0 => 不免打扰
                if mute_until == 0:
                    return False
                if mute_until == PERMANENT_MUTE:
                    return True
                return mute_until > int(time.time())

            # datetime 版本
            if isinstance(mute_until, datetime):
                return mute_until > now

            # 兜底使用免打扰策略
            return True
        except Exception as e:
            logger.warning(f"检查静音状态失败: {e}")
            # 保守策略：异常时视为静音，避免误触发逻辑
            return True

    async def should_forward(self, event) -> bool:
        """判断消息是否应该转发"""
        # 过滤服务消息
        if isinstance(event.message, MessageService):
            return False

        chat_id = event.chat_id

        # 白名单检查
        if self.whitelist_chats and str(chat_id) not in self.whitelist_chats:
            return False

        # 黑名单检查
        if self.blacklist_chats and str(chat_id) in self.blacklist_chats:
            return False

        # 静音检查
        if self.filter_muted and await self.is_chat_muted(event):
            logger.debug(f"对话 {chat_id} 已免打扰，跳过消息")
            return False

        return True

    async def get_chat_title(self, event) -> str:
        """获取对话标题"""
        try:
            chat = await event.get_chat()
            if isinstance(chat, Channel):
                return chat.title
            elif isinstance(chat, Chat):
                return chat.title
            elif isinstance(chat, User):
                if chat.last_name:
                    return f"{chat.first_name} {chat.last_name}"
                return chat.first_name or "Unknown"
            return "Unknown Chat"
        except Exception as e:
            logger.warning(f"获取对话标题失败: {e}")
            return "Unknown"

    async def get_sender_name(self, event) -> str:
        """获取发送者名称"""
        try:
            sender = await event.get_sender()
            if isinstance(sender, User):
                if sender.last_name:
                    return f"{sender.first_name} {sender.last_name}"
                return sender.first_name or "Unknown User"
            return "Unknown Sender"
        except Exception as e:
            logger.warning(f"获取发送者名称失败: {e}")
            return "Unknown"

    async def handle_new_message(self, event):
        """处理新消息"""
        try:
            # 判断是否应该转发
            if not await self.should_forward(event):
                return

            # 获取消息信息
            chat_title = await self.get_chat_title(event)
            sender_name = await self.get_sender_name(event)
            message_text = event.message.message or "[无文字内容]"

            # 构建转发消息
            forward_content = {
                'chat_title': chat_title,
                'sender': sender_name,
                'message': message_text,
                'chat_id': event.chat_id,
                'message_id': event.message.id
            }

            # 转发消息
            success = await self.forwarder.send(forward_content)

            if success:
                logger.info(f"消息已转发 - [{chat_title}] {sender_name}: {message_text[:10]}")
            else:
                logger.error(f"消息转发失败 - [{chat_title}] {sender_name}")

        except Exception as e:
            logger.error(f"处理消息时出错: {e}", exc_info=True)

    async def start(self):
        """启动转发器"""
        logger.info("正在启动 Telegram 转发器...")

        # 连接并登录
        await self.client.start(phone=self.phone)
        logger.info("已登录 Telegram")

        # 注册消息处理器
        @self.client.on(events.NewMessage())
        async def handler(event):
            await self.handle_new_message(event)

        logger.info("转发器已启动，等待新消息...")
        logger.info(f"免打扰过滤: {'启用' if self.filter_muted else '禁用'}")
        if self.whitelist_chats:
            logger.info(f"白名单: {self.whitelist_chats}")
        if self.blacklist_chats:
            logger.info(f"黑名单: {self.blacklist_chats}")

        # 保持运行
        await self.client.run_until_disconnected()


async def main():
    """主函数"""
    forwarder = TelegramForwarder()
    try:
        await forwarder.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
