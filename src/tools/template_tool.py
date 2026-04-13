from typing import Optional
from langchain.tools import tool
from coze_coding_dev_sdk import DocumentGenerationClient, XLSXConfig


@tool
def generate_alumni_template() -> str:
    """生成校友表模板（Excel格式）。

    Returns:
        Excel 文件的下载链接
    """
    try:
        client = DocumentGenerationClient(xlsx_config=XLSXConfig(header_bg_color="4472C4", auto_width=True))

        # 校友表模板数据
        template_data = [
            {
                "姓名": "张三",
                "公司": "阿里巴巴",
                "职位": "技术总监",
                "电话": "13800138000",
                "邮箱": "zhangsan@example.com",
                "城市": "杭州",
                "毕业年份": "2010",
                "专业": "计算机科学",
                "客户等级": "high",
                "联系频率": "high",
                "标签": "校友,技术"
            },
            {
                "姓名": "李四",
                "公司": "腾讯",
                "职位": "产品经理",
                "电话": "",
                "邮箱": "lisi@example.com",
                "城市": "深圳",
                "毕业年份": "2012",
                "专业": "软件工程",
                "客户等级": "medium",
                "联系频率": "medium",
                "标签": "校友,产品"
            }
        ]

        url = client.create_xlsx_from_list(template_data, "alumni_template", "校友表模板")

        return f"✅ 校友表模板已生成\n\n下载链接：{url}\n\n使用说明：\n- 第一行为示例数据，请删除后填写真实数据\n- 必填列：姓名\n- 可选列：公司、职位、电话、邮箱、城市等\n- 客户等级：high（高）/ medium（中）/ low（低）\n- 联系频率：high（一周2次）/ medium（一周1次）/ low（一月1次）"

    except Exception as e:
        return f"生成模板失败：{str(e)}"


@tool
def generate_industry_template() -> str:
    """生成行业协会表模板（Excel格式）。

    Returns:
        Excel 文件的下载链接
    """
    try:
        client = DocumentGenerationClient(xlsx_config=XLSXConfig(header_bg_color="4472C4", auto_width=True))

        # 行业协会表模板数据
        template_data = [
            {
                "姓名": "王五",
                "公司": "华为",
                "职位": "解决方案架构师",
                "电话": "13900139000",
                "邮箱": "wangwu@huawei.com",
                "城市": "深圳",
                "行业协会": "中国软件行业协会",
                "客户等级": "high",
                "联系频率": "medium",
                "标签": "协会,云计算"
            },
            {
                "姓名": "赵六",
                "公司": "字节跳动",
                "职位": "算法工程师",
                "电话": "",
                "邮箱": "zhaoliu@bytedance.com",
                "城市": "北京",
                "行业协会": "中国人工智能学会",
                "客户等级": "medium",
                "联系频率": "low",
                "标签": "协会,AI"
            }
        ]

        url = client.create_xlsx_from_list(template_data, "industry_template", "行业协会表模板")

        return f"✅ 行业协会表模板已生成\n\n下载链接：{url}\n\n使用说明：\n- 第一行为示例数据，请删除后填写真实数据\n- 必填列：姓名\n- 可选列：公司、职位、电话、邮箱、城市、行业协会等\n- 客户等级：high（高）/ medium（中）/ low（低）\n- 联系频率：high（一周2次）/ medium（一周1次）/ low（一月1次）"

    except Exception as e:
        return f"生成模板失败：{str(e)}"


@tool
def generate_contact_template() -> str:
    """生成通用联系人表模板（Excel格式）。

    Returns:
        Excel 文件的下载链接
    """
    try:
        client = DocumentGenerationClient(xlsx_config=XLSXConfig(header_bg_color="4472C4", auto_width=True))

        # 通用联系人表模板数据
        template_data = [
            {
                "姓名": "示例姓名",
                "公司": "示例公司",
                "职位": "示例职位",
                "电话": "13800000000",
                "邮箱": "example@example.com",
                "城市": "北京",
                "客户等级": "medium",
                "联系频率": "medium",
                "来源": "manual",
                "标签": "商务,合作",
                "关联联系人": "",
                "关系类型": "",
                "关系强度": "",
                "关系描述": ""
            }
        ]

        url = client.create_xlsx_from_list(template_data, "contact_template", "联系人表模板")

        return f"✅ 联系人表模板已生成\n\n下载链接：{url}\n\n使用说明：\n- 必填列：姓名\n- 可选列：公司、职位、电话、邮箱、城市、客户等级、联系频率等\n- 客户等级：high（高）/ medium（中）/ low（低）\n- 联系频率：high（一周2次）/ medium（一周1次）/ low（一月1次）\n- 来源：alumni（校友）/ industry_assoc（行业协会）/ business_exchange（商务交流）/ manual（手动）\n- 关系列用于建立联系人之间的关联"

    except Exception as e:
        return f"生成模板失败：{str(e)}"
