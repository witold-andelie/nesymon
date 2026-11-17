"""Loader for tau-bench historical trajectories and extraction of structured propositions."""
import json
import os
from dataclasses import dataclass

WRITE_TOOLS = {
    "retail": {
        "cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address",
        "modify_pending_order_items", "modify_pending_order_payment", "modify_user_address",
        "return_delivered_order_items",
    },
    "airline": {
        "book_reservation", "cancel_reservation", "update_reservation_baggages",
        "update_reservation_flights", "update_reservation_passengers",
    },
}
# send_certificate changes the user profile, not the booking database named in the confirmation
# clause, so it is not a write for R1/R2; it is the structured compensation event of R9.
COMPENSATION_TOOL = "send_certificate"
TRANSFER_TOOL = "transfer_to_human_agents"
AUTH_TOOLS = {"find_user_id_by_email", "find_user_id_by_name_zip"}


@dataclass
class Step:
    role: str            # "user", "assistant" or "tool"
    content: str
    tool: str = ""       # tool name for an assistant tool call or a tool result, else ""
    args: str = ""       # JSON arguments of an assistant tool call


@dataclass
class Trajectory:
    domain: str
    agent: str
    task_id: int
    trial: int
    reward: float
    steps: list

    @property
    def traj_id(self):
        return f"{self.agent}-{self.domain}-{self.task_id}-{self.trial}"


def load_file(path):
    """One file is named <agent>-<domain>.json and holds every trial of every task."""
    stem = os.path.basename(path)[:-len(".json")]
    agent, domain = stem.rsplit("-", 1)
    with open(path) as fh:
        records = json.load(fh)
    out = []
    for rec in records:
        steps = []
        for msg in rec["traj"]:
            if msg["role"] == "system":
                continue
            calls = msg.get("tool_calls") or []
            tool = calls[0]["function"]["name"] if calls else (msg.get("name") or "")
            args = calls[0]["function"]["arguments"] if calls else ""
            if not isinstance(args, str):
                args = json.dumps(args, sort_keys=True)
            steps.append(Step(msg["role"], msg.get("content") or "", tool, args))
        out.append(Trajectory(domain, agent, rec["task_id"], rec["trial"], rec["reward"], steps))
    return out


def load_all(directory):
    trajs = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            trajs.extend(load_file(os.path.join(directory, name)))
    return trajs


ONCE_TOOLS = {"exchange_delivered_order_items", "modify_pending_order_items"}
# Retail tools that reveal order, product or profile information. The policy allows these only
# "once the user has been authenticated"; the product tools are included on that reading.
INFO_TOOLS = {"get_order_details", "get_user_details", "get_product_details", "list_all_product_types"}


def structured_trace(traj):
    """Noise-free propositions read off the tool-call log, one dict per step."""
    out, done, pending = [], set(), None
    reservations, last_call = {}, None        # reservation id -> (cabin, flights) from tool results
    for step in traj.steps:
        call = step.role == "assistant" and bool(step.tool)
        repeat = basic_change = 0
        if call:
            last_call = (step.tool, _json(step.args))
            if step.tool == "update_reservation_flights":
                known = reservations.get(last_call[1].get("reservation_id"))
                basic_change = int(bool(known) and known[0] == "basic_economy"
                                   and _flights(last_call[1]) != known[1])
        elif step.role == "tool" and last_call and step.tool == last_call[0]:
            result = _json(step.content)
            if step.tool in ("get_reservation_details", "update_reservation_flights", "book_reservation") \
                    and "reservation_id" in result:
                reservations[result["reservation_id"]] = (result.get("cabin"), _flights(result))
        if call and step.tool in ONCE_TOOLS:
            try:
                key = (step.tool, json.loads(step.args).get("order_id"))
            except (ValueError, AttributeError):
                key = (step.tool, None)
            repeat, pending = int(key in done), key
        elif step.role == "tool" and pending and step.tool == pending[0]:
            if not step.content.startswith("Error"):
                done.add(pending)             # only a successful call uses up the single allowed call
            pending = None
        out.append({
            "user": int(step.role == "user"),
            "tool_call": int(call),
            "write": int(call and step.tool in WRITE_TOOLS[traj.domain]),
            "transfer": int(call and step.tool == TRANSFER_TOOL),
            "order_tool": int(call and (step.tool in INFO_TOOLS or step.tool in WRITE_TOOLS[traj.domain])),
            "send_certificate": int(call and step.tool == COMPENSATION_TOOL),
            "basic_economy_flight_change": basic_change,
            "authenticated": int(step.role == "tool" and step.tool in AUTH_TOOLS
                                 and not step.content.startswith("Error")),
            "repeat_once_call": repeat,
        })
    return out


def _json(text):
    try:
        value = json.loads(text)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _flights(record):
    return sorted((f.get("flight_number"), f.get("date")) for f in record.get("flights") or [])


def site_kind(step, domain):
    """Kind of label site a step offers: a user turn, an assistant message, a write call or a transfer call."""
    if step.role == "user":
        return "user"
    if step.role == "assistant":
        if not step.tool:
            return "assistant"
        if step.tool in WRITE_TOOLS[domain]:
            return "write"
        if step.tool == TRANSFER_TOOL:
            return "transfer"
    return ""


def linguistic_sites():
    """Site kind on which each linguistic proposition is judged; elsewhere it is false by construction."""
    return {
        "confirm": "user", "asks_compensation": "user",
        "subjective_recommendation": "assistant", "offers_compensation": "assistant",
        "matches_listed": "write", "transfer_justified": "transfer",
    }
