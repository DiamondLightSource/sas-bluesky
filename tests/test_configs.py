from saxs_bluesky.beamline_configs import b21_config, i22_config


def test_i22_profile():
    assert len(i22_config.DEFAULT_PROFILE.groups[0].run_pulses) == 4


def test_b21_profile():
    assert len(b21_config.DEFAULT_PROFILE.groups[0].run_pulses) == 6
