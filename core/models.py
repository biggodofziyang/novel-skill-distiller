"""Pydantic数据模型定义.

包含素材、拆解规则、规则集、Skill、创作项目、反馈样本等全部领域模型.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from core.constants import (
    AnalysisDimension,
    CreationStep,
    DistillMode,
    FeedbackCategory,
    FeedbackType,
    SkillLayer,
    SkillStatus,
)


# ============================ 基础混合类 ============================


class TimestampMixin(BaseModel):
    """时间戳混入类."""

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ============================ 素材与文本 ============================


class NovelMaterial(BaseModel):
    """原始网文素材.

    Attributes:
        id: 唯一标识.
        filename: 原始文件名.
        raw_text: 原始文本内容.
        file_size: 文件大小(字节).
        uploaded_at: 上传时间.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    raw_text: str
    file_size: int = Field(ge=0, default=0)
    uploaded_at: datetime = Field(default_factory=datetime.now)

    @field_validator("filename")
    @classmethod
    def _validate_filename(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("文件名不能为空")
        return value.strip()


class CleanedText(BaseModel):
    """清洗后的文本.

    Attributes:
        material_id: 关联的素材ID.
        cleaned_text: 清洗后的文本.
        removed_chars_count: 移除的字符数.
        removed_paragraphs_count: 移除的段落数.
        chunks: 分块后的文本列表.
    """

    material_id: str
    cleaned_text: str
    removed_chars_count: int = Field(ge=0, default=0)
    removed_paragraphs_count: int = Field(ge=0, default=0)
    chunks: list[str] = Field(default_factory=list)


# ============================ 拆解规则 ============================


class AnalysisRule(BaseModel):
    """单条拆解规则（LLM输出原始结构）.

    Attributes:
        id: 唯一标识.
        content: 规则内容描述.
        weight: 重要性权重(0-100).
        source_chunk_index: 来源分块索引.
        line_range: 原文行号范围(可选).
        explanation: 规则解释说明.
        examples: 原文示例片段.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    weight: int = Field(ge=0, le=100, default=50)
    source_chunk_index: int = Field(ge=0, default=0)
    line_range: tuple[int, int] | None = None
    explanation: str = ""
    examples: list[str] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("规则内容不能为空")
        return value.strip()


class AnalysisFile(BaseModel):
    """某一维度的拆解结果文件.

    Attributes:
        id: 唯一标识.
        material_id: 关联素材ID.
        dimension: 分析维度.
        rules: 拆解出的规则列表.
        summary: 该维度总结.
        created_at: 创建时间.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    material_id: str
    dimension: AnalysisDimension
    rules: list[AnalysisRule] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=datetime.now)


# ============================ 规则集 ============================


class Rule(BaseModel):
    """统一规则（蒸馏后的标准规则）.

    Attributes:
        id: 唯一标识.
        dimension: 所属分析维度.
        content: 规则内容.
        weight: 权重(0-100).
        source_material_ids: 来源素材ID列表.
        conflicting_rule_ids: 冲突规则ID列表.
        is_empty: 是否为空话/无效规则.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    dimension: AnalysisDimension
    content: str
    weight: int = Field(ge=0, le=100, default=50)
    source_material_ids: list[str] = Field(default_factory=list)
    conflicting_rule_ids: list[str] = Field(default_factory=list)
    is_empty: bool = False

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("规则内容不能为空")
        return value.strip()


class RuleSet(BaseModel):
    """规则集（一次蒸馏产出）.

    Attributes:
        id: 唯一标识.
        name: 规则集名称.
        distill_mode: 蒸馏模式.
        source_material_ids: 来源素材ID列表.
        rules: 按维度分组的规则字典.
        conflict_report: 冲突检测报告.
        created_at: 创建时间.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    distill_mode: DistillMode
    source_material_ids: list[str] = Field(default_factory=list)
    rules: dict[str, list[Rule]] = Field(default_factory=dict)
    conflict_report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("规则集名称不能为空")
        return value.strip()


# ============================ Skill模型 ============================


