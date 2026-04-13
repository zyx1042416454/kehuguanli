from coze_coding_dev_sdk.database import Base

from typing import Optional
import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Double, Integer, Numeric, PrimaryKeyConstraint, String, Text, ForeignKey, Index, func, text, Table
from sqlalchemy.dialects.postgresql import OID
from sqlalchemy.orm import Mapped, mapped_column

class HealthCheck(Base):
    __tablename__ = 'health_check'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='health_check_pkey'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), server_default=text('now()'))


t_pg_stat_statements = Table(
    'pg_stat_statements', Base.metadata,
    Column('userid', OID),
    Column('dbid', OID),
    Column('toplevel', Boolean),
    Column('queryid', BigInteger),
    Column('query', Text),
    Column('plans', BigInteger),
    Column('total_plan_time', Double(53)),
    Column('min_plan_time', Double(53)),
    Column('max_plan_time', Double(53)),
    Column('mean_plan_time', Double(53)),
    Column('stddev_plan_time', Double(53)),
    Column('calls', BigInteger),
    Column('total_exec_time', Double(53)),
    Column('min_exec_time', Double(53)),
    Column('max_exec_time', Double(53)),
    Column('mean_exec_time', Double(53)),
    Column('stddev_exec_time', Double(53)),
    Column('rows', BigInteger),
    Column('shared_blks_hit', BigInteger),
    Column('shared_blks_read', BigInteger),
    Column('shared_blks_dirtied', BigInteger),
    Column('shared_blks_written', BigInteger),
    Column('local_blks_hit', BigInteger),
    Column('local_blks_read', BigInteger),
    Column('local_blks_dirtied', BigInteger),
    Column('local_blks_written', BigInteger),
    Column('temp_blks_read', BigInteger),
    Column('temp_blks_written', BigInteger),
    Column('shared_blk_read_time', Double(53)),
    Column('shared_blk_write_time', Double(53)),
    Column('local_blk_read_time', Double(53)),
    Column('local_blk_write_time', Double(53)),
    Column('temp_blk_read_time', Double(53)),
    Column('temp_blk_write_time', Double(53)),
    Column('wal_records', BigInteger),
    Column('wal_fpi', BigInteger),
    Column('wal_bytes', Numeric),
    Column('jit_functions', BigInteger),
    Column('jit_generation_time', Double(53)),
    Column('jit_inlining_count', BigInteger),
    Column('jit_inlining_time', Double(53)),
    Column('jit_optimization_count', BigInteger),
    Column('jit_optimization_time', Double(53)),
    Column('jit_emission_count', BigInteger),
    Column('jit_emission_time', Double(53)),
    Column('jit_deform_count', BigInteger),
    Column('jit_deform_time', Double(53)),
    Column('stats_since', DateTime(True)),
    Column('minmax_stats_since', DateTime(True))
)


t_pg_stat_statements_info = Table(
    'pg_stat_statements_info', Base.metadata,
    Column('dealloc', BigInteger),
    Column('stats_reset', DateTime(True))
)


# 联系人表
class Contact(Base):
    __tablename__ = 'contacts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="姓名")
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="公司")
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="职位")
    contact_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium", comment="客户等级: high/medium/low")
    contact_frequency: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium", comment="联系频率: high/一周2次, medium/一周1次, low/一月1次")
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="电话")
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="邮箱")
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="城市")
    tags: Mapped[Optional[dict]] = mapped_column(Text, nullable=True, comment="标签，如校友、行业协会等")
    source: Mapped[str] = mapped_column(String(50), nullable=False, server_default="manual", comment="来源: alumni/industry_assoc/business_exchange/manual")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('contacts_name_idx', 'name'),
        Index('contacts_company_idx', 'company'),
        Index('contacts_contact_level_idx', 'contact_level'),
        Index('contacts_source_idx', 'source'),
    )


# 人脉关系表
class Relationship(Base):
    __tablename__ = 'relationships'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_contact_id: Mapped[int] = mapped_column(Integer, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)
    target_contact_id: Mapped[int] = mapped_column(Integer, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="关系类型: classmate/colleague/friend/business_partner")
    strength: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium", comment="关系强度: strong/medium/weak")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="关系描述")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('relationships_source_contact_idx', 'source_contact_id'),
        Index('relationships_target_contact_idx', 'target_contact_id'),
        Index('relationships_type_idx', 'relationship_type'),
    )


# 提醒规则表
class Alert(Base):
    __tablename__ = 'alerts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(Integer, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="提醒类型: follow_up/birthday/anniversary")
    trigger_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="触发条件")
    reminder_time: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="提醒时间")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active", comment="状态: active/inactive/completed")
    last_reminded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('alerts_contact_id_idx', 'contact_id'),
        Index('alerts_type_idx', 'alert_type'),
        Index('alerts_status_idx', 'status'),
    )


# 客户事件表（生日、纪念日等）
class CustomerEvent(Base):
    __tablename__ = 'customer_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(Integer, ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="事件类型: birthday/contract_anniversary/meeting")
    event_date: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, comment="事件日期")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="描述")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('customer_events_contact_id_idx', 'contact_id'),
        Index('customer_events_type_idx', 'event_type'),
        Index('customer_events_date_idx', 'event_date'),
    )


# 用户设置表
class UserSettings(Base):
    __tablename__ = 'user_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="飞书/企微 webhook 地址")
    notification_channel: Mapped[str] = mapped_column(String(50), nullable=False, server_default="feishu", comment="通知渠道: feishu/enterprise_wechat")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        Index('user_settings_channel_idx', 'notification_channel'),
    )
