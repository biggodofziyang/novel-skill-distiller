"""输入校验工具.

提供文件类型校验、参数范围校验、枚举值校验等功能.
"""

from pathlib import Path

from core.constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    MAX_UPLOAD_SIZE_MB,
    AnalysisDimension,
    CreationStep,
    DistillMode,
    FeedbackCategory,
    FeedbackType,
    SkillLayer,
    SkillStatus,
)


class ValidationError(ValueError):
    """校验错误异常类."""

    pass


def validate_file_extension(filename: str | Path) -> str:
    """校验文件扩展名是否在允许列表中.

    Args:
        filename: 文件名或路径.

    Returns:
        标准化后的文件扩展名（小写，含点号）.

    Raises:
        ValidationError: 当扩展名不在允许列表中时.
    """
    path = Path(filename)
    ext = path.suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise ValidationError(
            f"不支持的文件类型: '{ext}'。允许的类型: {allowed}"
        )
    return ext


def validate_file_size(size_bytes: int, max_mb: int = MAX_UPLOAD_SIZE_MB) -> int:
    """校验文件大小是否在限制范围内.

    Args:
        size_bytes: 文件大小（字节）.
        max_mb: 最大允许大小（MB）.

    Returns:
        校验通过的文件大小（字节）.

    Raises:
        ValidationError: 当文件大小超过限制时.
    """
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationError(
            f"文件大小超过限制: {size_bytes / 1024 / 1024:.2f}MB > {max_mb}MB"
        )
    if size_bytes < 0:
        raise ValidationError("文件大小不能为负数")
    return size_bytes


def validate_dimension(dimension: str) -> AnalysisDimension:
    """校验并转换分析维度字符串为枚举值.

    Args:
        dimension: 维度字符串.

    Returns:
        对应的AnalysisDimension枚举值.

    Raises:
        ValidationError: 当维度无效时.
    """
    try:
        return AnalysisDimension(dimension)
    except ValueError:
        valid = ", ".join([d.value for d in AnalysisDimension])
        raise ValidationError(f"无效的分析维度: '{dimension}'。有效值: {valid}")


def validate_distill_mode(mode: str) -> DistillMode:
    """校验并转换蒸馏模式字符串为枚举值.

    Args:
        mode: 模式字符串.

    Returns:
        对应的DistillMode枚举值.

    Raises:
        ValidationError: 当模式无效时.
    """
    try:
        return DistillMode(mode)
    except ValueError:
        valid = ", ".join([m.value for m in DistillMode])
        raise ValidationError(f"无效的蒸馏模式: '{mode}'。有效值: {valid}")


def validate_skill_layer(layer: str) -> SkillLayer:
    """校验并转换Skill层级字符串为枚举值.

    Args:
        layer: 层级字符串.

    Returns:
        对应的SkillLayer枚举值.

    Raises:
        ValidationError: 当层级无效时.
    """
    try:
        return SkillLayer(layer)
    except ValueError:
        valid = ", ".join([l.value for l in SkillLayer])
        raise ValidationError(f"无效的Skill层级: '{layer}'。有效值: {valid}")


def validate_skill_status(status: str) -> SkillStatus:
    """校验并转换Skill状态字符串为枚举值.

    Args:
        status: 状态字符串.

    Returns:
        对应的SkillStatus枚举值.

    Raises:
        ValidationError: 当状态无效时.
    """
    try:
        return SkillStatus(status)
    except ValueError:
        valid = ", ".join([s.value for s in SkillStatus])
        raise ValidationError(f"无效的Skill状态: '{status}'。有效值: {valid}")


def validate_creation_step(step: str) -> CreationStep:
    """校验并转换创作步骤字符串为枚举值.

    Args:
        step: 步骤字符串.

    Returns:
        对应的CreationStep枚举值.

    Raises:
        ValidationError: 当步骤无效时.
    """
    try:
        return CreationStep(step)
    except ValueError:
        valid = ", ".join([s.value for s in CreationStep])
        raise ValidationError(f"无效的创作步骤: '{step}'。有效值: {valid}")


def validate_feedback_type(feedback_type: str) -> FeedbackType:
    """校验并转换反馈类型字符串为枚举值.

    Args:
        feedback_type: 反馈类型字符串.

    Returns:
        对应的FeedbackType枚举值.

    Raises:
        ValidationError: 当类型无效时.
    """
    try:
        return FeedbackType(feedback_type)
    except ValueError:
        valid = ", ".join([t.value for t in FeedbackType])
        raise ValidationError(f"无效的反馈类型: '{feedback_type}'。有效值: {valid}")


def validate_feedback_category(category: str) -> FeedbackCategory:
    """校验并转换反馈分类字符串为枚举值.

    Args:
        category: 分类字符串.

    Returns:
        对应的FeedbackCategory枚举值.

    Raises:
        ValidationError: 当分类无效时.
    """
    try:
        return FeedbackCategory(category)
    except ValueError:
        valid = ", ".join([c.value for c in FeedbackCategory])
        raise ValidationError(f"无效的反馈分类: '{category}'。有效值: {valid}")


def validate_weight(weight: int | float, min_val: int = 0, max_val: int = 100) -> int:
    """校验并归一化权重值.

    Args:
        weight: 输入权重值.
        min_val: 最小允许值.
        max_val: 最大允许值.

    Returns:
        限制在范围内的整数值.
    """
    try:
        w = int(weight)
    except (TypeError, ValueError):
        raise ValidationError(f"权重必须是数值: {weight}")
    if w < min_val:
        return min_val
    if w > max_val:
        return max_val
    return w


def validate_non_empty_string(value: str, field_name: str = "字段") -> str:
    """校验字符串非空.

    Args:
        value: 待校验字符串.
        field_name: 字段名称（用于错误提示）.

    Returns:
        去除首尾空白后的字符串.

    Raises:
        ValidationError: 当字符串为空时.
    """
    if not value or not str(value).strip():
        raise ValidationError(f"{field_name}不能为空")
    return str(value).strip()
