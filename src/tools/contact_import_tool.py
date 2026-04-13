import os
import pandas as pd
import json
from datetime import datetime
from typing import Optional
from langchain.tools import tool
from postgrest.exceptions import APIError

from storage.database.supabase_client import get_supabase_client

# type: ignore  # 忽略 pandas 类型检查错误


@tool
def import_contacts_from_excel(file_path: str, source_type: str = "manual") -> str:
    """从Excel或CSV文件导入联系人信息到数据库。

    Args:
        file_path: Excel或CSV文件的路径
        source_type: 数据来源类型（alumni/industry_assoc/business_exchange/manual）

    Returns:
        导入结果的描述信息
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"错误：文件不存在 - {file_path}"

        # 读取文件
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df = pd.read_excel(file_path)
        elif file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            return "错误：不支持的文件格式，仅支持 .xlsx, .xls 和 .csv"

        # 检查必需列
        required_columns = ['姓名']
        for col in required_columns:
            if col not in df.columns:
                return f"错误：缺少必需列 - {col}"

        # 获取数据库客户端
        client = get_supabase_client()

        # 准备数据
        contacts_data = []
        for idx, row in df.iterrows():  # type: ignore
            contact = {
                'name': str(row['姓名']).strip() if pd.notna(row['姓名']) else '',  # type: ignore
                'company': str(row.get('公司', '')).strip() if pd.notna(row.get('公司')) and str(row.get('公司', '')) != 'nan' else None,  # type: ignore
                'position': str(row.get('职位', '')).strip() if pd.notna(row.get('职位')) and str(row.get('职位', '')) != 'nan' else None,  # type: ignore
                'phone': str(row.get('电话', '')).strip() if pd.notna(row.get('电话')) and str(row.get('电话', '')) != 'nan' else None,  # type: ignore
                'email': str(row.get('邮箱', '')).strip() if pd.notna(row.get('邮箱')) and str(row.get('邮箱', '')) != 'nan' else None,  # type: ignore
                'city': str(row.get('城市', '')).strip() if pd.notna(row.get('城市')) and str(row.get('城市', '')) != 'nan' else None,  # type: ignore
                'source': source_type,
                'contact_level': str(row.get('客户等级', 'medium')).strip() if pd.notna(row.get('客户等级')) else 'medium',  # type: ignore
                'contact_frequency': str(row.get('联系频率', 'medium')).strip() if pd.notna(row.get('联系频率')) else 'medium',  # type: ignore
            }

            # 解析标签
            tags = {}
            if pd.notna(row.get('标签')) and str(row.get('标签', '')) != 'nan':  # type: ignore
                tags['tags'] = str(row['标签'])  # type: ignore
            if pd.notna(row.get('毕业年份')) and str(row.get('毕业年份', '')) != 'nan':  # type: ignore
                tags['graduation_year'] = str(row['毕业年份'])  # type: ignore
            if pd.notna(row.get('专业')) and str(row.get('专业', '')) != 'nan':  # type: ignore
                tags['major'] = str(row['专业'])  # type: ignore

            if tags:
                contact['tags'] = json.dumps(tags, ensure_ascii=False)

            contacts_data.append(contact)

        # 批量插入数据库
        if contacts_data:
            response = client.table('contacts').insert(contacts_data).execute()

            # 分析结果
            imported_count = len(response.data)
            total_rows = len(df)

            # 提取并存储关系信息（如果存在关联列）
            relationships_data = []
            for idx, row in df.iterrows():  # type: ignore
                if pd.notna(row.get('关联联系人')) and str(row.get('关联联系人', '')) != 'nan':  # type: ignore
                    source_name = str(row['姓名']).strip()  # type: ignore
                    target_name = str(row['关联联系人']).strip()  # type: ignore

                    # 查找源联系人ID
                    try:
                        source_response = client.table('contacts').select('id').eq('name', source_name).execute()
                        if source_response.data and isinstance(source_response.data, list) and len(source_response.data) > 0:
                            source_id = source_response.data[0]['id']

                            # 查找目标联系人ID
                            target_response = client.table('contacts').select('id').eq('name', target_name).execute()
                            if target_response.data and isinstance(target_response.data, list) and len(target_response.data) > 0:
                                target_id = target_response.data[0]['id']

                                # 创建关系
                                rel_type_val = str(row.get('关系类型', 'friend')).strip() if pd.notna(row.get('关系类型')) else 'friend'  # type: ignore
                                rel_strength_val = str(row.get('关系强度', 'medium')).strip() if pd.notna(row.get('关系强度')) else 'medium'  # type: ignore
                                rel_desc_val = str(row.get('关系描述', '')).strip() if pd.notna(row.get('关系描述')) and str(row.get('关系描述', '')) != 'nan' else None  # type: ignore

                                relationships_data.append({
                                    'source_contact_id': source_id,
                                    'target_contact_id': target_id,
                                    'relationship_type': rel_type_val,
                                    'strength': rel_strength_val,
                                    'description': rel_desc_val
                                })
                    except APIError:
                        continue

            if relationships_data:
                client.table('relationships').insert(relationships_data).execute()

            return f"成功导入 {imported_count}/{total_rows} 条联系人记录。{'创建了 ' + str(len(relationships_data)) + ' 条关系记录。' if relationships_data else ''}"
        else:
            return "警告：没有有效的联系人数据可导入"

    except Exception as e:
        return f"导入失败：{str(e)}"


@tool
def create_contact(name: str, company: Optional[str] = None, position: Optional[str] = None,
                   phone: Optional[str] = None, email: Optional[str] = None,
                   contact_level: str = "medium", contact_frequency: str = "medium",
                   source: str = "manual", city: Optional[str] = None) -> str:
    """创建单个联系人。

    Args:
        name: 姓名（必需）
        company: 公司
        position: 职位
        phone: 电话
        email: 邮箱
        contact_level: 客户等级（high/medium/low）
        contact_frequency: 联系频率（high-一周2次, medium-一周1次, low-一月1次）
        source: 数据来源
        city: 城市

    Returns:
        创建结果的描述信息
    """
    try:
        client = get_supabase_client()

        contact_data = {
            'name': name.strip(),
            'company': company.strip() if company else None,
            'position': position.strip() if position else None,
            'phone': phone.strip() if phone else None,
            'email': email.strip() if email else None,
            'city': city.strip() if city else None,
            'contact_level': contact_level,
            'contact_frequency': contact_frequency,
            'source': source
        }

        response = client.table('contacts').insert(contact_data).execute()
        return f"成功创建联系人：{name}，ID：{response.data[0]['id']}"

    except APIError as e:
        return f"创建联系人失败：{e.message}"
    except Exception as e:
        return f"创建联系人失败：{str(e)}"
