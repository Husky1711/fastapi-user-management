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
import {
  BreakdownTables,
  CatalogTable,
  EmptyTableRow,
  formatTimestamp,
  parseStatsPayload,
  StatGrid,
} from "@/lib/compliance/display";
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

function StatsPanel({ raw }: { raw: unknown }) {
  const { metrics, breakdowns } = parseStatsPayload(raw);
  return (
    <>
      <StatGrid items={metrics} />
      <BreakdownTables sections={breakdowns} />
    </>
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
      setCleanupMessage(data.message ?? "Expired sessions were removed.");
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

  const auditLogs = auditLogsQuery.data?.logs ?? [];
  const permissions = permissionsQuery.data?.permissions ?? [];
  const groups = groupsQuery.data?.groups ?? [];
  const apiKeys = apiKeysQuery.data?.api_keys ?? [];
  const groupMembers = groupMembersQuery.data?.members ?? [];

  const overviewMetrics = [
    {
      label: "Audit events",
      value:
        parseStatsPayload(auditStatsQuery.data).metrics.find((m) => m.label === "Total Logs")
          ?.value ?? 0,
    },
    {
      label: "Active sessions",
      value:
        parseStatsPayload(sessionStatsQuery.data).metrics.find(
          (m) => m.label === "Active Sessions",
        )?.value ?? 0,
    },
    {
      label: "Permissions",
      value: permissionsQuery.data?.total_count ?? permissions.length,
    },
    {
      label: "Groups",
      value: groupsQuery.data?.total_count ?? groups.length,
    },
    {
      label: "API keys",
      value: apiKeysQuery.data?.total_count ?? apiKeys.length,
    },
  ];

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
          <h2>Overview</h2>
          <p className={styles.subtitle}>
            Security and compliance snapshot for your organization.
          </p>
          <StatGrid items={overviewMetrics} />
        </section>
      )}

      {tab === "audit" && (
        <section className={styles.section}>
          <h2>Audit trail</h2>
          <p className={styles.subtitle}>Recent sign-in and security events.</p>
          <StatsPanel raw={auditStatsQuery.data} />
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
                {auditLogs.length === 0 ? (
                  <EmptyTableRow colSpan={6} message="No audit events recorded yet." />
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id}>
                      <td>{formatTimestamp(log.created_at)}</td>
                      <td>{log.event_type ?? "—"}</td>
                      <td>{log.event_category ?? "—"}</td>
                      <td>{log.status ?? "—"}</td>
                      <td>{log.user_id ?? "—"}</td>
                      <td>{log.ip_address ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === "sessions" && (
        <section className={styles.section}>
          <h2>Sessions</h2>
          <p className={styles.subtitle}>Active and historical session activity.</p>
          <StatsPanel raw={sessionStatsQuery.data} />
          {canCleanup && (
            <div style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className={styles.logoutBtn}
                disabled={cleanupMutation.isPending}
                onClick={() => cleanupMutation.mutate()}
              >
                {cleanupMutation.isPending ? "Cleaning…" : "Remove expired sessions"}
              </button>
              {cleanupMessage && <p className={styles.loading}>{cleanupMessage}</p>}
            </div>
          )}
        </section>
      )}

      {tab === "permissions" && (
        <section className={styles.section}>
          <h2>Permissions</h2>
          <p className={styles.subtitle}>Granted permissions and available scopes.</p>
          <StatsPanel raw={permissionStatsQuery.data} />
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
                {permissions.length === 0 ? (
                  <EmptyTableRow colSpan={4} message="No custom permissions assigned." />
                ) : (
                  permissions.map((perm) => (
                    <tr key={perm.id}>
                      <td>{perm.permission_name}</td>
                      <td>
                        {perm.resource_type ?? "—"}
                        {perm.resource_id ? ` #${perm.resource_id}` : ""}
                      </td>
                      <td>{perm.is_active ? "Yes" : "No"}</td>
                      <td>{formatTimestamp(perm.expires_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {standardPermissionsQuery.data && (
            <CatalogTable
              title="Available permission scopes"
              entries={standardPermissionsQuery.data}
            />
          )}
        </section>
      )}

      {tab === "groups" && (
        <section className={styles.section}>
          <h2>Groups</h2>
          <p className={styles.subtitle}>User groups in your organization.</p>
          <StatsPanel raw={groupStatsQuery.data} />
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
                {groups.length === 0 ? (
                  <EmptyTableRow colSpan={5} message="No groups created yet." />
                ) : (
                  groups.map((group) => (
                    <tr key={group.id}>
                      <td>{group.id}</td>
                      <td>{group.name}</td>
                      <td>{group.member_count ?? 0}</td>
                      <td>{group.is_active ? "Yes" : "No"}</td>
                      <td>
                        <button
                          type="button"
                          className={styles.tab}
                          onClick={() => setSelectedGroupId(group.id)}
                        >
                          Members
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {selectedGroupId !== null && (
            <div style={{ marginTop: "1rem" }}>
              <h3>Group #{selectedGroupId} members</h3>
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
                    {groupMembers.length === 0 ? (
                      <EmptyTableRow colSpan={4} message="This group has no members." />
                    ) : (
                      groupMembers.map((member) => (
                        <tr key={`${member.user_id}-${member.added_at}`}>
                          <td>{member.user_id}</td>
                          <td>{member.username ?? "—"}</td>
                          <td>{member.email ?? "—"}</td>
                          <td>{formatTimestamp(member.added_at)}</td>
                        </tr>
                      ))
                    )}
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
          <p className={styles.subtitle}>Programmatic access keys for your organization.</p>
          <StatsPanel raw={apiKeyStatsQuery.data} />
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
                {apiKeys.length === 0 ? (
                  <EmptyTableRow colSpan={5} message="No API keys issued yet." />
                ) : (
                  apiKeys.map((key) => (
                    <tr key={key.id}>
                      <td>{key.key_name}</td>
                      <td>{key.key_prefix ?? "—"}</td>
                      <td>{key.user_id ?? "—"}</td>
                      <td>{key.is_active ? "Yes" : "No"}</td>
                      <td>{formatTimestamp(key.last_used_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          {apiKeyStandardQuery.data && (
            <CatalogTable
              title="Available API key scopes"
              entries={apiKeyStandardQuery.data}
            />
          )}
        </section>
      )}

      {tab === "password-policy" && (
        <section className={styles.section}>
          <h2>Password policy</h2>
          <p className={styles.subtitle}>Password strength and rotation requirements.</p>
          <StatsPanel raw={passwordPolicyQuery.data} />
        </section>
      )}
    </ComplianceShell>
  );
}
