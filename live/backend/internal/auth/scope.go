package auth

import (
	"context"
	"errors"
	"time"
)

type Scope struct {
	OrganizationID string   `json:"organization_id"`
	GroupIDs       []string `json:"group_ids"`
	UserID         string   `json:"user_id"`
	AsOf           string   `json:"as_of"`
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
		return nil, errors.New("unauthorized: principal not found")
	}

	return scope, nil
}


