package main

import (
	"fmt"
	"regexp"
)

func main() {
	text := `<|im_start|>{"name": "draft_read", "arguments": {"path": "test.md"}}`
	
	// Try different regex patterns
	patterns := []string{
		`<\|im_start\|>(?:assistant)?[\s\n]*(\{.*?"name".*?"arguments".*?\})`,
		`<\|im_start\|>.*?(\{.*?"name".*?"arguments".*?\})`,
		`<\|im_start\|>(\{.*?\})`,
	}
	
	for i, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		matches := re.FindStringSubmatch(text)
		fmt.Printf("Pattern %d: %s\n", i+1, pattern)
		fmt.Printf("Matches: %v\n", matches)
		fmt.Println()
	}
}

