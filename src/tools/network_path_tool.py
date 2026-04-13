from typing import Optional, List
from langchain.tools import tool
from postgrest.exceptions import APIError
from collections import deque
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import SearchClient, LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略类型检查错误


def _get_text_content(content):
    """安全获取文本内容"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        if content and isinstance(content[0], str):
            return " ".join(content)
        else:
            return " ".join(item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text")
    return str(content)


@tool
def find_shortest_path(target_name: str, target_company: Optional[str] = None) -> str:
    """通过互联网搜索目标公司的合作单位，然后在人脉数据库中查找潜在中间人。

    Args:
        target_name: 目标联系人姓名（如"刘蕾"）
        target_company: 目标公司（如"巨一科技"）

    Returns:
        推荐的引荐中间人列表和引荐话术

    业务逻辑：
        1. 通过互联网搜索目标公司的合作单位、客户、供应商等业务关联公司
        2. 在人脉数据库中查找这些合作单位的联系人
        3. 将找到的联系人作为潜在中间人推荐
        4. 生成引荐话术
    """
    try:
        client = get_supabase_client()

        # 如果没有提供公司名称，无法查询
        if not target_company:
            return f"请提供目标公司名称，以便为您查找相关的人脉资源。\n\n使用示例：\n- 我想认识巨一科技的刘蕾\n- 请帮我找一下字节跳动的张三"

        result = f"🎯 目标：认识 {target_name}（{target_company}）

"

        # 第一步：互联网搜索目标公司的合作单位
        result += "🔍 第一步：搜索 {target_company} 的业务关联信息...\n\n"

        search_response = None
        partner_companies = []

        try:
            ctx = new_context(method="find_shortest_path_search")
            search_client = SearchClient(ctx=ctx)

            # 搜索目标公司的合作单位、客户、供应商等
            search_query = f"{target_company} 合作单位 客户 供应商 战略合作伙伴"
            search_response = search_client.web_search_with_summary(query=search_query, count=10)

            if not search_response.web_items:
                result += "⚠️ 未能从互联网找到相关信息，直接查询数据库...\n\n"
                partner_companies = []
            else:
                # 提取搜索结果中的公司名称
                search_text = ""
                for item in search_response.web_items[:5]:
                    if item.title:
                        search_text += item.title + " "
                    if item.snippet:
                        search_text += item.snippet + " "
                    if item.summary:
                        search_text += item.summary + " "

                # 使用 LLM 从搜索结果中提取公司名称
                ctx_llm = new_context(method="extract_companies")
                llm_client = LLMClient(ctx=ctx_llm)

                extract_prompt = f"""
从以下文本中提取所有可能的公司名称（去除目标公司"{target_company}"本身）。

文本内容：
{search_text[:2000]}

要求：
1. 只提取公司名称，不要其他信息
2. 以列表形式返回，每行一个公司名称
3. 优先提取明确的合作单位、客户、供应商、战略合作伙伴
4. 最多返回 10 个公司名称
"""

                extract_messages = [
                    SystemMessage(content="你是专业的信息提取专家，擅长从文本中提取公司名称。"),
                    HumanMessage(content=extract_prompt)
                ]

                extract_response = llm_client.invoke(messages=extract_messages, temperature=0.3, model="doubao-seed-1-6-251015")
                extract_result = _get_text_content(extract_response.content)

                # 解析提取的公司名称
                partner_companies = []
                for line in extract_result.split('\n'):
                    line = line.strip()
                    if line and len(line) > 2:
                        # 清理行号、标点等
                        line = line.lstrip('0123456789.-•、 ')
                        if line and line != target_company:
                            partner_companies.append(line)

                if partner_companies:
                    result += f"✅ 从互联网找到 {len(partner_companies)} 个潜在合作单位：\n"
                    for i, company in enumerate(partner_companies[:5], 1):
                        result += f"  {i}. {company}\n"
                    result += "\n"
                else:
                    result += "⚠️ 从搜索结果中未能提取到明确的合作单位\n\n"

        except Exception as e:
            result += f"⚠️ 互联网搜索失败：{str(e)}\n\n"
            partner_companies = []

        # 第二步：在数据库中查找这些合作单位的联系人
        result += "📊 第二步：在人脉数据库中查找合作单位的联系人...\n\n"

        found_contacts = {}

        # 如果找到合作单位，逐一在数据库中查找
        if partner_companies:
            for company in partner_companies[:10]:  # 最多查找10个合作单位
                # 尝试精确匹配
                contacts_response = client.table('contacts').select(
                    'id, name, company, position, contact_level, phone, email'
                ).eq('company', company).execute()

                if contacts_response.data:
                    for contact in contacts_response.data:
                        if isinstance(contact, dict) and contact['id'] not in found_contacts:
                            found_contacts[contact['id']] = {
                                'contact': contact,
                                'source_company': company,
                                'source': 'internet_search'
                            }

        # 如果通过合作单位没有找到，尝试模糊匹配目标公司名称
        if not found_contacts:
            result += "💡 通过合作单位未找到联系人，尝试模糊匹配...\n\n"

            # 查找公司名称包含目标公司关键词的联系人
            company_keyword = target_company.replace("有限公司", "").replace("科技", "").replace("集团", "").replace("公司", "").replace("股份", "")
            if len(company_keyword) >= 2:
                fuzzy_response = client.table('contacts').select(
                    'id, name, company, position, contact_level, phone, email'
                ).ilike('company', f'%{company_keyword}%').execute()

                if fuzzy_response.data:
                    for contact in fuzzy_response.data:
                        if isinstance(contact, dict) and contact['id'] not in found_contacts:
                            found_contacts[contact['id']] = {
                                'contact': contact,
                                'source_company': contact.get('company', ''),
                                'source': 'fuzzy_match'
                            }

        # 第三步：展示结果
        if not found_contacts:
            result += f"❌ 未能找到可以引荐的中间人\n\n"

            result += f"""💡 建议：
