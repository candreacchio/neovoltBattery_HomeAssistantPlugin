"""Connection statistics tracking for ByteWatt integration."""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)


class ConnectionStatistics:
    """Track connection health statistics for circuit breaker pattern."""
    
    def __init__(self, window_size: int = 10):
        """Initialize connection statistics."""
        self.window_size = window_size
        self.success_history: List[bool] = []
        self.response_times: List[float] = []
        self.error_types: Dict[str, int] = {}
        self.last_success_time: Optional[datetime] = None
        self.last_error_time: Optional[datetime] = None
        self.last_error_message: Optional[str] = None

    def reset(self) -> None:
        """Clear all tracked history. Called when recovering from a known-good state."""
        self.success_history.clear()
        self.response_times.clear()
        self.error_types.clear()
        # Preserve last_*_time / last_error_message so operators can still see
        # the most recent event after a reset.
    
    def record_success(self, response_time: float):
        """Record a successful API call."""
        self.success_history.append(True)
        self.response_times.append(response_time)
        self.last_success_time = datetime.now()
        
        # Trim history to window size
        if len(self.success_history) > self.window_size:
            self.success_history = self.success_history[-self.window_size:]
            self.response_times = self.response_times[-self.window_size:]
    
    def record_failure(self, error_type: str, error_message: str):
        """Record a failed API call."""
        self.success_history.append(False)
        self.last_error_time = datetime.now()
        self.last_error_message = error_message
        
        # Record error type
        if error_type in self.error_types:
            self.error_types[error_type] += 1
        else:
            self.error_types[error_type] = 1
        
        # Trim history to window size
        if len(self.success_history) > self.window_size:
            self.success_history = self.success_history[-self.window_size:]
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate over the window."""
        if not self.success_history:
            return 1.0  # Default to 100% if no history
        
        return sum(1 for x in self.success_history if x) / len(self.success_history)
    
    @property
    def avg_response_time(self) -> Optional[float]:
        """Calculate average response time over the window."""
        if not self.response_times:
            return None
        
        return sum(self.response_times) / len(self.response_times)
    
    @property
    def most_common_error(self) -> Optional[Tuple[str, int]]:
        """Get the most common error type."""
        if not self.error_types:
            return None
        
        return max(self.error_types.items(), key=lambda x: x[1])
    
    def get_status_report(self) -> Dict[str, Any]:
        """Generate a status report of connection health."""
        return {
            "success_rate": f"{self.success_rate:.2%}",
            "avg_response_time": f"{self.avg_response_time:.2f}s" if self.avg_response_time else "N/A",
            "most_common_error": self.most_common_error[0] if self.most_common_error else "None",
            "error_count": sum(self.error_types.values()),
            "last_success": self.last_success_time.isoformat() if self.last_success_time else "Never",
            "last_error": self.last_error_time.isoformat() if self.last_error_time else "Never",
            "last_error_message": self.last_error_message or "None"
        }