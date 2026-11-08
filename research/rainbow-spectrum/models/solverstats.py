"""Solver statistics, where missing means missing.

z3 names its SAT counters "sat conflicts", "sat decisions", "sat propagations
2ary", and so on. A filter written against the bare names captures nothing, and
defaulting the lookup to 0 turns "not measured" into "measured zero". That is
not a hypothetical: this repository briefly published the claim that z3 did no
search at all -- "conflicts = 0 in every single cell" -- while the solver was in
fact performing tens of thousands of conflicts per instance. The wrong key was
harmless; the silent default was not.

The rule enforced here:

    an absent statistic is None, never 0, and any claim that rests on one must
    either check for None or use require(), which raises.
"""

DEFAULT_SUBSTRINGS = ("conflict", "decision", "propagation", "restart", "rlimit")


def collect(statistics, substrings=DEFAULT_SUBSTRINGS):
    """Every reported counter whose name contains one of `substrings`.

    Keys are kept verbatim, so "sat conflicts" stays "sat conflicts" and nothing
    is renamed into a shape a later lookup might silently miss.
    """
    out = {}
    try:
        for key in statistics.keys():
            if any(s in key for s in substrings):
                out[key] = statistics.get_key_value(key)
    except Exception:
        return {}
    return out


def get(stats, name):
    """Counter `name` under any known alias, or None if it was not reported.

    Counters that z3 splits across several keys -- propagations into "2ary" and
    "nary", for instance -- are summed, since the split is an implementation
    detail rather than a distinction worth reporting.
    """
    if not stats:
        return None
    for key in (name, f"sat {name}", f"{name}s", f"sat {name}s"):
        if key in stats:
            return stats[key]
    hits = [value for key, value in stats.items() if name in key]
    if not hits:
        return None
    return sum(hits) if len(hits) > 1 else hits[0]


def require(stats, name):
    """Like get(), but refuses to let a claim rest on an unreported counter."""
    value = get(stats, name)
    if value is None:
        raise KeyError(
            f"solver statistic {name!r} was not reported; any conclusion that "
            "depends on it cannot be drawn, and must not be defaulted to zero")
    return value


def show(stats, name):
    """Display form: the value, or an explicit 'n/a' -- never a fabricated 0."""
    value = get(stats, name)
    return "n/a" if value is None else value
