
import datetime
from enum import Enum

class Mode(Enum):
    NORMAL = 0
    TURBO = 1
    DEBUG = 2
    
class Respawn_Duration:
    def __init__(self, mode: Mode):
        self.mode = mode
    def next(self):
        self.mode = Mode((self.mode.value + 1) % len(Mode))
    def currentMode(self):
        return self.mode
    def setMode(self, mode: Mode):
        self.current = mode
    def tormentor_cooldown(self):
        return 60 * 10 if self.mode == Mode.NORMAL else 60 * 5 if self.mode == Mode.TURBO else 20
    def roshan_cooldown(self):
        # 3 min + 8 min
        return 3 * 60 + (60 * 8 if self.mode == Mode.NORMAL else 60 * 4 if self.mode == Mode.TURBO else 20)
    def rune_cooldown(self):
        return 1.5 * 60 - 15 if self.mode == Mode.NORMAL else 1.5 * 60 - 15 if self.mode == Mode.TURBO else 20
    def tormentor_spawn_at(self):
        return datetime.timedelta(minutes=20) if self.mode == Mode.NORMAL else datetime.timedelta(minutes=10) if self.mode == Mode.TURBO else datetime.timedelta(seconds=0)