"""The ``roblox-studio/1`` scenario vocabulary (SIP-0117 R5.8, #3040): what the Studio harness
executes, read from ``scenario_vocabulary.json`` beside this module.

**Paths** are instance paths, joined by ``.``:
- they start at a service (``Workspace``, ``ReplicatedStorage``, …), or at ``@player``, the one
  player of a play session. That is ``LocalPlayer`` on the client and the session's only player
  on the server, so a scenario never names a person's account;
- a name that holds a dot can't be addressed.

**Observations:**
- ``property`` and ``attribute`` read a value. Numbers, text and booleans are read as they are,
  and anything else as its text (``Enum.Material.Plastic``, an instance's path);
- ``gui_state`` reads ``visible`` (a GUI object shown on screen: it and every ancestor visible,
  and its screen enabled; of a screen itself, a ``ScreenGui``, that it is enabled, #3176) or
  ``text``, which a screen has none of;
- ``value`` reads a ``ValueBase``'s ``Value``.

An instance that isn't there observes ``absent``.

**Actions:**
- ``click_gui`` clicks a visible GUI object by path, with the mouse;
- ``hold_key`` holds a key (a ``KeyCode`` name) for some seconds;
- ``move_to`` walks the character to a point and waits until it is within a stud of it;
- ``wait_until`` waits for an observation to meet an expectation. In setup, one that times out
  means the scenario's world wasn't established. In steps, the scenario goes on, and its
  assertions read what happened.
"""

from __future__ import annotations

import json
from importlib import resources

from squadops.remote_execution.scenario import ScenarioVocabulary

#: The file the vocabulary is read from. A skill ships the same file as its
#: ``scenario_vocabulary.json`` (SIP-0116 §17g), held equal to this one by a test.
VOCABULARY_FILE = "scenario_vocabulary.json"

VOCABULARY = ScenarioVocabulary.from_document(
    json.loads(resources.files(__package__).joinpath(VOCABULARY_FILE).read_text(encoding="utf-8"))
)
#: How long a ``move_to`` may end from its point and still have arrived, in studs (S1 measured
#: navigation to within 0.7).
ARRIVED_STUDS = 1.0
