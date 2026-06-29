package models

const (
	RoleAdmin    = "admin"
	RoleEngineer = "engineer"
	RoleViewer   = "viewer"
)

var ValidRoles = map[string]bool{
	RoleAdmin:    true,
	RoleEngineer: true,
	RoleViewer:   true,
}

func IsValidRole(role string) bool {
	return ValidRoles[role]
}
