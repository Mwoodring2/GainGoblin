from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoblinAnimationClip:
    name: str
    mood: str
    duration_ms: int
    bounce_strength: int = 0
    coin_jiggle: bool = False
    blink: bool = True
    sweat: bool = False
    sparkle: bool = False
    eye_shift: int = 0
    foot_tap: bool = False


ANIMATION_CLIPS: dict[str, GoblinAnimationClip] = {
    "idle": GoblinAnimationClip("idle", "idle", 1000, blink=True),
    "happy": GoblinAnimationClip("happy", "happy", 1000, bounce_strength=2, sparkle=True),
    "greedy": GoblinAnimationClip("greedy", "greedy", 1200, coin_jiggle=True, sparkle=True),
    "worried": GoblinAnimationClip("worried", "worried", 1100, sweat=True),
    "thinking": GoblinAnimationClip("thinking", "thinking", 1200, bounce_strength=1),
    "blink": GoblinAnimationClip("blink", "idle", 400, blink=True),
    "look_left": GoblinAnimationClip("look_left", "idle", 700, eye_shift=-3),
    "look_right": GoblinAnimationClip("look_right", "idle", 700, eye_shift=3),
    "coin_jiggle": GoblinAnimationClip("coin_jiggle", "greedy", 900, coin_jiggle=True),
    "foot_tap": GoblinAnimationClip("foot_tap", "thinking", 900, bounce_strength=1, foot_tap=True),
    "shoulder_bounce": GoblinAnimationClip("shoulder_bounce", "happy", 800, bounce_strength=3),
    "shoulder_bob": GoblinAnimationClip("shoulder_bob", "happy", 800, bounce_strength=3),
    "happy_bounce": GoblinAnimationClip("happy_bounce", "happy", 1100, bounce_strength=5, sparkle=True),
    "greedy_sparkle": GoblinAnimationClip("greedy_sparkle", "greedy", 1200, coin_jiggle=True, sparkle=True),
    "greedy_coin_jiggle": GoblinAnimationClip(
        "greedy_coin_jiggle", "greedy", 1300, bounce_strength=2, coin_jiggle=True, sparkle=True
    ),
    "worried_sweat": GoblinAnimationClip("worried_sweat", "worried", 1200, sweat=True),
    "thinking_tap": GoblinAnimationClip("thinking_tap", "thinking", 1200, bounce_strength=1, foot_tap=True),
    "import_success": GoblinAnimationClip(
        "import_success", "greedy", 1400, bounce_strength=4, coin_jiggle=True, sparkle=True
    ),
    "import_failed": GoblinAnimationClip("import_failed", "worried", 1400, sweat=True),
    "holding_added": GoblinAnimationClip("holding_added", "happy", 1100, bounce_strength=5, sparkle=True),
    "profit_up": GoblinAnimationClip("profit_up", "happy", 1200, bounce_strength=4, sparkle=True),
    "profit_down": GoblinAnimationClip("profit_down", "worried", 1200, sweat=True),
    "missing_targets": GoblinAnimationClip("missing_targets", "thinking", 1200, bounce_strength=1, foot_tap=True),
    "delete": GoblinAnimationClip("delete", "thinking", 1100, bounce_strength=1, foot_tap=True),
    "celebrate": GoblinAnimationClip(
        "celebrate", "greedy", 1500, bounce_strength=5, coin_jiggle=True, sparkle=True
    ),
}


EVENT_TO_STATE = {
    "idle": "idle",
    "blink": "blink",
    "look_left": "look_left",
    "look_right": "look_right",
    "foot_tap": "foot_tap",
    "coin_jiggle": "coin_jiggle",
    "shoulder_bob": "shoulder_bob",
    "shoulder_bounce": "shoulder_bob",
    "happy_bounce": "happy_bounce",
    "greedy_sparkle": "greedy_sparkle",
    "greedy_coin_jiggle": "greedy_sparkle",
    "worried_sweat": "worried_sweat",
    "thinking_tap": "thinking_tap",
    "holding_added": "holding_added",
    "import_success": "import_success",
    "import_failed": "import_failed",
    "delete": "delete",
    "profit_up": "profit_up",
    "profit_down": "profit_down",
    "profit_positive": "profit_up",
    "profit_negative": "profit_down",
    "missing_targets": "thinking_tap",
    "celebrate": "celebrate",
}


# Backward-compatible alias for older tests/imports.
EVENT_TO_CLIP = EVENT_TO_STATE
