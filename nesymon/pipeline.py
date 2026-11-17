"""Glue between real trajectories, the labeler cache, human labels and the monitor's input format."""
import csv

from .data import linguistic_sites, site_kind, structured_trace
from .labeler import build_prompt, yes_no_probability

SITES = linguistic_sites()


def load_prop_defs(path="props/definitions.yaml"):
    import yaml
    with open(path) as fh:
        return {d["name"]: d for d in yaml.safe_load(fh)}


def render_history(steps):
    lines = []
    for i, s in enumerate(steps, 1):
        if s.role == "assistant" and s.tool:
            lines.append(f"[{i}] assistant calls tool {s.tool}({s.args})")
        elif s.role == "tool":
            lines.append(f"[{i}] tool {s.tool} returns: {s.content[:300]}")
        else:
            lines.append(f"[{i}] {s.role}: {s.content.strip()}")
    return "\n".join(lines)


def label_sites(traj, props):
    """(step, prop) pairs that need a judgement: linguistic props on steps of their own site kind."""
    return [(t, a) for t, s in enumerate(traj.steps) for a in props
            if a in SITES and SITES[a] == site_kind(s, traj.domain)]


def label_trajectory(traj, prop_defs, backend, cache):
    """Fill the cache for every label site of one trajectory. Returns the number of new model calls."""
    new = 0
    for t, a in label_sites(traj, prop_defs):
        if cache.get(traj.traj_id, t, a) is not None:
            continue
        d = prop_defs[a]
        prefix, suffix = build_prompt(render_history(traj.steps[:t + 1]), t + 1, d["definition"],
                                      d["positive"][0], d["negative"][0])
        cache.put(traj.traj_id, t, a, yes_no_probability(*backend.answer_logits(prefix, suffix)))
        new += 1
    return new


def load_labels(path):
    """labels.csv -> {(traj_id, step, prop): 0/1}; rows with an empty value are skipped."""
    out = {}
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            if row["value"] != "":
                out[(row["traj_id"], int(row["step"]), row["prop"])] = int(row["value"])
    return out


def assemble(traj, dfa, cache, labels=None):
    """Monitor input for one rule: a list of (probs, truth) per step.

    Structured props come from the tool log. Linguistic props off their site are None/0
    (false by construction); on their site they come from the cache and the human labels.
    Without labels the truth of linguistic props is None, which is enough for label-free statistics.
    """
    sites = set(label_sites(traj, dfa.props))
    out, trace = [], structured_trace(traj)
    for t, struct in enumerate(trace):
        probs, truth = {}, {}
        for a in dfa.props:
            if a in dfa.structured:
                probs[a], truth[a] = float(struct[a]), struct[a]
            elif (t, a) in sites:
                probs[a] = cache.get(traj.traj_id, t, a)
                truth[a] = labels[(traj.traj_id, t, a)] if labels is not None else None
                if probs[a] is None:
                    raise KeyError(f"no cached probability for {(traj.traj_id, t, a)}")
            else:
                probs[a], truth[a] = None, 0
        out.append((probs, truth))
    return out
