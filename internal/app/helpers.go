package app

import "strings"

// normalizeKey는 Bubble Tea key 문자열을 라우팅에서 쓰는 표준 이름으로 맞춘다.
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

// displayKey는 표준 key 이름을 입력 버퍼에 넣을 실제 문자로 바꾼다.
func displayKey(key string) string {
	if key == "space" {
		return " "
	}
	return key
}

// isText는 한 글자 입력만 text append 대상으로 본다.
func isText(key string) bool {
	return len([]rune(key)) == 1
}

// trimLastRune는 UTF-8 문자열에서 마지막 rune 하나를 지운다.
func trimLastRune(value string) string {
	runes := []rune(value)
	if len(runes) == 0 {
		return ""
	}
	return string(runes[:len(runes)-1])
}

// clamp는 cursor와 page index를 지정 범위 안에 고정한다.
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
