package sandbox

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Sandbox provides safe file operations within a root directory.
type Sandbox struct {
	Root string
}

// NewSandbox creates a new sandbox.
func NewSandbox(root string) (*Sandbox, error) {
	absRoot, err := filepath.Abs(root)
	if err != nil {
		return nil, err
	}
	return &Sandbox{Root: absRoot}, nil
}

// ValidatePath ensures a path is within the sandbox root.
func (s *Sandbox) ValidatePath(path string) (string, error) {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}

	rel, err := filepath.Rel(s.Root, absPath)
	if err != nil {
		return "", err
	}

	if strings.HasPrefix(rel, ".."+string(filepath.Separator)) || rel == ".." {
		return "", fmt.Errorf("path traversal attempt: %s is outside sandbox root %s", path, s.Root)
	}

	// Check if the path exists and is a symlink
	info, err := os.Lstat(absPath)
	if err == nil && info.Mode()&os.ModeSymlink != 0 {
		// Resolve symlink
		resolved, err := filepath.EvalSymlinks(absPath)
		if err != nil {
			return "", err
		}
		// Validate resolved path
		return s.ValidatePath(resolved)
	}

	return absPath, nil
}

// SafeRead reads a file from the sandbox.
func (s *Sandbox) SafeRead(path string) ([]byte, error) {
	validatedPath, err := s.ValidatePath(path)
	if err != nil {
		return nil, err
	}

	return os.ReadFile(validatedPath)
}

// SafeWrite writes a file atomically to the sandbox.
func (s *Sandbox) SafeWrite(path string, content []byte) error {
	validatedPath, err := s.ValidatePath(path)
	if err != nil {
		return err
	}

	// Ensure parent directory exists
	if err := os.MkdirAll(filepath.Dir(validatedPath), 0755); err != nil {
		return err
	}

	// Atomic write: write to temp file, then rename
	tmpFile, err := os.CreateTemp(filepath.Dir(validatedPath), ".tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmpFile.Name()
	defer os.Remove(tmpName)

	if _, err := tmpFile.Write(content); err != nil {
		_ = tmpFile.Close()
		return err
	}

	if err := tmpFile.Close(); err != nil {
		return err
	}

	return os.Rename(tmpName, validatedPath)
}

// SafeList lists contents of a directory in the sandbox.
func (s *Sandbox) SafeList(path string) ([]os.DirEntry, error) {
	validatedPath, err := s.ValidatePath(path)
	if err != nil {
		return nil, err
	}

	return os.ReadDir(validatedPath)
}
