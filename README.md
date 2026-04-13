# 智能人脉管理 Agent

一个基于 LangChain/LangGraph 的智能客户关系管理系统，支持从 Excel/CSV 导入联系人，构建六度人脉图谱，提供智能提醒和引荐策略。

## 核心功能

- **表格解析与入库**：自动识别 Excel/CSV 表头，清洗数据并存储到数据库
- **六度人脉路径查询**：在关系图谱中检索最短路径，提供中间人列表和建议话术
- **重要客户提醒**：支持跟进、生日、纪念日提醒，通过飞书推送卡片消息
- **关系增强建议**：分析关系网络薄弱环节，生成引荐文案和行动建议
- **表格模板生成**：动态生成校友表、行业协会表、通用联系人表模板
- **推送渠道管理**：支持飞书 Webhook 配置，发送文本、富文本和卡片消息

## 技术栈

- Python 3.9+
- LangChain 1.0
- LangGraph 1.0
- Supabase (PostgreSQL)
- Pandas, OpenPyXL
- coze-coding-dev-sdk
- Requests

## 数据库表结构

- `contacts`：联系人信息表
- `relationships`：人脉关系表
- `alerts`：提醒规则表
- `customer_events`：客户事件表（生日、纪念日等）
- `user_settings`：用户设置表

## 客户等级与联系频率

- **high**：一周2次
- **medium**：一周1次
- **low**：一月1次

## 本地运行

```bash
# 运行流程
bash scripts/local_run.sh -m flow

# 运行节点
bash scripts/local_run.sh -m node -n node_name
