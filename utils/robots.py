import urllib.robotparser
from dataclasses import dataclass
from typing import Optional

@dataclass
class RobotsPolicy:
    allowed: bool
    reason: str

class RobotsChecker:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._rp: Optional[urllib.robotparser.RobotFileParser] = None

    def load(self, robots_txt: str, robots_url: str) -> None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.parse(robots_txt.splitlines())
        self._rp = rp

    def can_fetch(self, url: str) -> RobotsPolicy:
        if not self._rp:
            return RobotsPolicy(False, "robots.txt nie je načítaný – bezpečne blokujem requesty.")
        ok = self._rp.can_fetch(self.user_agent, url)
        return RobotsPolicy(ok, "Povolené robots.txt" if ok else "Zakázané robots.txt")
