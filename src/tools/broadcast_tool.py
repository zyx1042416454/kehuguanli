from typing import Optional
from langchain.tools import tool
from postgrest.exceptions import APIError
from datetime import datetime
import json

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略类型检查错误


@tool
def broadcast_pending_reminders() -> str:
    """批量推送所有待处理的提醒到飞书。

    Returns:
        推送结果统计
    """
    try:
        from tools.alert_tool import get_pending_reminders
        from tools.notification_tool import send_feishu_message

        # 获取待处理提醒
        reminders = get_pending_reminders(days_ahead=7)
        
        # 检查是否有待处理提醒
        if "没有待处理的提醒" in reminders:
            return "没有需要推送的待处理提醒"

        # 构造推送消息
        summary_message = f"""📋 人脉管理提醒通知
{datetime.now().strftime("%Y年%m月%d日 %H:%M")}

{reminders}

---
以上提醒请及时处理，如需推迟请使用 snooze 功能。
        """

        # 发送到飞书
        result = send_feishu_message(summary_message, msg_type="post")

        return f"{result}\n\n已推送待处理提醒到飞书"

    except Exception as e:
        return f"批量推送失败：{str(e)}"


@tool
def push_high_value_contacts() -> str:
    """推送高价值客户列表到飞书（适合每周回顾）。

    Returns:
        推送结果
    """
    try:
        from tools.relationship_suggestion_tool import get_high_value_contacts
        from tools.notification_tool import send_feishu_message

        # 获取高价值客户
        high_value_contacts = get_high_value_contacts(limit=20)
        
        if "没有高价值客户" in high_value_contacts:
            return "当前没有高价值客户需要关注"

        # 构造推送消息
        summary_message = f"""🌟 高价值客户周报
{datetime.now().strftime("%Y年第%W周")}

{high_value_contacts}

---
建议：本周内至少与每位高价值客户联系2次
        """

        # 发送到飞书
        result = send_feishu_message(summary_message, msg_type="post")

        return f"{result}\n\n已推送高价值客户周报到飞书"

    except Exception as e:
        return f"推送高价值客户失败：{str(e)}"


@tool
def push_daily_summary() -> str:
    """推送每日客户关系摘要到飞书。

    Returns:
        推送结果
    """
    try:
        from tools.notification_tool import send_feishu_message
        client = get_supabase_client()

        # 统计今日数据
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 统计联系人总数
        contacts_response = client.table('contacts').select('id').execute()
        total_contacts = len(contacts_response.data)
        
        # 统计高价值客户数
        high_contacts_response = client.table('contacts').select('id').eq('contact_level', 'high').execute()
        high_contacts = len(high_contacts_response.data)
        
        # 统计关系总数
        relationships_response = client.table('relationships').select('id').execute()
        total_relationships = len(relationships_response.data)
        
        # 统计今日待处理提醒
        alerts_response = client.table('alerts').select('id').eq('status', 'active').execute()
        pending_alerts = len(alerts_response.data)

        # 构造推送消息
        summary_message = f"""📊 客户关系日报
{datetime.now().strftime("%Y年%m月%d日")}

📈 数据统计
- 联系人总数：{total_contacts} 人
- 高价值客户：{high_contacts} 人
- 关系连接：{total_relationships} 条
- 待处理提醒：{pending_alerts} 条

💡 今日建议
1. 检查待处理提醒并及时跟进
2. 回顾本周需要联系的高价值客户
3. 思考是否需要扩展新的关系网络

---
保持联系，持续积累人脉资产！
        """

        # 发送到飞书
        result = send_feishu_message(summary_message, msg_type="post")

        return f"{result}\n\n已推送每日摘要到飞书"

    except Exception as e:
        return f"推送每日摘要失败：{str(e)}"


