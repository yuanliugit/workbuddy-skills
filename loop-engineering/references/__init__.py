"""
loop-engineering package entry
Unified exports: StateManager, HandoffManager, RoundValidator

Usage:
    from loop_engineering import StateManager, HandoffManager, RoundValidator
    from loop_engineering import quick_init, quick_load, quick_handoff
"""

from .state_manager import StateManager, State, StateCorruptedError, quick_init, quick_load
from .handoff_manager import HandoffManager, quick_handoff
from .validator import RoundValidator, ValidationResult

__all__ = [
    "StateManager",
    "State",
    "StateCorruptedError",
    "HandoffManager",
    "RoundValidator",
    "ValidationResult",
    "quick_init",
    "quick_load",
    "quick_handoff",
]