1. 在领英（LinkedIn）上搜索 {target_company} 的员工
2. 参加相关行业会议和展会
3. 通过共同的朋友或同事引荐
4. 关注 {target_company} 官方社交媒体动态
5. 直接访问 {target_company} 官网，寻找联系方式

🌐 互联网搜索结果摘要：
"""
            if search_response and search_response.web_items:
                for item in search_response.web_items[:3]:
                    result += f"- {item.title}\n  {item.url}\n\n"
        else:
            result += f"✅ 找到 {len(found_contacts)} 个潜在引荐中间人：\n\n"

            # 按联系人等级排序
            sorted_found = sorted(found_contacts.values(), key=lambda x: {
                'high': 3,
                'medium': 2,
                'low': 1
            }.get(x['contact'].get('contact_level', 'medium'), 2), reverse=True)

            for i, item in enumerate(sorted_found, 1):
                contact = item['contact']
                source_company = item['source_company']
                source = item['source']

                result += f"{i}. {contact.get('name', '')}\n"
                result += f"   公司：{contact.get('company', '')}\n"
                result += f"   职位：{contact.get('position', '')}\n"
                result += f"   等级：{contact.get('contact_level', 'medium')}\n"
                if source == 'internet_search':
                    result += f"   🔗 关联：认识合作单位「{source_company}」\n"
                elif source == 'fuzzy_match':
                    result += f"   🔗 关联：公司名称相似\n"
                if contact.get('phone'):
                    result += f"   电话：{contact.get('phone', '')}\n"
                if contact.get('email'):
                    result += f"   邮箱：{contact.get('email', '')}\n"
                result += "\n"

            # 第四步：生成引荐话术
            result += "💡 第四步：生成引荐话术...\n\n"

            if sorted_found:
                primary_contact = sorted_found[0]['contact']
                primary_source = sorted_found[0]['source_company']

                ctx_script = new_context(method="generate_referral_script")
                llm_client = LLMClient(ctx=ctx_script)

                script_prompt = f"""
请为我生成一条请求引荐的话术。

目标联系人：{target_name}
目标公司：{target_company}

潜在引荐中间人：
- 姓名：{primary_contact.get('name', '')}
- 公司：{primary_contact.get('company', '')}
- 职位：{primary_contact.get('position', '')}

背景说明：
{target_company} 与 {primary_source} 有业务关联，所以这个中间人可能认识或能引荐到 {target_name}。

请生成一段礼貌且专业的请求话术，内容包括：
1. 自我介绍（假设我是商务合作方）
2. 说明想认识 {target_name} 的原因和合作意向
3. 提到通过 {primary_contact.get('name', '')} 引荐是因为他/她在 {primary_source} 工作，与 {target_company} 有业务关联
4. 请求引荐
5. 表达感谢

