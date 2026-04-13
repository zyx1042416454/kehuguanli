from typing import Optional
from datetime import datetime, timedelta
from langchain.tools import tool
from postgrest.exceptions import APIError

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略类型检查错误


@tool
def create_follow_up_alert(contact_name: str, reminder_time: str, description: Optional[str] = None) -> str:
    """创建跟进提醒。

    Args:
        contact_name: 联系人姓名
        reminder_time: 提醒时间（格式：YYYY-MM-DD HH:MM 或相对时间如"3天后"）
        description: 提醒描述

    Returns:
        创建结果
    """
    try:
        client = get_supabase_client()

        # 查找联系人
        contact_response = client.table('contacts').select('id, name').eq('name', contact_name).execute()

        if not contact_response.data:
            return f"未找到联系人：{contact_name}"

        contact_id = contact_response.data[0]['id']

        # 解析提醒时间
        if "后" in reminder_time or "周" in reminder_time or "月" in reminder_time:
            # 相对时间
            if "天" in reminder_time:
                days = int(reminder_time.replace("天", "").replace("后", "").strip())
                reminder_datetime = datetime.now() + timedelta(days=days)
            elif "周" in reminder_time:
                weeks = int(reminder_time.replace("周", "").replace("后", "").strip())
                reminder_datetime = datetime.now() + timedelta(weeks=weeks)
            elif "月" in reminder_time:
                months = int(reminder_time.replace("个月", "").replace("月", "").replace("后", "").strip())
                reminder_datetime = datetime.now() + timedelta(days=months*30)
            else:
                reminder_datetime = datetime.now() + timedelta(days=1)
        else:
            # 绝对时间
            try:
                reminder_datetime = datetime.strptime(reminder_time, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    reminder_datetime = datetime.strptime(reminder_time, "%Y-%m-%d")
                except ValueError:
                    return f"时间格式错误，请使用 YYYY-MM-DD HH:MM 或相对时间（如'3天后'）"

        alert_data = {
            'contact_id': contact_id,
            'alert_type': 'follow_up',
            'trigger_condition': description or '定期跟进',
            'reminder_time': reminder_datetime.strftime("%Y-%m-%d %H:%M"),
            'status': 'active'
        }

        response = client.table('alerts').insert(alert_data).execute()
        return f"成功创建跟进提醒：{contact_name} - {reminder_datetime.strftime('%Y-%m-%d %H:%M')}"

    except APIError as e:
        return f"创建提醒失败：{e.message}"
    except Exception as e:
        return f"创建提醒失败：{str(e)}"


@tool
def get_pending_reminders(days_ahead: int = 7) -> str:
    """获取待处理的提醒。

    Args:
        days_ahead: 查询未来几天的提醒（默认7天）

    Returns:
        待处理提醒列表
    """
    try:
        client = get_supabase_client()

        # 计算时间范围
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # 查询活跃提醒
        response = client.table('alerts').select(
            'id, alert_type, reminder_time, status, contacts(name, company, contact_level, phone)'
        ).eq('status', 'active').lte('reminder_time', end_date).order('reminder_time').execute()

        if not response.data:
            return f"未来 {days_ahead} 天内没有待处理的提醒"

        result = f"📋 待处理提醒（共 {len(response.data)} 条）：\n\n"

        for alert in response.data:
            if not isinstance(alert, dict):
                continue
            contact = alert.get('contacts') if isinstance(alert.get('contacts'), dict) else {}
            alert_type_text = {
                'follow_up': '跟进',
                'birthday': '生日',
                'anniversary': '纪念日'
            }.get(alert.get('alert_type', ''), alert.get('alert_type', ''))

            contact_name = contact.get('name', '未知') if isinstance(contact, dict) else '未知'
            contact_company = contact.get('company', '') if isinstance(contact, dict) else ''
            contact_level = contact.get('contact_level', 'medium') if isinstance(contact, dict) else 'medium'
            contact_phone = contact.get('phone', '') if isinstance(contact, dict) else ''

            result += f"• {contact_name}（{contact_company}）\n"
            result += f"  类型：{alert_type_text}\n"
            result += f"  时间：{alert.get('reminder_time', '')}\n"
            result += f"  等级：{contact_level}\n"
            if contact_phone:
                result += f"  电话：{contact_phone}\n"
            result += "\n"

        return result

    except APIError as e:
        return f"查询提醒失败：{e.message}"
    except Exception as e:
        return f"查询提醒失败：{str(e)}"


@tool
def complete_alert(alert_id: int) -> str:
    """标记提醒为已完成。

    Args:
        alert_id: 提醒ID

    Returns:
        操作结果
    """
    try:
        client = get_supabase_client()

        response = client.table('alerts').update(
            {'status': 'completed', 'last_reminded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        ).eq('id', alert_id).execute()

        if response.data:
            return f"成功标记提醒 #{alert_id} 为已完成"
        else:
            return f"未找到提醒 #{alert_id}"

    except APIError as e:
        return f"更新提醒失败：{e.message}"
    except Exception as e:
        return f"更新提醒失败：{str(e)}"


@tool
def create_birthday_reminder(contact_name: str, birthday: str) -> str:
    """创建生日提醒。

    Args:
        contact_name: 联系人姓名
        birthday: 生日（格式：MM-DD 或 YYYY-MM-DD）

    Returns:
        创建结果
    """
    try:
        client = get_supabase_client()

        # 查找联系人
        contact_response = client.table('contacts').select('id, name').eq('name', contact_name).execute()

        if not contact_response.data:
            return f"未找到联系人：{contact_name}"

        contact_id = contact_response.data[0]['id']

        # 解析生日
        if len(birthday) == 5 and birthday.count('-') == 1:
            # MM-DD 格式
            birthday_date = f"2024-{birthday}"  # 使用2024年作为基准
        else:
            birthday_date = birthday

        # 创建客户事件
        event_data = {
            'contact_id': contact_id,
            'event_type': 'birthday',
            'event_date': birthday_date,
            'description': '生日提醒'
        }

        # 同时创建提醒
        alert_data = {
            'contact_id': contact_id,
            'alert_type': 'birthday',
            'trigger_condition': '每年生日',
            'reminder_time': birthday_date.replace('2024', str(datetime.now().year)),  # 今年生日
            'status': 'active'
        }

        client.table('customer_events').insert(event_data).execute()
        client.table('alerts').insert(alert_data).execute()

        return f"成功创建生日提醒：{contact_name} - {birthday}"

    except APIError as e:
        return f"创建生日提醒失败：{e.message}"
    except Exception as e:
        return f"创建生日提醒失败：{str(e)}"
