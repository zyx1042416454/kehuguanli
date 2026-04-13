import os
import json
from typing import Annotated
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from coze_coding_utils.runtime_ctx.context import default_headers
from storage.memory.memory_saver import get_memory_saver

# 导入工具
from tools.contact_import_tool import import_contacts_from_excel, create_contact
from tools.network_path_tool import find_shortest_path, search_contacts, get_contact_relationships
from tools.alert_tool import create_follow_up_alert, get_pending_reminders, complete_alert, create_birthday_reminder
from tools.relationship_suggestion_tool import generate_referral_script, analyze_relationship_gaps, get_high_value_contacts
from tools.template_tool import generate_alumni_template, generate_industry_template, generate_contact_template
from tools.notification_tool import configure_feishu_webhook, send_feishu_message, send_reminder_card
from tools.broadcast_tool import (
    broadcast_pending_reminders,
    push_high_value_contacts,
    push_daily_summary,
    push_weekly_report,
    push_contact_birthday_upcoming
)

# type: ignore  # 忽略类型检查错误

LLM_CONFIG = "config/agent_llm_config.json"

# 默认保留最近 20 轮对话 (40 条消息)
MAX_MESSAGES = 40

def _windowed_messages(old, new):
    """滑动窗口: 只保留最近 MAX_MESSAGES 条消息"""
    return add_messages(old, new)[-MAX_MESSAGES:]

class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]

def build_agent(ctx=None):
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    config_path = os.path.join(workspace_path, LLM_CONFIG)

    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")

    llm = ChatOpenAI(
        model=cfg['config'].get("model"),
        api_key=api_key,
        base_url=base_url,
        temperature=cfg['config'].get('temperature', 0.7),
        streaming=True,
        timeout=cfg['config'].get('timeout', 600),
        extra_body={
            "thinking": {
                "type": cfg['config'].get('thinking', 'disabled')
            }
        },
        default_headers=default_headers(ctx) if ctx else {}
    )

    # 工具列表
    tools = [
        # 表格解析与入库
        import_contacts_from_excel,
        create_contact,

        # 六度人脉路径查询
        find_shortest_path,
        search_contacts,
        get_contact_relationships,

        # 重要客户提醒
        create_follow_up_alert,
        get_pending_reminders,
        complete_alert,
        create_birthday_reminder,

        # 关系增强建议
        generate_referral_script,
        analyze_relationship_gaps,
        get_high_value_contacts,

        # 表格模板生成
        generate_alumni_template,
        generate_industry_template,
        generate_contact_template,

        # 推送渠道管理（飞书）
        configure_feishu_webhook,
        send_feishu_message,
        send_reminder_card,

        # 批量推送功能
        broadcast_pending_reminders,
        push_high_value_contacts,
        push_daily_summary,
        push_weekly_report,
        push_contact_birthday_upcoming
    ]

    return create_agent(
        model=llm,
        system_prompt=cfg.get("sp"),
        tools=tools,
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )
