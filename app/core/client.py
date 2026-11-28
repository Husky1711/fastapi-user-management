"""Who is calling: the client's address and user agent, as the app should record them."""

from dataclasses import dataclass

USER_AGENT_MAX_LENGTH = 256


@dataclass(frozen=True, slots=True)
class ClientInfo:
    ip: str | None
    user_agent: str | None

    @classmethod
    def unknown(cls) -> "ClientInfo":
        return cls(ip=None, user_agent=None)
