package tools

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSafePath(t *testing.T) {
	baseDir, err := os.MkdirTemp("", "safepath-test-*")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(baseDir)

	// Ensure we have absolute paths for comparison
	baseAbs, _ := filepath.Abs(baseDir)

	tests := []struct {
		name      string
		base      string
		requested string
		want      string
		wantErr   bool
	}{
		{
			name:      "Valid relative path",
			base:      baseAbs,
			requested: "src/index.ts",
			want:      filepath.Join(baseAbs, "src/index.ts"),
			wantErr:   false,
		},
		{
			name:      "Valid dot slash path",
			base:      baseAbs,
			requested: "./src/index.ts",
			want:      filepath.Join(baseAbs, "src/index.ts"),
			wantErr:   false,
		},
		{
			name:      "Traversal attack - double dot",
			base:      baseAbs,
			requested: "../etc/passwd",
			want:      "",
			wantErr:   true,
		},
		{
			name:      "Traversal attack - nested double dot",
			base:      baseAbs,
			requested: "foo/../../etc/passwd",
			want:      "",
			wantErr:   true,
		},
		{
			name:      "Absolute path attempt",
			base:      baseAbs,
			requested: "/etc/passwd",
			want:      "",
			wantErr:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := SafePath(tt.base, tt.requested)
			if (err != nil) != tt.wantErr {
				t.Errorf("SafePath() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !tt.wantErr && got != tt.want {
				// On some systems (macOS /var vs /private/var), paths might differ slightly but be functionally same.
				// We compare absolute paths.
				gotAbs, _ := filepath.Abs(got)
				wantAbs, _ := filepath.Abs(tt.want)
				if gotAbs != wantAbs {
					t.Errorf("SafePath() = %v, want %v", got, tt.want)
				}
			}
			if tt.wantErr && !strings.Contains(err.Error(), "path traversal attempt") && !strings.Contains(tt.name, "Absolute") {
				// The absolute path attempt might fail with a different error depending on OS logic in Rel()
			}
		})
	}
}
