/**
 * Active organization for multi-organization users.
 *
 * The API client sends it as `X-Organization-Id` on every request; the backend
 * validates membership and evaluates the user's role *in that organization*.
 * Not set = the user's home organization (single-org users never see a switcher).
 */
const STORAGE_KEY = "activeOrganizationId";

let activeOrgId: number | null = read();

function read(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const n = raw ? Number(raw) : NaN;
    return Number.isInteger(n) && n > 0 ? n : null;
  } catch {
    return null; // storage blocked (private mode, previews)
  }
}

export function getActiveOrgId(): number | null {
  return activeOrgId;
}

export function setActiveOrgId(id: number | null): void {
  activeOrgId = id;
  try {
    if (id === null) localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, String(id));
  } catch {
    // per-tab only when storage is unavailable
  }
}

export const ORG_HEADER = "X-Organization-Id";
