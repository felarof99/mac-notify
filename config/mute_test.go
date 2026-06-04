package config

import "testing"

func TestMuteMatchesSource(t *testing.T) {
	m, invalid := CompileMutes([]string{`^Codex · .*chatcli`})
	if len(invalid) != 0 {
		t.Fatalf("unexpected invalid patterns: %v", invalid)
	}
	if !m.MatchesAny("Codex · 📁 chatcli", `✅ {"segments":[]}`) {
		t.Error("expected the source to match the anchored pattern")
	}
}

func TestMuteMatchesBody(t *testing.T) {
	m, _ := CompileMutes([]string{`"segments"`})
	if !m.MatchesAny("Claude · SELF_IMPROVE", `✅ {"segments":[]}`) {
		t.Error("expected the body to match")
	}
}

func TestMuteNoMatch(t *testing.T) {
	m, _ := CompileMutes([]string{`chatcli`})
	if m.MatchesAny("Claude · SELF_IMPROVE › MAC_NOTIFY · w1", "✅ Done") {
		t.Error("did not expect a match for unrelated notification")
	}
}

func TestMuteAnchorsArePerField(t *testing.T) {
	// `^chatcli` must match a source that *starts* with chatcli, but not a body
	// that merely contains it — because each field is tested independently
	// rather than against one concatenated string.
	m, _ := CompileMutes([]string{`^chatcli`})
	if !m.MatchesAny("chatcli runner", "some body") {
		t.Error("expected anchored pattern to match the source field")
	}
	if m.MatchesAny("Codex · something", "ran chatcli at 10am") {
		t.Error("anchored ^ should not match chatcli in the middle of the body")
	}
}

func TestMuteInvalidRegexIsSkipped(t *testing.T) {
	m, invalid := CompileMutes([]string{`(unclosed`, `chatcli`})
	if len(invalid) != 1 || invalid[0] != `(unclosed` {
		t.Fatalf("expected exactly the bad pattern reported invalid, got %v", invalid)
	}
	// the valid pattern must still work after the bad one is skipped
	if !m.MatchesAny("x", "running chatcli now") {
		t.Error("valid pattern should still match after an invalid one is skipped")
	}
}

func TestMuteEmptyNeverMatches(t *testing.T) {
	m, _ := CompileMutes(nil)
	if m.MatchesAny("anything", "at all") {
		t.Error("empty mute set should never match")
	}
	// nil receiver must be safe (handleSend may call before any load)
	var nilSet *MuteSet
	if nilSet.MatchesAny("a", "b") {
		t.Error("nil MuteSet should never match")
	}
}

func TestMuteBlankPatternsIgnored(t *testing.T) {
	// blank / whitespace-only entries are config noise, not "match everything".
	m, invalid := CompileMutes([]string{"", "   "})
	if len(invalid) != 0 {
		t.Fatalf("blank patterns should be skipped silently, got invalid=%v", invalid)
	}
	if m.MatchesAny("literally anything", "with  two spaces") {
		t.Error("blank patterns should not match anything")
	}
}
