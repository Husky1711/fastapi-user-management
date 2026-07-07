import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ComplianceShell } from "@/components/ComplianceShell";
import { getApiError } from "@/lib/apiClient";
import { useAuth } from "@/lib/auth/AuthProvider";
import {
  cleanupExpiredSessions,
  fetchApiKeyStandardPermissions,
  fetchApiKeyStatistics,
  fetchApiKeys,
  fetchAuditLogs,
  fetchAuditStatistics,
  fetchGroupMembers,
  fetchGroupStatistics,
  fetchGroups,
  fetchPasswordPolicyStats,
  fetchPermissionStatistics,
  fetchPermissions,
  fetchSessionStatistics,
  fetchStandardPermissions,
} from "@/lib/compliance/api";
import styles from "@/pages/AdminPage.module.css";

type TabId =
  | "overview"
  | "audit"
  | "sessions"
  | "permissions"
  | "groups"
  | "api-keys"
  | "password-policy";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "audit", label: "Audit" },
  { id: "sessions", label: "Sessions" },
  { id: "permissions", label: "Permissions" },
  { id: "groups", label: "Groups" },
  { id: "api-keys", label: "API keys" },
  { id: "password-policy", label: "Password policy" },
];

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.card}>
      <p className={styles.cardLabel}>{label}</p>
      <p className={styles.cardValue}>{value}</p>
    </div>
  );
}

function KeyValueGrid({ data }: { data: Record<string, unknown> | undefined }) {
  if (!data || Object.keys(data).length === 0) {
    return <p className={styles.loading}>No statistics available.</p>;
  }

  return (
    <div className={styles.grid}>
      {Object.entries(data).map(([key, value]) => (
        <StatCard
          key={key}
          label={key.replaceAll("_", " ")}
          value={
            typeof value === "object" && value !== null
              ? JSON.stringify(value)
              : String(value ?? "—")
          }
        />
      ))}
    </div>
  );
}

