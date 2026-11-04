from app.services.identity import RawIdentity, resolve_developers


def test_exact_email_match_merges_identities():
    idents = [RawIdentity("John Smith", "john@example.com"), RawIdentity("J. Smith", "john@example.com")]
    resolved = resolve_developers(idents)
    assert len(resolved) == 1
    assert len(resolved[0].raw_identities) == 2


def test_different_email_same_name_is_not_auto_merged():
    idents = [RawIdentity("John Smith", "john@company-a.com"), RawIdentity("John Smith", "john@company-b.com")]
    resolved = resolve_developers(idents)
    # Not silently merged -> two separate developers, each flagged with a suggestion.
    assert len(resolved) == 2
    assert all(d.suggested_merges for d in resolved)


def test_same_name_same_domain_auto_merges():
    idents = [RawIdentity("Jane Doe", "jane@corp.com"), RawIdentity("Jane Doe", "jane.doe@corp.com")]
    resolved = resolve_developers(idents)
    assert len(resolved) == 1


def test_no_email_identity_is_not_merged_with_same_name_email_identity():
    idents = [RawIdentity("Sam Lee", "sam@example.com"), RawIdentity("Sam Lee", None)]

    resolved = resolve_developers(idents)

    assert len(resolved) == 2
    assert {developer.primary_email for developer in resolved} == {"sam@example.com", None}
    assert sorted(len(developer.raw_identities) for developer in resolved) == [1, 1]


def test_developers_with_no_email_are_kept_distinct_by_name():
    idents = [RawIdentity("Alice", None), RawIdentity("Bob", None)]
    resolved = resolve_developers(idents)
    assert len(resolved) == 2
