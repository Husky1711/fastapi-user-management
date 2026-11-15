import { useId, useState } from "react";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useMyOrganizations } from "@/lib/org/api";
import styles from "./OrgSwitcher.module.css";

/**
 * Organization switcher for people who belong to several organizations.
 * Renders nothing for single-organization users. Switching re-loads the user's
 * profile (their role can differ per organization) and opens the matching home.
 */
export function OrgSwitcher() {
  const { status, switchOrganization } = useAuth();
  const { data } = useMyOrganizations(status === "authenticated");
  const [switching, setSwitching] = useState(false);
  const id = useId();

  if (!data || data.organizations.length < 2) return null;

  return (
    <label className={styles.switcher} htmlFor={id}>
      Organization
      <select
        id={id}
        className={styles.select}
        value={data.active_organization_id}
        disabled={switching}
        onChange={async (e) => {
          setSwitching(true);
          try {
            await switchOrganization(Number(e.target.value));
          } finally {
            setSwitching(false);
          }
        }}
      >
        {data.organizations.map((o) => (
          <option key={o.organization_id} value={o.organization_id}>
            {(o.organization_name ?? `Organization ${o.organization_id}`) + ` (${o.role.replace(/_/g, " ")})`}
          </option>
        ))}
      </select>
    </label>
  );
}
