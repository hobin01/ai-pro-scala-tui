package app

import "strings"

// normalizeKey는 관련 동작을 처리한다.
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

// displayKey는 관련 동작을 처리한다.
func displayKey(key string) string {
	if key == "space" {
		return " "
	}
	return key
}

// isText는 관련 동작을 처리한다.
func isText(key string) bool {
	return len([]rune(key)) == 1
}

// trimLastRune는 관련 동작을 처리한다.
func trimLastRune(value string) string {
	runes := []rune(value)
	if len(runes) == 0 {
		return ""
	}
	return string(runes[:len(runes)-1])
}

// clamp는 관련 동작을 처리한다.
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