export function CompliancePage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<TabId>("overview");
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [cleanupMessage, setCleanupMessage] = useState<string | null>(null);

  const canCleanup =
    user?.role === "super_admin" || user?.role === "organization_admin";

  const auditStatsQuery = useQuery({
    queryKey: ["compliance", "audit-stats"],
    queryFn: fetchAuditStatistics,
  });
  const auditLogsQuery = useQuery({
    queryKey: ["compliance", "audit-logs"],
    queryFn: () => fetchAuditLogs({ limit: 50 }),
    enabled: tab === "audit" || tab === "overview",
  });
  const sessionStatsQuery = useQuery({
    queryKey: ["compliance", "session-stats"],
    queryFn: fetchSessionStatistics,
  });
  const permissionsQuery = useQuery({
    queryKey: ["compliance", "permissions"],
    queryFn: () => fetchPermissions(),
    enabled: tab === "permissions" || tab === "overview",
  });
  const permissionStatsQuery = useQuery({
    queryKey: ["compliance", "permission-stats"],
    queryFn: fetchPermissionStatistics,
    enabled: tab === "permissions" || tab === "overview",
  });
  const standardPermissionsQuery = useQuery({
    queryKey: ["compliance", "permissions-standard"],
    queryFn: fetchStandardPermissions,
    enabled: tab === "permissions",
  });
  const groupsQuery = useQuery({
    queryKey: ["compliance", "groups"],
    queryFn: fetchGroups,
    enabled: tab === "groups" || tab === "overview",
  });
  const groupStatsQuery = useQuery({
    queryKey: ["compliance", "group-stats"],
    queryFn: fetchGroupStatistics,
    enabled: tab === "groups" || tab === "overview",
  });
  const groupMembersQuery = useQuery({
    queryKey: ["compliance", "group-members", selectedGroupId],
    queryFn: () => fetchGroupMembers(selectedGroupId!),
    enabled: tab === "groups" && selectedGroupId !== null,
  });
  const apiKeysQuery = useQuery({
    queryKey: ["compliance", "api-keys"],
    queryFn: () => fetchApiKeys(),
    enabled: tab === "api-keys" || tab === "overview",
  });
  const apiKeyStatsQuery = useQuery({
    queryKey: ["compliance", "api-key-stats"],
    queryFn: fetchApiKeyStatistics,
    enabled: tab === "api-keys" || tab === "overview",
  });
  const apiKeyStandardQuery = useQuery({
    queryKey: ["compliance", "api-key-standard"],
    queryFn: fetchApiKeyStandardPermissions,
    enabled: tab === "api-keys",
  });
  const passwordPolicyQuery = useQuery({
    queryKey: ["compliance", "password-policy"],
    queryFn: () => fetchPasswordPolicyStats(),
    enabled: tab === "password-policy" || tab === "overview",
  });

  const cleanupMutation = useMutation({
    mutationFn: cleanupExpiredSessions,
    onSuccess: (data) => {
      setCleanupMessage(data.message ?? "Expired sessions cleaned up.");
      void sessionStatsQuery.refetch();
    },
    onError: (err) => setCleanupMessage(getApiError(err).detail),
  });

  const activeError =
    auditStatsQuery.error ||
    auditLogsQuery.error ||
    sessionStatsQuery.error ||
    permissionsQuery.error ||
    groupsQuery.error ||
    apiKeysQuery.error ||
    passwordPolicyQuery.error;

  return (
    <ComplianceShell>
      <div className={styles.tabs} style={{ marginTop: "1rem" }}>
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? styles.tabActive : styles.tab}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {activeError && (
        <p className={styles.error} style={{ marginTop: "1rem" }}>
          {getApiError(activeError).detail}
        </p>
      )}

      {tab === "overview" && (
        <section className={styles.section}>
          <h2>Compliance overview</h2>
          <p className={styles.subtitle}>Aggregated M8 production endpoint statistics</p>
          <div className={styles.grid}>
            <StatCard
              label="Audit logs"
              value={auditStatsQuery.data?.statistics?.total_logs ?? "—"}
            />
            <StatCard
              label="Active sessions"
              value={sessionStatsQuery.data?.statistics?.active_sessions ?? "—"}
            />
            <StatCard
              label="Permissions"
              value={permissionsQuery.data?.total_count ?? permissionsQuery.data?.permissions?.length ?? "—"}
            />
            <StatCard
              label="Groups"
              value={groupsQuery.data?.total_count ?? groupsQuery.data?.groups?.length ?? "—"}
            />
            <StatCard
              label="API keys"
              value={apiKeysQuery.data?.total_count ?? apiKeysQuery.data?.api_keys?.length ?? "—"}
            />
          </div>
        </section>
      )}

      {tab === "audit" && (
        <section className={styles.section}>
          <h2>Audit logs</h2>
          <p className={styles.subtitle}>GET /api/v1/audit/logs · /audit/statistics</p>
          <KeyValueGrid
            data={auditStatsQuery.data?.statistics as Record<string, unknown> | undefined}
          />
          <div className={styles.tableWrap} style={{ marginTop: "1rem" }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>User</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {(auditLogsQuery.data?.logs ?? []).map((log) => (
                  <tr key={log.id}>
                    <td>{log.created_at ?? "—"}</td>
                    <td>{log.event_type ?? "—"}</td>
                    <td>{log.event_category ?? "—"}</td>
                    <td>{log.status ?? "—"}</td>
                    <td>{log.user_id ?? "—"}</td>
                    <td>{log.ip_address ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "sessions" && (
        <section className={styles.section}>
          <h2>Session analytics</h2>
          <p className={styles.subtitle}>
            GET /api/v1/sessions/statistics · POST /api/v1/sessions/cleanup
          </p>
          <KeyValueGrid
            data={sessionStatsQuery.data?.statistics as Record<string, unknown> | undefined}
          />
          {canCleanup && (
            <div style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className={styles.logoutBtn}
                disabled={cleanupMutation.isPending}
                onClick={() => cleanupMutation.mutate()}
              >
                {cleanupMutation.isPending ? "Cleaning…" : "Clean up expired sessions"}
              </button>
              {cleanupMessage && <p className={styles.loading}>{cleanupMessage}</p>}
            </div>
          )}
        </section>
      )}

      {tab === "permissions" && (
        <section className={styles.section}>
          <h2>Permissions</h2>
          <p className={styles.subtitle}>
            GET /api/v1/permissions · /permissions/standard · /permissions/statistics
          </p>
          <KeyValueGrid
            data={permissionStatsQuery.data?.statistics as Record<string, unknown> | undefined}
          />
          <div className={styles.tableWrap} style={{ marginTop: "1rem" }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Resource</th>
                  <th>Active</th>
                  <th>Expires</th>
                </tr>
              </thead>
              <tbody>
                {(permissionsQuery.data?.permissions ?? []).map((perm) => (
                  <tr key={perm.id}>
                    <td>{perm.permission_name}</td>
                    <td>
                      {perm.resource_type ?? "—"}
                      {perm.resource_id ? ` #${perm.resource_id}` : ""}
                    </td>
                    <td>{perm.is_active ? "yes" : "no"}</td>
                    <td>{perm.expires_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {standardPermissionsQuery.data && (
            <div style={{ marginTop: "1rem" }}>
              <h3>Standard permissions</h3>
              <KeyValueGrid data={standardPermissionsQuery.data} />
            </div>
          )}
        </section>
      )}

      {tab === "groups" && (
        <section className={styles.section}>
          <h2>Groups</h2>
          <p className={styles.subtitle}>
            GET /api/v1/groups · /groups/statistics · /groups/{"{id}"}/members
          </p>
          <KeyValueGrid data={groupStatsQuery.data} />
          <div className={styles.tableWrap} style={{ marginTop: "1rem" }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Members</th>
                  <th>Active</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(groupsQuery.data?.groups ?? []).map((group) => (
                  <tr key={group.id}>
                    <td>{group.id}</td>
                    <td>{group.name}</td>
                    <td>{group.member_count ?? "—"}</td>
                    <td>{group.is_active ? "yes" : "no"}</td>
                    <td>
                      <button
                        type="button"
                        className={styles.tab}
                        onClick={() => setSelectedGroupId(group.id)}
                      >
                        View members
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {selectedGroupId !== null && (
            <div style={{ marginTop: "1rem" }}>
              <h3>Members of group #{selectedGroupId}</h3>
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>User ID</th>
                      <th>Username</th>
                      <th>Email</th>
                      <th>Added</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(groupMembersQuery.data?.members ?? []).map((member) => (
                      <tr key={`${member.user_id}-${member.added_at}`}>
                        <td>{member.user_id}</td>
                        <td>{member.username ?? "—"}</td>
                        <td>{member.email ?? "—"}</td>
                        <td>{member.added_at ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      )}

      {tab === "api-keys" && (
        <section className={styles.section}>
          <h2>API keys</h2>
          <p className={styles.subtitle}>
            GET /api/v1/api-keys · /api-keys/statistics · /api-keys/standard-permissions
          </p>
          <KeyValueGrid data={apiKeyStatsQuery.data} />
          <div className={styles.tableWrap} style={{ marginTop: "1rem" }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Prefix</th>
                  <th>User</th>
                  <th>Active</th>
                  <th>Last used</th>
                </tr>
              </thead>
              <tbody>
                {(apiKeysQuery.data?.api_keys ?? []).map((key) => (
                  <tr key={key.id}>
                    <td>{key.key_name}</td>
                    <td>{key.key_prefix ?? "—"}</td>
                    <td>{key.user_id ?? "—"}</td>
                    <td>{key.is_active ? "yes" : "no"}</td>
                    <td>{key.last_used_at ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {apiKeyStandardQuery.data && (
            <div style={{ marginTop: "1rem" }}>
              <h3>Standard API key permissions</h3>
              <KeyValueGrid data={apiKeyStandardQuery.data} />
            </div>
          )}
        </section>
      )}

      {tab === "password-policy" && (
        <section className={styles.section}>
          <h2>Password policy</h2>
          <p className={styles.subtitle}>GET /api/v1/password/policy-stats</p>
          <KeyValueGrid
            data={passwordPolicyQuery.data?.statistics as Record<string, unknown> | undefined}
          />
        </section>
      )}
    </ComplianceShell>
  );
}
