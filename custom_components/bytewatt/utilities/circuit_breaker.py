"""Circuit breaker pattern implementation for ByteWatt integration."""
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any

from .connection_stats import ConnectionStatistics

_LOGGER = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"      # Error threshold reached, no requests allowed
    HALF_OPEN = "half_open"  # Testing if service is back online


class CircuitBreaker:
    """Implements circuit breaker pattern for API calls."""
    
    def __init__(
        self, 
        failure_threshold: float = 0.5,
        recovery_timeout: int = 300,
        half_open_timeout: int = 60
    ):
        """Initialize circuit breaker with configurable thresholds."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_threshold = failure_threshold  # 50% failure rate by default
        self.recovery_timeout = recovery_timeout  # 5 minutes by default
        self.half_open_timeout = half_open_timeout  # 1 minute by default
        self.last_state_change = datetime.now()
        self.stats = ConnectionStatistics()
    
    def record_success(self, response_time: float):
        """Record a successful API call."""
        self.stats.record_success(response_time)
        
        # If we're in half-open state and got a success, close the circuit
        if self.state == CircuitBreakerState.HALF_OPEN:
            _LOGGER.info("Circuit breaker transitioning from HALF_OPEN to CLOSED after successful response")
            self.state = CircuitBreakerState.CLOSED
            self.last_state_change = datetime.now()
    
    def record_failure(self, error_type: str, error_message: str):
        """Record a failed API call."""
        self.stats.record_failure(error_type, error_message)
        
        # If success rate drops below threshold, open the circuit
        if (self.state == CircuitBreakerState.CLOSED and 
            len(self.stats.success_history) >= 3 and  # Need at least 3 data points
            self.stats.success_rate < self.failure_threshold):
            
            _LOGGER.warning(
                "Circuit breaker transitioning from CLOSED to OPEN: "
                f"success rate ({self.stats.success_rate:.2%}) below threshold ({self.failure_threshold:.2%})"
            )
            self.state = CircuitBreakerState.OPEN
            self.last_state_change = datetime.now()
        
        # If we're in half-open state and got a failure, back to open
        elif self.state == CircuitBreakerState.HALF_OPEN:
            _LOGGER.warning("Circuit breaker transitioning from HALF_OPEN to OPEN after failed response")
            self.state = CircuitBreakerState.OPEN
            self.last_state_change = datetime.now()
    
    def check_state_transition(self):
        """Check if circuit breaker state should transition based on timeouts."""
        now = datetime.now()
        
        # If circuit is open and recovery timeout has passed, try half-open
        if (self.state == CircuitBreakerState.OPEN and 
            (now - self.last_state_change).total_seconds() > self.recovery_timeout):
            
            _LOGGER.info(
                f"Circuit breaker transitioning from OPEN to HALF_OPEN after {self.recovery_timeout}s timeout"
            )
            self.state = CircuitBreakerState.HALF_OPEN
            self.last_state_change = now
    
    def can_execute(self) -> bool:
        """Check if the API call should be allowed based on circuit state."""
        self.check_state_transition()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.HALF_OPEN:
            # In half-open state, allow one request to test the service
            return True
        else:  # OPEN
            return False
    
    def reset(self) -> None:
        """Force the circuit back to CLOSED and clear the failure history.

        Called by the recovery flow after the operator (or auto-reconnect) has
        re-established the connection. Without this, a recovered-but-still-OPEN
        circuit would keep refusing requests until the failure window aged out
        naturally on its own.
        """
        previous_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.last_state_change = datetime.now()
        self.stats.reset()
        if previous_state != CircuitBreakerState.CLOSED:
            _LOGGER.info("Circuit breaker reset from %s to CLOSED", previous_state.value)

    def get_status_report(self) -> Dict[str, Any]:
        """Generate a status report of circuit breaker health."""
        state_duration = (datetime.now() - self.last_state_change).total_seconds()
        
        report = {
            "state": self.state.value,
            "state_duration": f"{state_duration:.0f}s",
            "failure_threshold": f"{self.failure_threshold:.2%}",
            "recovery_timeout": f"{self.recovery_timeout}s",
        }
        
        # Add connection statistics
        report.update(self.stats.get_status_report())
        
        return report