class SkillRule(BaseModel):
    """Skill中的规则（含层级信息）.

    Attributes:
        id: 唯一标识.
        layer: 所属Skill层级.
        dimension: 分析维度.
        content: 规则内容.
        weight: 权重(0-100).
        source_rule_ids: 来源规则ID列表.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    layer: SkillLayer
    dimension: AnalysisDimension
    content: str
    weight: int = Field(ge=0, le=100, default=50)
    source_rule_ids: list[str] = Field(default_factory=list)

    @field_validator("layer", mode="before")
    @classmethod
    def _migrate_legacy_layer(cls, value: Any) -> Any:
        """将旧版三层名称迁移到当前层级模型."""
        legacy_mapping = {
            "基础层": SkillLayer.BASE.value,
            "角色层": SkillLayer.MIDDLE.value,
            "叙事层": SkillLayer.MIDDLE.value,
        }
        return legacy_mapping.get(value, value)

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("规则内容不能为空")
        return value.strip()


class SkillVersion(BaseModel):
    """Skill版本快照.

    Attributes:
        version: 版本号(如 1.0.0).
        rules_snapshot: 规则快照（按层级分组）.
        changelog: 版本变更说明.
        created_at: 创建时间.
    """

    version: str
    rules_snapshot: dict[str, list[SkillRule]] = Field(default_factory=dict)
    changelog: str = ""
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("版本号不能为空")
        return value.strip()


class Skill(BaseModel):
    """Skill完整模型.

    Attributes:
        id: 唯一标识.
        name: Skill名称.
        description: Skill描述.
        layers: 三层结构规则字典.
        versions: 版本历史.
        status: 当前状态.
        current_version: 当前生效版本号.
        created_at: 创建时间.
        updated_at: 更新时间.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    layers: dict[str, list[SkillRule]] = Field(
        default_factory=lambda: {
            SkillLayer.BASE.value: [],
            SkillLayer.MIDDLE.value: [],
            SkillLayer.DYNAMIC.value: [],
        }
    )
    versions: list[SkillVersion] = Field(default_factory=list)
    status: SkillStatus = SkillStatus.DRAFT
    current_version: str = "0.0.1"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Skill名称不能为空")
        return value.strip()

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_layers(cls, value: Any) -> Any:
        """保留旧版 Skill 存档的可读性，并补齐三层结构."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        source_layers = data.get("layers")
        if not isinstance(source_layers, dict):
            return data

        legacy_mapping = {
            "基础层": SkillLayer.BASE.value,
            "角色层": SkillLayer.MIDDLE.value,
            "叙事层": SkillLayer.MIDDLE.value,
        }
        migrated = {layer.value: [] for layer in SkillLayer}
        for layer_name, rules in source_layers.items():
            target_layer = legacy_mapping.get(layer_name, layer_name)
            if target_layer in migrated:
                migrated[target_layer].extend(rules or [])
        data["layers"] = migrated
        return data


# ============================ 创作项目 ============================


class CreationProject(BaseModel):
    """分步创作项目.

    Attributes:
        id: 唯一标识.
        name: 项目名称.
        skill_id: 使用的Skill ID.
        current_step: 当前创作步骤.
        locked_steps: 已锁定的步骤.
        step_contents: 各步骤内容字典.
        locked_snapshots: 已锁定的步骤快照路径.
        validation_reports: 各步骤校验报告.
        created_at: 创建时间.
        updated_at: 更新时间.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    skill_id: str = ""
    current_step: CreationStep = CreationStep.WORLD_BUILDING
    locked_steps: list[str] = Field(default_factory=list)
    step_contents: dict[str, str] = Field(default_factory=dict)
    locked_snapshots: dict[str, str] = Field(default_factory=dict)
    validation_reports: dict[str, dict[str, Any]] = Field(default_factory=dict)
    dynamic_rules: list[SkillRule] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("项目名称不能为空")
        return value.strip()


# ============================ 反馈样本 ============================


class FeedbackSample(BaseModel):
    """反馈样本（正负样本）.

    Attributes:
        id: 唯一标识.
        project_id: 关联项目ID.
        feedback_type: 反馈类型（正/负）.
        category: 问题分类.
        content: 反馈内容描述.
        related_rule_ids: 关联规则ID列表.
        suggested_weight_delta: 建议权重调整值.
        timestamp: 反馈时间.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    feedback_type: FeedbackType
    category: FeedbackCategory = FeedbackCategory.OTHER
    content: str
    related_rule_ids: list[str] = Field(default_factory=list)
    suggested_weight_delta: int = Field(default=0)
    timestamp: datetime = Field(default_factory=datetime.now)

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("反馈内容不能为空")
        return value.strip()


# ============================ LLM相关配置 ============================


class RetryConfig(BaseModel):
    """重试配置.

    Attributes:
        max_retries: 最大重试次数.
        base_delay: 基础延迟秒数.
        backoff_multiplier: 退避乘数.
    """

    max_retries: int = Field(ge=0, le=10, default=3)
    base_delay: float = Field(ge=0, default=1.0)
    backoff_multiplier: float = Field(ge=1.0, default=3.0)


class ApiConfig(BaseModel):
    """API配置.

    Attributes:
        provider: 提供商名称.
        base_url: API基础URL.
        api_key: API密钥.
        model: 模型名称.
        timeout: 超时秒数.
        retry: 重试配置.
    """

    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    timeout: int = Field(ge=1, default=120)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_retry_config(cls, value: Any) -> Any:
        """兼容配置文件中历史遗留的 max_retries 字段."""
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "max_retries" in data and "retry" not in data:
            data["retry"] = {"max_retries": data.pop("max_retries")}
        return data


class LLMRequest(BaseModel):
    """LLM请求封装.

    Attributes:
        prompt: 提示词内容.
        system_message: 系统消息.
        temperature: 温度参数.
        top_p: 核采样参数.
        max_tokens: 最大生成token数.
    """

    prompt: str
    system_message: str = ""
    temperature: float = Field(ge=0.0, le=2.0, default=0.7)
    top_p: float = Field(ge=0.0, le=1.0, default=0.9)
    max_tokens: int | None = Field(default=None, ge=1)

    @field_validator("prompt")
    @classmethod
    def _validate_prompt(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("提示词不能为空")
        return value.strip()


class LLMResponse(BaseModel):
    """LLM响应封装.

    Attributes:
        success: 是否成功.
        content: 响应内容.
        raw_response: 原始响应字典.
        latency_ms: 响应延迟毫秒.
        token_usage: token用量统计.
        error_message: 错误信息.
    """

    success: bool = True
    content: str = ""
    raw_response: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0
    token_usage: dict[str, int] = Field(default_factory=dict)
    error_message: str = ""
