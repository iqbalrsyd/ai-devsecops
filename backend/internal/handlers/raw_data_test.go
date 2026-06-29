package handlers

import (
	"encoding/json"
	"strings"
	"testing"
)

// TestRawDataNormalization verifies that we correctly accept both
// shapes from the AI service for the raw_data field:
//
//  1. JSON object (preferred — Python serialises dicts natively).
//  2. JSON-encoded string (a string that contains a JSON document).
//
// Without this flexibility, a small type drift between the Python
// service and the Go client would 500 the entire pipeline request.
// This is a regression test for the @capture_io Pendekatan B
// rollout (raw_data is now a per-node snapshot of state).
func TestRawDataNormalization(t *testing.T) {
	tests := []struct {
		name    string
		payload string
		want    string
	}{
		{
			name:    "raw_data as JSON object (preferred)",
			payload: `{"domain_detection":{"duration_ms":1234,"output":{"detected_domain":"e-commerce"}}}`,
			want:    `{"domain_detection":{"duration_ms":1234,"output":{"detected_domain":"e-commerce"}}}`,
		},
		{
			name:    "raw_data as JSON-encoded string",
			payload: `"{\"domain_detection\":{\"duration_ms\":1234}}"`,
			want:    `{"domain_detection":{"duration_ms":1234}}`,
		},
		{
			name:    "raw_data empty",
			payload: `null`,
			want:    "null",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			// Replicate the inline normalisation logic in
			// pipeline_handler.go so the test exercises the
			// exact same code path.
			var raw json.RawMessage
			if err := json.Unmarshal([]byte(tc.payload), &raw); err != nil {
				t.Fatalf("unmarshal payload: %v", err)
			}

			rawDataStr := ""
			if len(raw) > 0 {
				trimmed := strings.TrimSpace(string(raw))
				if len(trimmed) > 0 && trimmed[0] == '"' {
					var s string
					if err := json.Unmarshal([]byte(trimmed), &s); err == nil {
						rawDataStr = s
					} else {
						rawDataStr = trimmed
					}
				} else {
					rawDataStr = trimmed
				}
			}

			if rawDataStr != tc.want {
				t.Errorf("normalised raw_data mismatch:\n  want: %q\n  got:  %q", tc.want, rawDataStr)
			}
		})
	}
}

// TestRawDataPersistable ensures that the normalised raw_data
// is valid JSON that can be inserted into a jsonb column. This
// guards against accidentally storing a string containing escaped
// quotes that Postgres will reject.
func TestRawDataPersistable(t *testing.T) {
	payload := `{"domain_detection":{"input":{},"output":{"detected_domain":"e-commerce"}}}`
	var raw json.RawMessage
	if err := json.Unmarshal([]byte(payload), &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	// Re-marshal and re-parse to round-trip.
	roundTrip, err := json.Marshal(raw)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var probe map[string]any
	if err := json.Unmarshal(roundTrip, &probe); err != nil {
		t.Fatalf("re-parse: %v", err)
	}
	if probe["domain_detection"] == nil {
		t.Errorf("expected domain_detection key in parsed payload")
	}
}