要求：语气友好、专业、简洁（200字以内）
"""

                script_messages = [
                    SystemMessage(content="你是专业的商务沟通专家，擅长撰写得体的请求引荐话术。"),
                    HumanMessage(content=script_prompt)
                ]

                script_response = llm_client.invoke(messages=script_messages, temperature=0.7, model="doubao-seed-1-6-251015")
                referral_script = _get_text_content(script_response.content)

                result += f"📝 推荐引荐话术：\n\n{referral_script}\n\n"

            # 第五步：行动建议
            result += f"📌 下一步行动建议：\n"
            result += f"1. 优先联系关系最强的中间人（高等级联系人）\n"
            result += f"2. 在请求中说明具体的合作意向和价值\n"
            result += f"3. 提到中间人的公司与 {target_company} 有业务关联，增加引荐合理性\n"
            result += f"4. 准备好自我介绍和合作方案\n"
            result += f"5. 表达对对方时间的尊重和感谢\n"

        return result

    except APIError as e:
        return f"查询失败：{e.message}"
    except Exception as e:
        return f"查询失败：{str(e)}"


@tool
def search_contacts(keyword: str, filters: Optional[dict] = None) -> str:
    """搜索联系人。

    Args:
        keyword: 搜索关键词（姓名、公司、职位等）
        filters: 额外过滤条件（可选），如 {'contact_level': 'high', 'city': '北京'}

    Returns:
        联系人列表信息
    """
    try:
        client = get_supabase_client()

        # 构建基础查询
        query = client.table('contacts').select('id, name, company, position, contact_level, contact_frequency, city, source, phone, email')

        # 添加关键词搜索
        if keyword:
            query = query.or_(f'name.ilike.%{keyword}%,company.ilike.%{keyword}%,position.ilike.%{keyword}%')

        # 添加过滤条件
        if filters:
            if 'contact_level' in filters:
                query = query.eq('contact_level', filters['contact_level'])
            if 'contact_frequency' in filters:
                query = query.eq('contact_frequency', filters['contact_frequency'])
            if 'city' in filters:
                query = query.eq('city', filters['city'])
            if 'source' in filters:
                query = query.eq('source', filters['source'])

        query = query.limit(20)
        response = query.execute()

        if not response.data:
            return f"未找到匹配的联系人：{keyword}"

        result = f"找到 {len(response.data)} 个联系人：\n\n"

        for contact in response.data:
            result += f"• {contact['name']}"
            if contact.get('company'):
                result += f" - {contact['company']}"
            if contact.get('position'):
                result += f" - {contact['position']}"
            result += f"\n  等级：{contact['contact_level']}，频率：{contact['contact_frequency']}"
            if contact.get('city'):
                result += f"，城市：{contact['city']}"
            result += f"\n  来源：{contact['source']}\n\n"

        return result

    except APIError as e:
        return f"搜索联系人失败：{e.message}"
    except Exception as e:
        return f"搜索联系人失败：{str(e)}"


@tool
def get_contact_relationships(contact_name: str) -> str:
    """查看联系人的关系网络。

    Args:
        contact_name: 联系人姓名

    Returns:
        该联系人的所有关系信息
    """
    try:
        client = get_supabase_client()

        # 查找联系人ID
        contact_response = client.table('contacts').select('id, name, company').eq('name', contact_name).execute()

        if not contact_response.data:
            return f"未找到联系人：{contact_name}"

        contact_id = contact_response.data[0]['id']

        # 查询所有关系（源或目标）
        rels_response = client.table('relationships').select(
            'source_contact_id, target_contact_id, relationship_type, strength, description, source_contacts(name, company), target_contacts(name, company)'
        ).or_(f'source_contact_id.eq.{contact_id},target_contact_id.eq.{contact_id}').execute()

        if not rels_response.data:
            return f"{contact_name} 暂无关系记录"

        result = f"{contact_name} 的关系网络（共 {len(rels_response.data)} 条）：\n\n"

        for rel in rels_response.data:
            is_source = rel['source_contact_id'] == contact_id
            other_contact = rel['source_contacts'] if not is_source else rel['target_contacts']

            if other_contact:
                direction = "认识" if is_source else "被认识"
                result += f"• {direction}：{other_contact['name']}（{other_contact.get('company', '未知公司')}）\n"
                result += f"  关系类型：{rel['relationship_type']}，强度：{rel['strength']}\n"
                if rel.get('description'):
                    result += f"  描述：{rel['description']}\n"
                result += "\n"

        return result

    except APIError as e:
        return f"查询关系失败：{e.message}"
    except Exception as e:
        return f"查询关系失败：{str(e)}"
