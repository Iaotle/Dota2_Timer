from __future__ import annotations

import threading
from datetime import timedelta
import time
from typing import Optional
from utils.terminal import TerminalWindow


class TimestampedHistory:
    def __init__(self, history_window: Optional[TerminalWindow] = None, max_history: int = 10):
        self._lock = threading.Lock()  # Mutex lock for thread safety
        self.max_history = max_history  # Maximum number of events to store
        self._history = []
        self.history_window = history_window
        self.new_game = True
        self._games = []
        
        
    def __bool__(self):
        return bool(self._history) # return True if history is not empty
    
    def writeToWindow(self, global_game_timedelta: timedelta):
        events = self.get_history()
        # truncate history based on time, invert history list so we pop in the correct order
        for event in self._history[::-1]:
            if event["timestamp"] > global_game_timedelta and global_game_timedelta.total_seconds() > 90:
                self._history.remove(event)
            else:
                break # stop when we reach an event that is not in the past
        
        self.history_window.startWrite()
        for event in events:
            if "{spacer}" in event:
                self.history_window.writeLine('-')
            else:
                self.history_window.write(event)
        self.history_window.write(f"{self.format_timedelta(global_game_timedelta)} ---")
        self.history_window.finishWrite()
    
    def start_new_game(self):
        if self.new_game:
            return
        self.new_game = True
        self._history.append(
            {"event_name": "{spacer}", "timestamp": timedelta(seconds=0), "timeouts": None}
        )
        self._games.append(self._history)
        self._history = []
        self._history.append(
            {"event_name": "New Game", "timestamp": timedelta(0), "timeouts": None}
        )
        
    def add_event(
        self,
        event_name: str,
        timestamp: timedelta,
        timeouts: Optional[list[timedelta]] = None,
    ):
        self.new_game = False
        self._history.append(
            {"event_name": event_name, "timestamp": timestamp, "timeouts": timeouts}
        )

    def format_timedelta(self, td: timedelta) -> str:
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02}:{seconds:02}"
        else:
            return f"{minutes}:{seconds:02}"

    def get_history(self) -> list[str]:
        # with self._lock:
        # format to string: "HH:MM:SS EventName (timeout[0] - timeout[1])"
        # hours not shown if 0
        
        # for example: "1:23:45 Roshan (1:32:45 - 1:34:45)"
        # or "23:45 Roshan (32:45 - 34:45)"
        formatted = []
        
        
        
        # TODO: limit history to max_history, fix saving with lists
        
        all_events = [event for game in self._games for event in game]
        all_events.extend(self._history)
                
        for event in all_events:
            event_name = event["event_name"]
            timestamp = event["timestamp"]
            timeouts = event["timeouts"]

            # Convert timestamp to HH:MM:SS or MM:SS format
            timestamp_str = str(timestamp) if timestamp >= timedelta(hours=1) else str(timestamp)[2:]
            formatted_event = f"{timestamp_str} {event_name}"
            timeout_start_str = ""
            timeout_end_str = ""
            # Convert timeouts to HH:MM:SS or MM:SS format
            if timeouts:
                timeout_start_str = self.format_timedelta(timeouts[0])
                if (len(timeouts) > 1):
                    timeout_end_str = " - " + self.format_timedelta(timeouts[1])
                formatted_event += f" ({timeout_start_str}{timeout_end_str})"

            # TODO: limit event length to fit in the history window
            # TODO: limit history to max_history, truncate when reached so we don't overflow ring buffer
            formatted.append(formatted_event)
        return formatted

    def clear_history(self):
        # with self._lock:
        self._history.clear()
