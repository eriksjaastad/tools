package logger

import (
	"log/slog"
	"os"
)

var defaultLogger *slog.Logger

func init() {
	// MCP protocol uses stdout, so logs must go to stderr
	opts := &slog.HandlerOptions{
		Level: slog.LevelInfo,
	}
	defaultLogger = slog.New(slog.NewJSONHandler(os.Stderr, opts))
}

func Info(msg string, args ...any) {
	defaultLogger.Info(msg, args...)
}

func Debug(msg string, args ...any) {
	defaultLogger.Debug(msg, args...)
}

func Warn(msg string, args ...any) {
	defaultLogger.Warn(msg, args...)
}

func Error(msg string, err error, args ...any) {
	if err != nil {
		args = append(args, slog.Any("error", err))
	}
	defaultLogger.Error(msg, args...)
}

func SetLevel(level string) {
	var l slog.Level
	switch level {
	case "DEBUG":
		l = slog.LevelDebug
	case "INFO":
		l = slog.LevelInfo
	case "WARN":
		l = slog.LevelWarn
	case "ERROR":
		l = slog.LevelError
	default:
		l = slog.LevelInfo
	}

	opts := &slog.HandlerOptions{
		Level: l,
	}
	defaultLogger = slog.New(slog.NewJSONHandler(os.Stderr, opts))
}
