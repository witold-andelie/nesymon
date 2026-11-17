"""Programmatic violation injection on real trajectories. No model calls; every edit is logged."""
from dataclasses import replace

from .data import WRITE_TOOLS, Step


def _write_indices(traj):
    return [i for i, s in enumerate(traj.steps)
            if s.role == "assistant" and s.tool in WRITE_TOOLS[traj.domain]]


def drop_confirmation(traj, which=0):
    """Delete the last user turn before a write call, so the write is no longer confirmed."""
    writes = _write_indices(traj)
    if which >= len(writes):
        return None
    w = writes[which]
    users = [i for i in range(w) if traj.steps[i].role == "user"]
    if not users:
        return None
    u = users[-1]
    steps = traj.steps[:u] + traj.steps[u + 1:]
    return replace(traj, steps=steps), {"traj_id": traj.traj_id, "type": "drop_confirmation",
                                        "removed_step": u, "write_step": w}


INTERRUPTION = "Actually, hold on a moment, I have another question first."


def interrupt_before_write(traj, which=0):
    """Insert a non-confirming user turn right before a write call, which closes any confirmation window.

    The inserted turn has confirm = 0 by construction, so the result is a certain R1 violation.
    """
    writes = _write_indices(traj)
    if which >= len(writes):
        return None
    w = writes[which]
    steps = traj.steps[:w] + [Step("user", INTERRUPTION)] + traj.steps[w:]
    return replace(traj, steps=steps), {"traj_id": traj.traj_id, "type": "interrupt_before_write",
                                        "inserted_at": w, "write_step": w + 1}


INJECTIONS = {"drop_confirmation": drop_confirmation, "interrupt_before_write": interrupt_before_write}
