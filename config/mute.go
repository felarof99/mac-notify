package config

import (
	"regexp"
	"strings"
)

// MuteSet is a compiled collection of mute patterns. A notification is muted
// when any pattern matches any of the fields it is tested against (source or
// body). The zero value (and a nil *MuteSet) never matches, so callers can use
// it before any config has been loaded.
type MuteSet struct {
	res []*regexp.Regexp
}

// CompileMutes compiles regex patterns into a MuteSet. Blank/whitespace-only
// entries are ignored, and any pattern that fails to compile is skipped and
// returned in invalid — a bad pattern must never take down the daemon or
// silence everything.
func CompileMutes(patterns []string) (*MuteSet, []string) {
	m := &MuteSet{}
	var invalid []string
	for _, p := range patterns {
		if strings.TrimSpace(p) == "" {
			continue
		}
		re, err := regexp.Compile(p)
		if err != nil {
			invalid = append(invalid, p)
			continue
		}
		m.res = append(m.res, re)
	}
	return m, invalid
}

// MatchesAny reports whether any compiled pattern matches any of the given
// (non-empty) texts. Each text is tested independently so anchored patterns
// (^, $) behave per field rather than against a concatenation.
func (m *MuteSet) MatchesAny(texts ...string) bool {
	if m == nil || len(m.res) == 0 {
		return false
	}
	for _, re := range m.res {
		for _, t := range texts {
			if t != "" && re.MatchString(t) {
				return true
			}
		}
	}
	return false
}