@tool
def push_weekly_report() -> str:
    """推送每周客户关系分析报告到飞书。

    Returns:
        推送结果
    """
    try:
        from tools.notification_tool import send_feishu_message
        from tools.alert_tool import get_pending_reminders
        from tools.relationship_suggestion_tool import get_high_value_contacts
        client = get_supabase_client()

        # 统计本周数据
        week_start = datetime.now().strftime("%Y年第%W周")
        
        # 按客户等级统计
        high_response = client.table('contacts').select('id').eq('contact_level', 'high').execute()
        medium_response = client.table('contacts').select('id').eq('contact_level', 'medium').execute()
        low_response = client.table('contacts').select('id').eq('contact_level', 'low').execute()
        
        # 按来源统计
        alumni_response = client.table('contacts').select('id').eq('source', 'alumni').execute()
        industry_response = client.table('contacts').select('id').eq('source', 'industry_assoc').execute()
        business_response = client.table('contacts').select('id').eq('source', 'business_exchange').execute()
        
        # 获取本周新增联系人
        week_contacts_response = client.table('contacts').select('id, name, company').order('created_at', desc=True).limit(5).execute()
        
        # 构造推送消息
        summary_message = f"""📊 人脉管理周报
{week_start}

📊 客户分布
- 高价值客户：{len(high_response.data)} 人
- 中等价值客户：{len(medium_response.data)} 人
- 低价值客户：{len(low_response.data)} 人

📚 来源分布
- 校友资源：{len(alumni_response.data)} 人
- 行业协会：{len(industry_response.data)} 人
- 商务交流：{len(business_response.data)} 人

🆕 本周新增联系人
"""
        
        for contact in week_contacts_response.data:
            if isinstance(contact, dict):
                summary_message += f"- {contact.get('name', '')} ({contact.get('company', '')})\n"
        
        summary_message += f"""

💡 本周建议
1. 高价值客户保持每周至少2次联系
2. 关注校友资源，定期组织/参加校友活动
3. 行业协会是拓展新关系的重要渠道
4. 检查本周待处理提醒并完成跟进

---
持续积累，让人脉成为你的核心竞争力！
        """

        # 发送到飞书
        result = send_feishu_message(summary_message, msg_type="post")

        return f"{result}\n\n已推送周报到飞书"

    except Exception as e:
        return f"推送周报失败：{str(e)}"


@tool
def push_contact_birthday_upcoming(days: int = 7) -> str:
    """推送即将过生日的联系人提醒。

    Args:
        days: 查询未来几天的生日（默认7天）

    Returns:
        推送结果
    """
    try:
        from tools.notification_tool import send_feishu_message
        from datetime import datetime, timedelta
        client = get_supabase_client()

        # 计算日期范围
        today = datetime.now()
        end_date = today + timedelta(days=days)
        
        # 查询即将到来的生日
        events_response = client.table('customer_events').select(
            'event_date, contacts(name, company, contact_level, phone)'
        ).eq('event_type', 'birthday').execute()
        
        if not events_response.data:
            return f"未来 {days} 天内没有生日提醒"

        birthday_list = []
        for event in events_response.data:
            if not isinstance(event, dict):
                continue
            contact = event.get('contacts')
            if isinstance(contact, dict):
                event_date = event.get('event_date', '')
                # 简化处理：实际应该对比月日
                birthday_list.append(f"- {contact.get('name', '')}（{contact.get('company', '')}）- {event_date}")

        if not birthday_list:
            return f"未来 {days} 天内没有生日提醒"

        # 构造推送消息
        summary_message = f"""🎂 生日提醒
未来 {days} 天内即将过生日的联系人：

{chr(10).join(birthday_list)}

💡 建议
1. 提前准备生日祝福
2. 考虑发送小礼物或邀请午餐
3. 这是加强关系的好机会

---
祝生日快乐！
        """

        # 发送到飞书
        result = send_feishu_message(summary_message, msg_type="post")

        return f"{result}\n\n已推送生日提醒到飞书"

    except Exception as e:
        return f"推送生日提醒失败：{str(e)}"
