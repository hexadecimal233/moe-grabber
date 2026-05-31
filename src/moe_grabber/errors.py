class MoeError(Exception):
    """Base exception for moe-grabber."""

    pass


class IdTakenError(MoeError):
    """The moe ID is already taken — skip to the next one."""

    def __init__(self, moe_id: str):
        self.moe_id = moe_id
        super().__init__(f"ID {moe_id} 已被占用")


class TransientError(MoeError):
    """Transient error (network, captcha, rate limit) — retry current ID."""

    pass
