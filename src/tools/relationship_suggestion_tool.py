from typing import Optional
from langchain.tools import tool
from postgrest.exceptions import APIError
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略类型检查错误


@tool
def generate_referral_script(contact_name: str, target_name: str, context: str) -> str:
    """生成引荐文案。

    Args:
        contact_name: 中间人姓名
        target_name: 目标联系人姓名
        context: 上下文或目的

    Returns:
        引荐文案
    """
    try:
        client = get_supabase_client()

        # 查找联系人信息
        contact_response = client.table('contacts').select('id, name, company, position').eq('name', contact_name).execute()
        target_response = client.table('contacts').select('id, name, company, position').eq('name', target_name).execute()

        if not contact_response.data or not isinstance(contact_response.data, list) or len(contact_response.data) == 0:
            return f"未找到联系人：{contact_name}"
        if not target_response.data or not isinstance(target_response.data, list) or len(target_response.data) == 0:
            return f"未找到目标联系人：{target_name}"

        contact_info = contact_response.data[0] if isinstance(contact_response.data[0], dict) else {}
        target_info = target_response.data[0] if isinstance(target_response.data[0], dict) else {}

        # 使用 LLM 生成引荐文案
        ctx = new_context(method="generate_referral_script")
        llm_client = LLMClient(ctx=ctx)

        prompt = f"""
请根据以下信息生成一段引荐文案：

中间人信息：
- 姓名：{contact_info.get('name', '')}
- 公司：{contact_info.get('company', '未知')}
- 职位：{contact_info.get('position', '未知')}

目标联系人信息：
- 姓名：{target_info.get('name', '')}
- 公司：{target_info.get('company', '未知')}
- 职位：{target_info.get('position', '未知')}

引荐目的/上下文：
{context}

请生成以下两部分内容：
1. 给中间人的请求话术
2. 给目标联系人的自我介绍话术

要求：
- 语气专业且友好
- 突出共同利益点
- 简洁明了，不超过200字
"""

        messages = [
            SystemMessage(content="你是专业的商务引荐专家，擅长撰写得体的引荐文案。"),
            HumanMessage(content=prompt)
        ]

        response = llm_client.invoke(messages=messages, temperature=0.7, model="doubao-seed-1-6-251015")

        # 提取文本内容
        if isinstance(response.content, str):
            return response.content
        elif isinstance(response.content, list):
            text_parts = []
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        else:
            return str(response.content)

    except Exception as e:
        return f"生成引荐文案失败：{str(e)}"


@tool
def analyze_relationship_gaps(contact_name: str) -> str:
    """分析联系人关系网络的薄弱环节，给出增强建议。

    Args:
        contact_name: 联系人姓名

    Returns:
        关系增强建议
    """
    try:
        client = get_supabase_client()

        # 查找联系人
        contact_response = client.table('contacts').select('id, name, company, position, city, tags').eq('name', contact_name).execute()

        if not contact_response.data:
            return f"未找到联系人：{contact_name}"

        contact_id = contact_response.data[0]['id']
        contact_info = contact_response.data[0]

        # 查询该联系人的关系
        rels_response = client.table('relationships').select(
            'relationship_type, strength, target_contacts(name, company, position)'
        ).eq('source_contact_id', contact_id).execute()

        # 分析关系类型分布
        rel_types = {}
        rel_strengths = {'strong': 0, 'medium': 0, 'weak': 0}

        for rel in rels_response.data:
            if not isinstance(rel, dict):
                continue
            rel_type = rel.get('relationship_type', '')
            rel_types[rel_type] = rel_types.get(rel_type, 0) + 1
            rel_strength_val = rel.get('strength', '')
            if rel_strength_val in rel_strengths:
                rel_strengths[rel_strength_val] += 1

        # 查询相同公司的其他联系人
        company_contacts_response = client.table('contacts').select('id, name, position').eq('company', contact_info.get('company', '')).neq('id', contact_id).limit(5).execute()

        # 查询同城的联系人
        city_contacts_response = client.table('contacts').select('id, name, company').eq('city', contact_info.get('city', '')).neq('id', contact_id).limit(5).execute()

        # 使用 LLM 生成建议
        ctx = new_context(method="analyze_relationship_gaps")
        llm_client = LLMClient(ctx=ctx)

        prompt = f"""
请分析以下联系人关系网络，给出增强建议：

联系人信息：
- 姓名：{contact_info.get('name', '')}
- 公司：{contact_info.get('company', '未知')}
- 职位：{contact_info.get('position', '未知')}
- 城市：{contact_info.get('city', '未知')}

当前关系统计：
- 关系总数：{len(rels_response.data)}
- 关系类型分布：{rel_types}
- 关系强度分布：{rel_strengths}

潜在连接：
- 同公司同事：{len(company_contacts_response.data)} 人
- 同城联系人：{len(city_contacts_response.data)} 人

请根据以上信息，分析关系网络的薄弱环节，并提供具体的增强建议，包括：
1. 需要加强的关系类型
2. 可以尝试的活动或渠道
3. 具体的行动建议
"""

        messages = [
            SystemMessage(content="你是专业的人脉关系顾问，擅长分析关系网络并提供实用的增强建议。"),
            HumanMessage(content=prompt)
        ]

        response = llm_client.invoke(messages=messages, temperature=0.7, model="doubao-seed-1-6-251015")

        # 提取文本内容
        if isinstance(response.content, str):
            return response.content
        elif isinstance(response.content, list):
            text_parts = []
            for item in response.content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            return "\n".join(text_parts)
        else:
            return str(response.content)

    except Exception as e:
        return f"分析关系网络失败：{str(e)}"


@tool
def get_high_value_contacts(limit: int = 10) -> str:
    """获取高价值客户列表（按客户等级排序）。

    Args:
        limit: 返回数量

    Returns:
        高价值客户列表
    """
    try:
        client = get_supabase_client()

        response = client.table('contacts').select(
            'id, name, company, position, contact_level, contact_frequency, phone, email'
        ).in_('contact_level', ['high']).order('contact_level').limit(limit).execute()

        if not response.data:
            return "没有高价值客户（high 等级）"

        result = f"🌟 高价值客户列表（共 {len(response.data)} 人）：\n\n"

        for contact in response.data:
            if not isinstance(contact, dict):
                continue
            frequency_text = {
                'high': '一周2次',
                'medium': '一周1次',
                'low': '一月1次'
            }.get(contact.get('contact_frequency', ''), contact.get('contact_frequency', ''))

            result += f"• {contact.get('name', '')}\n"
            result += f"  公司：{contact.get('company', '未知')} - {contact.get('position', '未知')}\n"
            result += f"  联系频率：{frequency_text}\n"
            if contact.get('phone'):
                result += f"  电话：{contact.get('phone', '')}\n"
            if contact.get('email'):
                result += f"  邮箱：{contact.get('email', '')}\n"
            result += "\n"

        # 提供跟进建议
        result += "💡 跟进建议：\n"
        result += "- 高价值客户建议每周至少联系2次\n"
        result += "- 优先处理他们的需求和问题\n"
        result += "- 定期分享有价值的行业资讯\n"

        return result

    except APIError as e:
        return f"查询高价值客户失败：{e.message}"
    except Exception as e:
        return f"查询高价值客户失败：{str(e)}"
