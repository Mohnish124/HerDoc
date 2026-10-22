// Role-based landing pages. The role always comes from the server's authenticated user;
// the backend enforces access on every API call regardless of what the UI shows.
export const STAFF_ROLES = ['doctor', 'admin'];
export const WORKER_ROLES = ['worker'];

export function homePathForRole(role) {
  return role === 'worker' ? '/worker' : '/dashboard';
}

// Only return to a remembered page if the signed-in role is allowed there.
export function canVisit(role, pathname) {
  if (!pathname) return false;
  if (pathname === '/worker' || pathname.startsWith('/worker/')) return role === 'worker';
  if (pathname === '/workers') return role === 'admin';
  if (['/dashboard', '/facility'].includes(pathname) || pathname.startsWith('/patients/')) {
    return STAFF_ROLES.includes(role);
  }
  return false;
}
