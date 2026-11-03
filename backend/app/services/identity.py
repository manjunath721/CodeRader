"""
Developer identity normalization.

Only "exact" rules ever auto-merge (same email, or same normalized name +
shared email domain). Anything looser is returned as a *suggestion* for a
human to confirm — this module never silently merges ambiguous identities
(master spec §6).
"""
import re
from dataclasses import dataclass


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", name.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower()


@dataclass
class RawIdentity:
    name: str
    email: str | None


@dataclass
class ResolvedDeveloper:
    display_name: str
    primary_email: str | None
    normalized_key: str
    raw_identities: list[RawIdentity]
    suggested_merges: list[RawIdentity]  # identities that *might* be the same person but weren't auto-merged


def resolve_developers(raw_identities: list[RawIdentity]) -> list[ResolvedDeveloper]:
    """
    Groups raw (name, email) pairs from commit authorship into developers
    using exact-match rules only, and separately flags same-normalized-name
    identities with a *different* email domain as suggestions rather than
    merging them.
    """
    by_email: dict[str, list[RawIdentity]] = {}
    no_email: list[RawIdentity] = []
    for ident in raw_identities:
        if ident.email:
            by_email.setdefault(ident.email.lower(), []).append(ident)
        else:
            no_email.append(ident)

    # First pass: exact email groups become developers.
    resolved: list[ResolvedDeveloper] = []
    email_to_developer: dict[str, ResolvedDeveloper] = {}
    for email, idents in by_email.items():
        display_name = max({i.name for i in idents}, key=len)  # prefer the longest/most complete name
        dev = ResolvedDeveloper(
            display_name=display_name,
            primary_email=email,
            normalized_key=normalize_name(display_name),
            raw_identities=idents,
            suggested_merges=[],
        )
        resolved.append(dev)
        email_to_developer[email] = dev

    # Second pass: exact normalized-name + shared email domain -> auto-merge into
    # the existing developer with that name if domains match.
    name_to_developers: dict[str, list[ResolvedDeveloper]] = {}
    for dev in resolved:
        name_to_developers.setdefault(dev.normalized_key, []).append(dev)

    merged: list[ResolvedDeveloper] = []
    seen_keys: set[str] = set()
    for key, devs in name_to_developers.items():
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if len(devs) == 1:
            merged.append(devs[0])
            continue
        domains = {email_domain(d.primary_email) for d in devs}
        if len(domains) == 1 and None not in domains:
            # Same normalized name, same email domain -> exact-rule auto-merge.
            primary = max(devs, key=lambda d: len(d.raw_identities))
            all_idents = [i for d in devs for i in d.raw_identities]
            merged.append(
                ResolvedDeveloper(
                    display_name=primary.display_name,
                    primary_email=primary.primary_email,
                    normalized_key=key,
                    raw_identities=all_idents,
                    suggested_merges=[],
                )
            )
        else:
            # Same name, different domains: NOT auto-merged. Kept as separate
            # developers, but flagged so the ingestion result can surface a
            # "did you mean to merge these?" suggestion to the user.
            for d in devs:
                d.suggested_merges = [i for other in devs if other is not d for i in other.raw_identities]
                merged.append(d)

    # No-email identities become their own developer, one per distinct normalized name,
    # unless that name already matches a resolved developer's normalized_key.
    key_index = {d.normalized_key: d for d in merged}
    for ident in no_email:
        key = normalize_name(ident.name)
        if key in key_index:
            key_index[key].raw_identities.append(ident)
        else:
            dev = ResolvedDeveloper(
                display_name=ident.name,
                primary_email=None,
                normalized_key=key,
                raw_identities=[ident],
                suggested_merges=[],
            )
            merged.append(dev)
            key_index[key] = dev

    return merged
