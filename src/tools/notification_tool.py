import json
import requests
from typing import Optional
from langchain.tools import tool
from postgrest.exceptions import APIError

from storage.database.supabase_client import get_supabase_client


def _get_webhook_url() -> str:
    """从 Supabase 获取 webhook_url 配置"""
    try:
        client = get_supabase_client()

        # 查询用户设置
        response = client.table('user_settings').select('webhook_url').execute()

        if response.data and isinstance(response.data, list) and len(response.data) > 0:
            first_setting = response.data[0]
            if isinstance(first_setting, dict) and first_setting.get('webhook_url'):
                return first_setting.get('webhook_url')

        return None

    except Exception as e:
        print(f"获取 webhook_url 失败：{str(e)}")
        return None


def _set_webhook_url(webhook_url: str) -> bool:
    """保存 webhook_url 到 Supabase"""
    try:
        client = get_supabase_client()

        # 检查是否已有配置
        existing_response = client.table('user_settings').select('id').execute()

        if existing_response.data:
            # 更新
            client.table('user_settings').update({'webhook_url': webhook_url}).execute()
        else:
            # 插入
            client.table('user_settings').insert({'webhook_url': webhook_url}).execute()

        return True

    except Exception as e:
        print(f"保存 webhook_url 失败：{str(e)}")
        return False


@tool
def configure_feishu_webhook(webhook_url: str) -> str:
    """配置飞书 Webhook 地址。

    Args:
        webhook_url: 飞书机器人的 Webhook 地址

    Returns:
        配置结果
    """
    try:
        # 保存到数据库
        if _set_webhook_url(webhook_url):
            # 测试连接
            test_payload = {
                "msg_type": "text",
                "content": {
                    "text": "✅ 飞书 Webhook 配置成功！人脉管理助手已就绪。"
                }
            }

            response = requests.post(webhook_url, json=test_payload, timeout=10)

            if response.status_code == 200:
                return f"✅ 飞书 Webhook 配置成功！\n\n测试消息已发送。"
            else:
                return f"⚠️ Webhook 已保存，但测试发送失败：{response.text}\n\n请检查 webhook_url 是否正确。"

        return "❌ 保存 Webhook 配置失败"

    except Exception as e:
        return f"配置失败：{str(e)}"


@tool
def send_feishu_message(content: str, msg_type: str = "text") -> str:
    """通过飞书发送消息。

    Args:
        content: 消息内容
        msg_type: 消息类型（text/post/interactive）

    Returns:
        发送结果
    """
    try:
        webhook_url = _get_webhook_url()

        if not webhook_url:
            return "❌ 未配置飞书 Webhook，请先使用 configure_feishu_webhook 工具配置"

        if msg_type == "text":
            payload = {
                "msg_type": "text",
                "content": {
                    "text": content
                }
            }
        elif msg_type == "post":
            payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": "人脉管理提醒",
                            "content": [
                                [
                                    {"tag": "text", "text": content}
                                ]
                            ]
                        }
                    }
                }
            }
        else:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": content
                }
            }

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('StatusCode') == 0:
                return "✅ 消息发送成功"
            else:
                return f"⚠️ 消息发送失败：{result}"
        else:
            return f"❌ 发送请求失败：{response.status_code} - {response.text}"

    except Exception as e:
        return f"发送消息失败：{str(e)}"


@tool
def send_reminder_card(contact_name: str, reminder_type: str, description: str) -> str:
    """发送提醒卡片到飞书。

    Args:
        contact_name: 联系人姓名
        reminder_type: 提醒类型（跟进/生日/纪念日）
        description: 提醒描述

    Returns:
        发送结果
    """
    try:
        webhook_url = _get_webhook_url()

        if not webhook_url:
            return "❌ 未配置飞书 Webhook，请先使用 configure_feishu_webhook 工具配置"

        # 构建卡片消息
        emoji_map = {
            "跟进": "📞",
            "生日": "🎂",
            "纪念日": "🎉",
            "follow_up": "📞",
            "birthday": "🎂",
            "anniversary": "🎉"
        }

        emoji = emoji_map.get(reminder_type, "📌")

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"{emoji} 客户提醒"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**联系人：** {contact_name}\n**类型：** {reminder_type}\n**描述：** {description}"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "✅ 已处理"
                                },
                                "type": "primary",
                                "url": f"https://example.com/complete?contact={contact_name}"
                            },
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "⏰ 稍后提醒"
                                },
                                "type": "default",
                                "url": f"https://example.com/snooze?contact={contact_name}"
                            }
                        ]
                    }
                ]
            }
        }

        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if result.get('StatusCode') == 0:
                return f"✅ 提醒卡片发送成功：{contact_name}"
            else:
                return f"⚠️ 提醒卡片发送失败：{result}"
        else:
            return f"❌ 发送请求失败：{response.status_code} - {response.text}"

    except Exception as e:
        return f"发送提醒卡片失败：{str(e)}"
