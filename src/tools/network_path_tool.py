from typing import Optional, List
from langchain.tools import tool
from postgrest.exceptions import APIError
from collections import deque

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略类型检查错误


@tool
def find_shortest_path(target_name: str, target_company: Optional[str] = None) -> str:
    """查找从当前用户到目标联系人的最短路径（六度人脉）。

    Args:
        target_name: 目标联系人姓名
        target_company: 目标公司（可选，用于更精确匹配）

    Returns:
        路径描述信息，包括中间人列表和建议话术
    """
    try:
        client = get_supabase_client()

        # 构建查询条件
        query = client.table('contacts').select('id, name, company, position')
        if target_company:
            query = query.eq('name', target_name).eq('company', target_company)
        else:
            query = query.eq('name', target_name)

        target_response = query.execute()

        if not target_response.data:
            return f"未找到目标联系人：{target_name}" + (f"（公司：{target_company}）" if target_company else "")

        target_data = target_response.data[0] if isinstance(target_response.data, list) and len(target_response.data) > 0 else {}
        if not isinstance(target_data, dict):
            return f"数据格式错误：无法解析目标联系人信息"
        target_id = target_data.get('id')
        target_info = target_data

        # 获取所有关系
        rels_response = client.table('relationships').select('source_contact_id, target_contact_id, relationship_type, strength').execute()
        relationships = rels_response.data

        # 构建邻接表
        graph = {}
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            src = rel.get('source_contact_id')
            tgt = rel.get('target_contact_id')
            if src is None or tgt is None:
                continue
            if src not in graph:
                graph[src] = []
            if tgt not in graph:
                graph[tgt] = []
            graph[src].append((tgt, rel))
            graph[tgt].append((src, rel))  # 无向图

        # BFS 查找最短路径（限制6跳）
        # 假设用户节点ID为0，或者需要指定起始节点
        # 这里我们简化：假设用户想要找到任何已存在的联系人到目标的最短路径

        # 获取所有联系人ID
        all_contacts_response = client.table('contacts').select('id, name, company, position').execute()
        contacts_map = {}
        for c in all_contacts_response.data:
            if isinstance(c, dict) and 'id' in c:
                contacts_map[c['id']] = c

        if not contacts_map:
            return "数据库中没有联系人数据，无法计算路径"

        # 使用第一个联系人作为起点，或者让用户指定起点
        start_nodes = list(contacts_map.keys())

        best_path = None
        best_start = None

        for start_id in start_nodes:
            if start_id == target_id:
                continue

            visited = set()
            queue = deque([(start_id, [])])

            while queue:
                current, path = queue.popleft()

                if current == target_id:
                    if best_path is None or len(path) < len(best_path):
                        best_path = path
                        best_start = start_id
                    break

                if current in visited or len(path) >= 6:
                    continue

                visited.add(current)

                if current in graph:
                    for neighbor, rel in graph[current]:
                        if neighbor not in visited:
                            queue.append((neighbor, path + [(current, neighbor, rel)]))

        if best_path is None:
            return f"未找到从现有联系人到 {target_name} 的路径（限制6跳以内）\n\n建议：\n1. 参加相关行业活动\n2. 通过共同校友圈寻找连接\n3. 直接联系该目标联系人"

        # 构建路径描述
        path_description = f"📊 最短路径（共 {len(best_path)} 跳）：\n\n"

        # 获取起点信息
        start_contact = contacts_map.get(best_start, {})
        if isinstance(start_contact, dict):
            path_description += f"起点：{start_contact.get('name', '未知')}（{start_contact.get('company', '')} - {start_contact.get('position', '')}）\n"

        for i, step in enumerate(best_path):
            if not isinstance(step, (list, tuple)) or len(step) < 3:
                continue
            src_id, tgt_id, rel = step
            src_contact = contacts_map.get(src_id, {})
            tgt_contact = contacts_map.get(tgt_id, {})

            path_description += f"  ↓\n"
            src_name = src_contact.get('name', '未知') if isinstance(src_contact, dict) else '未知'
            tgt_name = tgt_contact.get('name', '未知') if isinstance(tgt_contact, dict) else '未知'
            rel_type = rel.get('relationship_type', '未知') if isinstance(rel, dict) else '未知'
            rel_strength = rel.get('strength', '未知') if isinstance(rel, dict) else '未知'

            path_description += f"第{i+1}跳：{src_name} → {tgt_name}\n"
            path_description += f"  关系类型：{rel_type}，强度：{rel_strength}\n"
            if i == len(best_path) - 1:
                tgt_company = target_info.get('company', '') if isinstance(target_info, dict) else ''
                tgt_position = target_info.get('position', '') if isinstance(target_info, dict) else ''
                path_description += f"  目标：{tgt_name}（{tgt_company} - {tgt_position}）\n"

        # 生成建议话术
        path_description += f"\n💡 建议话术：\n\n"
        path_description += f"如果是通过中间人引荐：\n"
        if len(best_path) > 0:
            first_step = best_path[0]
            first_intermediary = contacts_map[first_step[1]]
            path_description += f"1. 先联系 {first_intermediary['name']}：\n"
            path_description += f'   "您好！我了解到您认识 {target_name}，能否帮忙引荐一下？我有一些合作的想法想与TA探讨。"\n\n'

        path_description += f"2. 联系 {target_name}：\n"
        path_description += f'   "您好！我是通过 {first_intermediary["name"] if len(best_path) > 0 else "朋友"} 了解到您的，希望能有机会交流一下。"\n'

        return path_description

    except APIError as e:
        return f"查询路径失败：{e.message}"
    except Exception as e:
        return f"查询路径失败：{str(e)}"


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
