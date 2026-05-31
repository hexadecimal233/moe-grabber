import json
from typing import List

from pydantic import BaseModel, Field


class MoeConfig(BaseModel):
    """Type-safe configuration model for moe-grabber.

    Loaded from config.json. All fields are required.
    moe_numbers must contain at least one ID.
    """

    moe_numbers: List[str] = Field(
        min_length=1,
        description="萌备号码列表，按优先级排序",
    )
    scheduled_time: str = Field(
        description="抢号开始时间，ISO 8601 格式，如 2026-05-30T10:00:00，"
        "支持时区后缀如 +08:00",
    )
    name: str = Field(description="主页名")
    domain: str = Field(description="主页域名")
    homepage: str = Field(description="主页链接")
    description: str = Field(description="主页简介")
    owner: str = Field(description="站长名称")
    email_mail: str = Field(description="Proton Mail 邮箱地址")
    email_pass: str = Field(description="邮箱密码")

    @classmethod
    def from_json(cls, path: str = "config.json") -> "MoeConfig":
        """Load and validate config from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
