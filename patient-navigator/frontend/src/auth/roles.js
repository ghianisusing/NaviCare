// Which experience a signed-in user gets. Staff (care coordinators and
// admins) get a work-focused app with no patient features; everyone
// else gets the patient app. The server enforces the real permissions
// (core/permissions.py); this only decides what to show.

export function isStaffUser(user) {
  return Boolean(user?.is_staff || user?.is_superuser)
}

export function homePathFor(user) {
  if (user?.is_superuser) return '/agent-monitoring'
  if (user?.is_staff) return '/care-support'
  return '/dashboard'
}
