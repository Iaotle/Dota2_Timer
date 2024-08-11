from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Optional
from utils.terminal import TerminalWindow

class TimestampedHistory:
    def __init__(self, history_window: Optional[TerminalWindow] = None):
        self._lock = threading.Lock()  # Mutex lock for thread safety
        self._history = []  # List to store history events
        self.max_history = 10  # Maximum number of events to store
        self.history_window = history_window
        self.new_game = True


    def writeToWindow(self):
        self.history_window.startWrite()
        events = self.get_history()
        
        for event in events:
            if "New Game" in event:
                self.history_window.writeLine('-')
            self.history_window.write(event)
        self.history_window.finishWrite()
        
        
    def add_event(
        self,
        event_name: str,
        timestamp: timedelta,
        timeouts: Optional[list[timedelta]] = None,
    ):
        with self._lock:
            if event_name == "New Game":
                self.new_game = True
            else:
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
        with self._lock:
            # format to string: "HH:MM:SS EventName (timeout[0] - timeout[1])"
            # hours not shown if 0
            
            # for example: "1:23:45 Roshan (1:32:45 - 1:34:45)"
            # or "23:45 Roshan (32:45 - 34:45)"
            formatted = []
            for event in self._history:
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
                    formatted_event += f"({timeout_start_str}{timeout_end_str})"

                # TODO: limit event length to fit in the history window
                # TODO: limit history to max_history, truncate when reached so we don't overflow ring buffer
                formatted.append(formatted_event)
            return formatted

    def clear_history(self):
        with self._lock:
            self._history.clear()
