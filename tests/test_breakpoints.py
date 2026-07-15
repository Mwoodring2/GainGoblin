from gaingoblin.ui.breakpoints import breakpoint_for_size


def test_breakpoint_for_size_returns_compact_standard_and_wide() -> None:
    compact = breakpoint_for_size(1024, 700)
    standard = breakpoint_for_size(1280, 800)
    wide = breakpoint_for_size(1600, 900)

    assert compact.name == "compact"
    assert compact.compact
    assert compact.summary_columns == 2

    assert standard.name == "standard"
    assert not standard.compact
    assert standard.show_speech

    assert wide.name == "wide"
    assert wide.goblin_size > standard.goblin_size
    assert wide.companion_width > standard.companion_width
