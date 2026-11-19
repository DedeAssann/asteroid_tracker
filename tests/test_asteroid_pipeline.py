import pytest

from asteroid_tracker.jpl_cad import validate_payload
from asteroid_tracker.pipeline import payload_to_dataframe


SAMPLE = {
    "signature": {
        "source": "NASA/JPL SBDB Close Approach Data API",
        "version": "1.5",
    },
    "count": 1,
    "fields": [
        "des",
        "orbit_id",
        "jd",
        "cd",
        "dist",
        "dist_min",
        "dist_max",
        "v_rel",
        "v_inf",
        "t_sigma_f",
        "h",
        "diameter",
        "diameter_sigma",
        "fullname",
    ],
    "data": [[
        "99942",
        "206",
        "2462240.407091595",
        "2029-Apr-13 21:46",
        "0.000254099098170977",
        "0.000254085852623379",
        "0.000254112343772133",
        "7.42249308586014",
        "5.84135545611464",
        "< 00:01",
        "19.7",
        "0.34",
        "0.04",
        " 99942 Apophis (2004 MN4)",
    ]],
}


def test_payload_is_normalized_and_enriched():
    frame = payload_to_dataframe(SAMPLE)

    assert len(frame) == 1
    assert frame.loc[0, "fullname"] == "99942 Apophis (2004 MN4)"
    assert frame.loc[0, "diameter_m"] == pytest.approx(340.0)
    assert frame.loc[0, "distance_ld"] > 0


def test_wrong_api_version_is_rejected():
    payload = dict(SAMPLE)
    payload["signature"] = {"version": "99.0"}

    with pytest.raises(ValueError, match="Unsupported JPL CAD API version"):
        validate_payload(payload)


def test_zero_count_payload_returns_empty_dataframe():
    payload = {
        "signature": {"version": "1.5"},
        "count": 0,
    }

    frame = payload_to_dataframe(payload)
    assert frame.empty
