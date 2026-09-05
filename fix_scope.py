import sys
path = 'live/backend/internal/auth/scope.go'
code = \"\"\"package auth

import (
	"context"
	"time"
)

type Scope struct {
	OrganizationID string   json:"organization_id"
	GroupIDs       []string json:"group_ids"
	UserID         string   json:"user_id"
	AsOf           string   json:"as_of"
}

// ResolveScope queries PostgreSQL (mocked) for a user's RBAC permissions
// Returns their canonical organization_id and authorized group_ids
func ResolveScope(ctx context.Context, userID string) (*Scope, error) {
	scope := &Scope{
		UserID: userID,
		AsOf:   time.Now().Format(time.RFC3339),
	}

	// MOCK Database Lookup
	if userID == "admin-123" {
		scope.OrganizationID = "JPL"
		scope.GroupIDs = []string{"1", "2"}
	} else if userID == "tenant-456" {
		scope.OrganizationID = "NASA"
		scope.GroupIDs = []string{"3"}
	} else {
		scope.OrganizationID = "DEFAULT_ORG"
		scope.GroupIDs = []string{"0"}
	}

	return scope, nil
}
\"\"\"
with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
