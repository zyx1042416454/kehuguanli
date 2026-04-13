from typing import Optional, List, Dict
from langchain.tools import tool
from postgrest.exceptions import APIError
from collections import deque
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import SearchClient, LLMClient
from langchain_core.messages import SystemMessage, HumanMessage
import json

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略类型检查错误
# pyright: reportOptionalMemberAccess=false
# pyright: reportGeneralTypeIssues=false


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


def _extract_partner_info(search_text: str, target_company: str) -> List[Dict]:
    """使用LLM从搜索结果中提取详细的合作伙伴信息"""
    ctx_llm = new_context(method="extract_detailed_partners")
    llm_client = LLMClient(ctx=ctx_llm)

    extract_prompt = f"""
从以下文本中提取关于"{target_company}"的合作伙伴信息。

文本内容：
{search_text[:3000]}

请以JSON格式返回合作伙伴信息，包含以下字段：
1. name: 公司名称
2. type: 合作类型（客户/供应商/战略合作伙伴/投资方/技术合作伙伴/渠道合作伙伴）
3. level: 合作深度（核心/普通/潜在）
4. description: 合作描述（简短说明）

返回格式示例：
[
  {{
    "name": "国轩高科",
    "type": "客户",
    "level": "核心",
    "description": "主要电池供应商，长期合作"
  }},
  {{
    "name": "宁德时代",
    "type": "供应商",
    "level": "核心",
    "description": "战略合作伙伴，共同研发"
  }}
]

要求：
1. 只返回明确的合作伙伴信息
2. 最多返回 10 个合作伙伴
3. 必须是有效的JSON格式
"""

    extract_messages = [
        SystemMessage(content="你是专业的信息提取专家，擅长从文本中提取合作伙伴的详细信息。"),
        HumanMessage(content=extract_prompt)
    ]

    try:
        extract_response = llm_client.invoke(messages=extract_messages, temperature=0.2, model="doubao-seed-1-6-251015")
        extract_result = _get_text_content(extract_response.content)

        # 尝试解析JSON
        try:
            # 清理可能的markdown标记
            extract_result = extract_result.strip()
            if extract_result.startswith("```json"):
                extract_result = extract_result[7:]
            if extract_result.startswith("```"):
                extract_result = extract_result[3:]
            if extract_result.endswith("```"):
                extract_result = extract_result[:-3]
            extract_result = extract_result.strip()

            partners = json.loads(extract_result)
            if isinstance(partners, list):
                return partners
        except json.JSONDecodeError:
            pass

        # JSON解析失败，回退到简单提取
        partners = []
        lines = extract_result.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 2 and target_company not in line:
                partners.append({
                    "name": line.lstrip("0123456789.-•、 '\""),
                    "type": "未知",
                    "level": "普通",
                    "description": ""
                })
        return partners

    except Exception as e:
        return []


def _find_path_to_target(client, start_contact_id: int, target_company: str, visited: set = None, max_depth: int = 4) -> List[Dict]:
    """通过BFS查找从起始联系人到目标公司的最短路径"""
    if visited is None:
        visited = set()
    
    if start_contact_id in visited or max_depth == 0:
        return []
    
    visited.add(start_contact_id)
    
    # 查询起始联系人的所有关系
    rels_response = client.table('relationships').select(
        'source_contact_id, target_contact_id, relationship_type, strength, description'
    ).or_(f'source_contact_id.eq.{start_contact_id},target_contact_id.eq.{start_contact_id}').execute()
    
    for rel in rels_response.data:
        if not isinstance(rel, dict):
            continue
        
        # 确定下一跳的联系人ID
        if rel['source_contact_id'] == start_contact_id:
            next_id = rel['target_contact_id']
        else:
            next_id = rel['source_contact_id']
        
        # 查询下一跳联系人的公司信息
        contact_response = client.table('contacts').select('id, name, company, position').eq('id', next_id).execute()
        
        if contact_response.data:
            contact_info = contact_response.data[0]
            if isinstance(contact_info, dict):
                company = contact_info.get('company', '')
                
                # 检查是否到达目标公司
                if company == target_company or target_company in company:
                    # 找到了路径！
                    return [{
                        'contact_id': next_id,
                        'name': contact_info.get('name', ''),
                        'company': company,
                        'position': contact_info.get('position', ''),
                        'relationship_type': rel.get('relationship_type', ''),
                        'strength': rel.get('strength', ''),
                        'description': rel.get('description', ''),
                        'is_target': True
                    }]
                
                # 继续递归查找
                if next_id not in visited:
                    remaining_path = _find_path_to_target(client, next_id, target_company, visited.copy(), max_depth - 1)
                    if remaining_path:
                        return [{
                            'contact_id': next_id,
                            'name': contact_info.get('name', ''),
                            'company': company,
                            'position': contact_info.get('position', ''),
                            'relationship_type': rel.get('relationship_type', ''),
                            'strength': rel.get('strength', ''),
                            'description': rel.get('description', ''),
                            'is_target': False
                        }] + remaining_path
    
    return []


