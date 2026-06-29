package app

import "strings"

func normalizeKey(key string) string {
	if key == " " {
		return "space"
	}
	switch strings.ToLower(key) {
	case "enter", "up", "down", "left", "right", "space", "backspace", "ctrl+c", "ctrl+v", "ctrl+y", "alt+y", "esc":
		return strings.ToLower(key)
	default:
		return key
	}
}

func displayKey(key string) string {
	if key == "space" {
		return " "
	}
	return key
}

func isText(key string) bool {
	return len([]rune(key)) == 1
}

func trimLastRune(value string) string {
	runes := []rune(value)
	if len(runes) == 0 {
		return ""
	}
	return string(runes[:len(runes)-1])
}

func clamp(value int, min int, max int) int {
	if max < min {
		return min
	}
	if value < min {
		return min
	}
	if value > max {
		return max
	}
	return value
}
