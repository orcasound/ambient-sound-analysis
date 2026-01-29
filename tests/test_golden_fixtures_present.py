import os

import pytest


def test_golden_fixtures_are_present():
    """
    Require committed golden fixtures to be present.

    This is a fast, dependency-light check that fails with a clear message if
    `tests/golden/*.pkl` fixtures were deleted or not included in the checkout.
    """
    this_dir = os.path.dirname(__file__)
    golden_dir = os.path.join(this_dir, "golden")

    stems = ["live000", "live001", "live002"]
    config_names = ["60s_100hz", "60s_3oct"]
    kinds = ["psd", "bb"]

    missing = []
    for stem in stems:
        for config_name in config_names:
            for kind in kinds:
                path = os.path.join(golden_dir, f"{stem}__{config_name}__{kind}.pkl")
                if not os.path.exists(path):
                    missing.append(os.path.relpath(path))

    if missing:
        pytest.fail(
            "Missing golden fixtures:\n"
            + "\n".join(f"- {p}" for p in missing)
            + "\n\nRegenerate with: python -m tests.generate_test_data"
        )