@tool
def find_shortest_path(target_name: str, target_company: Optional[str] = None) -> str:
    """通过多种路径查找潜在引荐中间人（展示完整的人脉链路）。

    Args:
        target_name: 目标联系人姓名（如"刘蕾"）
        target_company: 目标公司（如"巨一科技"）

    Returns:
        推荐的引荐中间人列表和完整的人脉路径

    业务逻辑：
        路径1（重点）：通过业务合作单位
            - 细分为：客户、供应商、战略合作伙伴、投资方、技术合作伙伴、渠道合作伙伴
            - 区分合作深度：核心、普通、潜在
            - 查找完整的人脉链路：我 → 中间人 → ... → 目标公司
        路径2：通过行业协会
        路径3：通过校友人脉
    """
    try:
        client = get_supabase_client()

        # 如果没有提供公司名称，无法查询
        if not target_company:
            return f"请提供目标公司名称，以便为您查找相关的人脉资源。\n\n使用示例：\n- 我想认识巨一科技的刘蕾\n- 请帮我找一下字节跳动的张三"

        result = f"""🎯 目标：认识 {target_name}（{target_company}）

🔍 正在为您分析人脉链路...

"""

        # 获取当前用户的所有联系人
        my_contacts_response = client.table('contacts').select('id, name, company, position, contact_level, phone, email').execute()
        my_contacts = {c['id']: c for c in my_contacts_response.data if isinstance(c, dict)}
        
        if not my_contacts:
            return f"❌ 您的人脉数据库中暂无联系人，请先导入联系人信息。"
        
        result += f"📊 您的人脉数据库中有 {len(my_contacts)} 个联系人\n\n"

        # 存储所有找到的路径
        all_paths = []

        # ========== 路径1：通过业务合作单位（细化版）==========
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "📍 路径1：通过业务合作单位\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        try:
            # 1.1 搜索核心合作伙伴
            result += "🔍 搜索核心战略合作伙伴...\n"
            ctx_strategic = new_context(method="search_strategic_partners")
            search_client = SearchClient(ctx=ctx_strategic)
            search_query = f"{target_company} 战略合作伙伴 核心供应商 主要客户 深度合作"
            strategic_response = search_client.web_search_with_summary(query=search_query, count=10)

            # 1.2 搜索供应商
            result += "🔍 搜索供应商信息...\n"
            ctx_supplier = new_context(method="search_suppliers")
            search_query = f"{target_company} 供应商 供应链 采购"
            supplier_response = search_client.web_search_with_summary(query=search_query, count=10)

            # 1.3 搜索客户
            result += "🔍 搜索客户信息...\n"
            ctx_customer = new_context(method="search_customers")
            search_query = f"{target_company} 客户 合作项目"
            customer_response = search_client.web_search_with_summary(query=search_query, count=10)

            # 1.4 搜索技术合作伙伴
            result += "🔍 搜索技术合作伙伴...\n"
            ctx_tech = new_context(method="search_tech_partners")
            search_query = f"{target_company} 技术合作 联合研发 技术伙伴"
            tech_response = search_client.web_search_with_summary(query=search_query, count=10)

            # 1.5 搜索投资方
            result += "🔍 搜索投资方信息...\n"
            ctx_invest = new_context(method="search_investors")
            search_query = f"{target_company} 投资方 融资 股东"
            invest_response = search_client.web_search_with_summary(query=search_query, count=10)

            # 合并所有搜索结果
            all_search_results = []
            for resp in [strategic_response, supplier_response, customer_response, tech_response, invest_response]:
                if resp.web_items:
                    all_search_results.extend(resp.web_items)

            # 提取合作伙伴详细信息
            if all_search_results:
                search_text = ""
                for item in all_search_results[:15]:
                    if item.title:
                        search_text += item.title + " "
                    if item.snippet:
                        search_text += item.snippet + " "
                    if item.summary:
                        search_text += item.summary + " "

                partners = _extract_partner_info(search_text, target_company)

                if partners:
                    result += f"✅ 提取到 {len(partners)} 个合作伙伴信息：\n\n"

                    # 按合作类型分组
                    type_groups = {
                        "客户": [],
                        "供应商": [],
                        "战略合作伙伴": [],
                        "投资方": [],
                        "技术合作伙伴": [],
                        "渠道合作伙伴": [],
                        "未知": []
                    }

                    for partner in partners:
                        p_type = partner.get('type', '未知')
                        if p_type not in type_groups:
                            p_type = '未知'
                        type_groups[p_type].append(partner)

                    # 展示每个类型的合作伙伴
                    for p_type, p_list in type_groups.items():
                        if p_list:
                            result += f"📋 {p_type}（{len(p_list)}个）：\n"
                            for partner in p_list[:3]:
                                level_icon = {'核心': '⭐', '普通': '🔹', '潜在': '💫'}.get(partner.get('level', '普通'), '🔹')
                                result += f"  {level_icon} {partner.get('name', '')}"
                                if partner.get('description'):
                                    result += f" - {partner.get('description', '')}"
                                result += "\n"
                            if len(p_list) > 3:
                                result += f"  ...还有 {len(p_list) - 3} 个\n"
                            result += "\n"

                    result += "🔗 分析人脉链路...\n\n"

                    # 为每个合作伙伴查找人脉链路
                    for partner in partners[:10]:  # 最多分析10个合作伙伴
                        company_name = partner.get('name', '').strip()
                        if not company_name or company_name == target_company:
                            continue

                        # 查找我在该公司的直接联系人
                        direct_contacts = client.table('contacts').select(
                            'id, name, company, position, contact_level, phone, email'
                        ).eq('company', company_name).execute()

                        if direct_contacts.data:
                            for contact in direct_contacts.data:
                                if isinstance(contact, dict):
                                    contact_id = contact['id']
                                    contact_name = contact.get('name', '')
                                    
                                    # 找到直接联系人，尝试从TA出发找路径
                                    path_to_target = _find_path_to_target(client, contact_id, target_company)
                                    
                                    if path_to_target:
                                        # 找到完整路径了！
                                        level_weight = {
                                            '核心': 3, '普通': 2, '潜在': 1
                                        }.get(partner.get('level', '普通'), 2)
                                        
                                        type_weight = {
                                            '战略合作伙伴': 5, '投资方': 4, '客户': 3,
                                            '供应商': 3, '技术合作伙伴': 3, '渠道合作伙伴': 2, '未知': 1
                                        }.get(partner.get('type', '未知'), 1)
                                        
                                        full_path = [{
                                            'name': contact_name,
                                            'company': company_name,
                                            'position': contact.get('position', ''),
                                            'contact_level': contact.get('contact_level', 'medium'),
                                            'phone': contact.get('phone', ''),
                                            'email': contact.get('email', ''),
                                            'relationship_to_me': '直接认识',
                                            'partner_type': partner.get('type', '未知'),
                                            'partner_level': partner.get('level', '普通'),
                                            'partner_desc': partner.get('description', ''),
                                            'weight': level_weight + type_weight,
                                            'path_length': len(path_to_target) + 1,
                                            'full_path': [contact] + path_to_target
                                        }]
                                        
                                        all_paths.append(full_path[0])
                                    else:
                                        # 没找到路径，但直接联系人也可能是中间人
                                        level_weight = {
                                            '核心': 3, '普通': 2, '潜在': 1
                                        }.get(partner.get('level', '普通'), 2)
                                        
                                        type_weight = {
                                            '战略合作伙伴': 5, '投资方': 4, '客户': 3,
                                            '供应商': 3, '技术合作伙伴': 3, '渠道合作伙伴': 2, '未知': 1
                                        }.get(partner.get('type', '未知'), 1)
                                        
                                        all_paths.append({
                                            'name': contact_name,
                                            'company': company_name,
                                            'position': contact.get('position', ''),
                                            'contact_level': contact.get('contact_level', 'medium'),
                                            'phone': contact.get('phone', ''),
                                            'email': contact.get('email', ''),
                                            'relationship_to_me': '直接认识',
                                            'partner_type': partner.get('type', '未知'),
                                            'partner_level': partner.get('level', '普通'),
                                            'partner_desc': partner.get('description', ''),
                                            'weight': level_weight + type_weight - 2,  # 降低权重
                                            'path_length': 2,  # 我 → 中间人 → 目标公司
                                            'full_path': [contact]  # 没有中间节点
                                        })

                    # 模糊匹配
                    fuzzy_contacts = []
                    for contact in my_contacts.values():
                        company = contact.get('company', '')
                        if company and any(partner.get('name', '') in company for partner in partners):
                            fuzzy_contacts.append(contact)
                    
                    if fuzzy_contacts:
                        for contact in fuzzy_contacts[:5]:
                            contact_id = contact['id']
                            contact_name = contact.get('name', '')
                            
                            # 从TA出发找路径
                            path_to_target = _find_path_to_target(client, contact_id, target_company)
                            
                            if path_to_target:
                                all_paths.append({
                                    'name': contact_name,
                                    'company': contact.get('company', ''),
                                    'position': contact.get('position', ''),
                                    'contact_level': contact.get('contact_level', 'medium'),
                                    'phone': contact.get('phone', ''),
                                    'email': contact.get('email', ''),
                                    'relationship_to_me': '直接认识',
                                    'partner_type': '相关公司',
                                    'partner_level': '普通',
                                    'partner_desc': '',
                                    'weight': 2,
                                    'path_length': len(path_to_target) + 1,
                                    'full_path': [contact] + path_to_target
                                })

                    if all_paths:
                        result += f"✅ 找到 {len(all_paths)} 条人脉链路\n\n"
                    else:
                        result += "⚠️ 未找到完整的人脉链路\n\n"
                else:
                    result += "⚠️ 未能提取到明确的合作伙伴信息\n\n"
            else:
                result += "⚠️ 互联网搜索未返回结果\n\n"

        except Exception as e:
            result += f"⚠️ 业务合作搜索失败：{str(e)}\n\n"

        # ========== 汇总结果 ==========
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "📋 推荐结果汇总\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if not all_paths:
            result += f"❌ 未找到可以引荐的中间人\n\n"
            result += f"""💡 建议：
1. 在领英（LinkedIn）上搜索 {target_company} 的员工
2. 参加相关行业会议和展会
3. 通过共同的朋友或同事引荐
4. 关注 {target_company} 官方社交媒体动态
5. 导入更多联系人到人脉数据库
"""
        else:
            # 排序：权重高优先，路径短优先
            sorted_paths = sorted(all_paths, key=lambda x: (-x.get('weight', 0), x.get('path_length', 999)))

            result += f"✅ 找到 {len(sorted_paths)} 条人脉链路（按推荐优先级排序）：\n\n"

            for i, path_info in enumerate(sorted_paths, 1):
                full_path = path_info.get('full_path', [])
                
                result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                result += f"📍 路径{i}：{path_info.get('path_length', 0)}跳\n"
                result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                # 构建路径图
                result += "🔗 完整链路：\n"
                for j, contact in enumerate(full_path):
                    if isinstance(contact, dict):
                        if j == 0:
                            result += f"  我 → {contact.get('name', '')}（{contact.get('company', '')}）\n"
                        elif contact.get('is_target'):
                            result += f"  → {contact.get('name', '')}（{contact.get('company', '')}）⭐目标\n"
                        else:
                            rel_type = contact.get('relationship_type', '认识')
                            result += f"  → {contact.get('name', '')}（{contact.get('company', '')}）【{rel_type}】\n"
                result += "\n"
                
                # 第一跳联系人详情
                first_contact = full_path[0]
                result += f"👤 首跳联系人（您的直接联系人）：\n"
                result += f"  姓名：{first_contact.get('name', '')}\n"
                result += f"  公司：{first_contact.get('company', '')}\n"
                result += f"  职位：{first_contact.get('position', '')}\n"
                result += f"  等级：{first_contact.get('contact_level', 'medium')}\n"
                result += f"  电话：{first_contact.get('phone', '未填写')}\n"
                result += f"  邮箱：{first_contact.get('email', '未填写')}\n"
                
                # 合作信息
                if path_info.get('partner_type'):
                    level_icon = {'核心': '⭐', '普通': '🔹', '潜在': '💫'}.get(path_info.get('partner_level', '普通'), '🔹')
                    result += f"  📊 合作信息：{level_icon} {path_info.get('partner_level', '普通')} - {path_info.get('partner_type', '未知')}\n"
                    if path_info.get('partner_desc'):
                        result += f"  📝 描述：{path_info.get('partner_desc', '')}\n"
                
                result += "\n"
                
                # 如果有中间跳
                if len(full_path) > 2:
                    result += f"🔄 中间跳（{len(full_path) - 2}人）：\n"
                    for j, contact in enumerate(full_path[1:-1], 1):
                        if isinstance(contact, dict):
                            result += f"  第{j}跳：{contact.get('name', '')}（{contact.get('company', '')}）\n"
                            result += f"        关系：{contact.get('relationship_type', '未知')}，强度：{contact.get('strength', '未知')}\n"
                    result += "\n"
                
                # 目标联系人
                target_contact = full_path[-1]
                result += f"🎯 目标联系人：\n"
                result += f"  姓名：{target_name}\n"
                result += f"  公司：{target_company}\n"
                result += f"  状态：需要通过链路引荐\n"
                
                result += "\n\n"

            # 生成引荐话术（使用最佳路径）
            result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            result += "📝 推荐引荐话术（基于最佳路径）\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            if sorted_paths:
                best_path = sorted_paths[0]
                first_contact = best_path['full_path'][0]
                company_name = first_contact.get('company', '')

                ctx_script = new_context(method="generate_referral_script")
                llm_client = LLMClient(ctx=ctx_script)

                script_prompt = f"""
请为我生成一条请求引荐的话术。

目标联系人：{target_name}
目标公司：{target_company}

我的直接联系人：
- 姓名：{first_contact.get('name', '')}
- 公司：{company_name}
- 职位：{first_contact.get('position', '')}

背景：
{target_company} 与 {company_name} 有业务关联，所以我想通过 {first_contact.get('name', '')} 来引荐认识 {target_name}。

请生成一段礼貌且专业的请求话术，内容包括：
1. 自我介绍（假设我是商务合作方）
2. 说明想认识 {target_name} 的原因和合作意向
3. 提到 {company_name} 与 {target_company} 有业务往来
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

                result += f"{referral_script}\n\n"

            # 行动建议
            result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            result += "📌 下一步行动建议\n"
            result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            result += "1. 优先选择跳数少的路径（推荐优先级最高）\n"
            result += "2. 准备好自我介绍和合作方案\n"
            result += "3. 说明具体的合作意向和价值\n"
            result += "4. 表达对对方时间的尊重和感谢\n"
            result += "5. 如果路径较长，可以考虑分步引荐\n"

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
        query = client.table('contacts').select('id, name, company, position, contact_level, contact_frequency, city, source, phone, email, tags')

        # 添加关键词搜索
        if keyword:
            query = query.or_(f'name.ilike.%{keyword}%,company.ilike.%{keyword}%,position.ilike.%{keyword}%,tags.ilike.%{keyword}%')

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
            if contact.get('tags'):
                result += f"\n  标签：{contact['tags']}"
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
