package menubar

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/nickhudkins/mac-notify/ipc"
)

func writeConfig(t *testing.T, home, body string) {
	t.Helper()
	dir := filepath.Join(home, ".config", "mac-notify")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "config.yaml"), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func resetState() {
	mu.Lock()
	messages = nil
	muteSet = nil
	muteMtime = time.Time{}
	mu.Unlock()
}

// A muted notification must be dropped before it queues. This path returns
// before any cgo (menu/banner) call, so it is safe to exercise in a test.
func TestHandleSendDropsMuted(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	writeConfig(t, home, "system_notifications: false\nmute_patterns:\n  - \"^Codex · .*chatcli\"\n")
	resetState()

	resp := handleSend(ipc.Request{
		Message: `✅ {"segments":[]}`,
		Source:  "Codex · 📁 chatcli",
		ID:      "codex-spam",
	})
	if !resp.OK {
		t.Fatalf("muted send should still report OK, got %+v", resp)
	}
	if got := len(messages); got != 0 {
		t.Fatalf("muted message must not be queued, queue has %d", got)
	}
}

// Editing config.yaml takes effect on the next send, without a restart.
func TestRefreshMutesLiveReload(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	resetState()

	writeConfig(t, home, "mute_patterns:\n  - foo\n")
	mu.Lock()
	refreshMutes()
	mu.Unlock()
	if !muteSet.MatchesAny("foo", "") {
		t.Fatal("expected 'foo' to match after initial load")
	}

	time.Sleep(10 * time.Millisecond) // ensure a distinct mtime
	writeConfig(t, home, "mute_patterns:\n  - bar\n")
	mu.Lock()
	refreshMutes()
	mu.Unlock()
	if muteSet.MatchesAny("foo", "") {
		t.Error("'foo' should no longer match after live reload")
	}
	if !muteSet.MatchesAny("bar", "") {
		t.Error("'bar' should match after live reload")
	}
}
