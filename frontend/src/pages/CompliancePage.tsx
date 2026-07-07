import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ComplianceShell } from "@/components/ComplianceShell";
import { getApiError } from "@/lib/apiClient";
import { useAuth } from "@/lib/auth/AuthProvider";
import {
  addGroupMember,
  cleanupExpiredSessions,
  createApiKey,
  createGroup,
  deleteGroup,
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
  removeGroupMember,
  revokeApiKey,
} from "@/lib/compliance/api";
import { canManageUsers } from "@/lib/auth/routing";
import {
  BreakdownTables,
  CatalogTable,
  EmptyTableRow,
  formatTimestamp,
  parseStatsPayload,
  StatGrid,
} from "@/lib/compliance/display";
import styles from "@/pages/AdminPage.module.css";
import formStyles from "@/pages/ProfilePage.module.css";

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
  const [groupName, setGroupName] = useState("");
  const [groupDescription, setGroupDescription] = useState("");
  const [groupActionMessage, setGroupActionMessage] = useState<string | null>(null);
  const [memberUserId, setMemberUserId] = useState("");
  const [apiKeyName, setApiKeyName] = useState("");
  const [apiKeyActionMessage, setApiKeyActionMessage] = useState<string | null>(null);
  const [issuedKeyValue, setIssuedKeyValue] = useState<string | null>(null);

  const canCleanup =
    user?.role === "super_admin" || user?.role === "organization_admin";
  const canManageGroups = user ? canManageUsers(user.role) : false;

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

  const createGroupMutation = useMutation({
    mutationFn: () =>
      createGroup({
        name: groupName.trim(),
        description: groupDescription.trim() || undefined,
      }),
    onSuccess: (data) => {
      setGroupActionMessage(data.message ?? "Group created.");
      setGroupName("");
      setGroupDescription("");
      void groupsQuery.refetch();
      void groupStatsQuery.refetch();
    },
    onError: (err) => setGroupActionMessage(getApiError(err).detail),
  });

  const deleteGroupMutation = useMutation({
    mutationFn: deleteGroup,
    onSuccess: (data) => {
      setGroupActionMessage(data.message ?? "Group deleted.");
      setSelectedGroupId(null);
      void groupsQuery.refetch();
      void groupStatsQuery.refetch();
    },
    onError: (err) => setGroupActionMessage(getApiError(err).detail),
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      addGroupMember(groupId, userId),
    onSuccess: (data) => {
      setGroupActionMessage(data.message ?? "Member added.");
      setMemberUserId("");
      void groupMembersQuery.refetch();
      void groupsQuery.refetch();
    },
    onError: (err) => setGroupActionMessage(getApiError(err).detail),
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      removeGroupMember(groupId, userId),
    onSuccess: (data) => {
      setGroupActionMessage(data.message ?? "Member removed.");
      void groupMembersQuery.refetch();
      void groupsQuery.refetch();
    },
    onError: (err) => setGroupActionMessage(getApiError(err).detail),
  });

  const createApiKeyMutation = useMutation({
    mutationFn: () => createApiKey({ key_name: apiKeyName.trim() }),
    onSuccess: (data) => {
      setApiKeyActionMessage(data.message ?? "API key created.");
      setIssuedKeyValue(data.key_value ?? null);
      setApiKeyName("");
      void apiKeysQuery.refetch();
      void apiKeyStatsQuery.refetch();
    },
    onError: (err) => setApiKeyActionMessage(getApiError(err).detail),
  });

  const revokeApiKeyMutation = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: (data) => {
      setApiKeyActionMessage(data.message ?? "API key revoked.");
      void apiKeysQuery.refetch();
      void apiKeyStatsQuery.refetch();
    },
    onError: (err) => setApiKeyActionMessage(getApiError(err).detail),
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
          {groupActionMessage && <p className={styles.subtitle}>{groupActionMessage}</p>}
          {canManageGroups && (
            <form
              className={formStyles.form}
              onSubmit={(event) => {
                event.preventDefault();
                if (!groupName.trim()) return;
                createGroupMutation.mutate();
              }}
            >
              <input
                className={formStyles.input}
                placeholder="Group name"
                value={groupName}
                onChange={(event) => setGroupName(event.target.value)}
              />
              <input
                className={formStyles.input}
                placeholder="Description (optional)"
                value={groupDescription}
                onChange={(event) => setGroupDescription(event.target.value)}
              />
              <button type="submit" className={formStyles.primaryBtn} disabled={createGroupMutation.isPending}>
                Create group
              </button>
            </form>
          )}
          <StatsPanel raw={groupStatsQuery.data} />
          <div className={styles.tableWrap} style={{ marginTop: "1rem" }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Members</th>
                  <th>Active</th>
                  <th>Actions</th>
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
                        {canManageGroups && group.is_active !== false && (
                          <button
                            type="button"
                            className={styles.tab}
                            style={{ marginLeft: "0.5rem" }}
                            onClick={() => deleteGroupMutation.mutate(group.id)}
                            disabled={deleteGroupMutation.isPending}
                          >
                            Delete
                          </button>
                        )}
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
              {canManageGroups && (
                <form
                  className={formStyles.form}
                  onSubmit={(event) => {
                    event.preventDefault();
                    const userId = Number(memberUserId);
                    if (!Number.isFinite(userId) || userId <= 0) return;
                    addMemberMutation.mutate({ groupId: selectedGroupId, userId });
                  }}
                >
                  <input
                    className={formStyles.input}
                    placeholder="User ID to add"
                    value={memberUserId}
                    onChange={(event) => setMemberUserId(event.target.value)}
                  />
                  <button type="submit" className={formStyles.primaryBtn} disabled={addMemberMutation.isPending}>
                    Add member
                  </button>
                </form>
              )}
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>User ID</th>
                      <th>Username</th>
                      <th>Email</th>
                      <th>Added</th>
                      {canManageGroups && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {groupMembers.length === 0 ? (
                      <EmptyTableRow
                        colSpan={canManageGroups ? 5 : 4}
                        message="This group has no members."
                      />
                    ) : (
                      groupMembers.map((member) => (
                        <tr key={`${member.user_id}-${member.added_at}`}>
                          <td>{member.user_id}</td>
                          <td>{member.username ?? "—"}</td>
                          <td>{member.email ?? "—"}</td>
                          <td>{formatTimestamp(member.added_at)}</td>
                          {canManageGroups && (
                            <td>
                              <button
                                type="button"
                                className={styles.tab}
                                onClick={() =>
                                  removeMemberMutation.mutate({
                                    groupId: selectedGroupId,
                                    userId: member.user_id,
                                  })
                                }
                                disabled={removeMemberMutation.isPending}
                              >
                                Remove
                              </button>
                            </td>
                          )}
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
          {apiKeyActionMessage && <p className={styles.subtitle}>{apiKeyActionMessage}</p>}
          {issuedKeyValue && (
            <p className={styles.subtitle}>
              Copy this key now — it will not be shown again:{" "}
              <code>{issuedKeyValue}</code>
            </p>
          )}
          <form
            className={formStyles.form}
            onSubmit={(event) => {
              event.preventDefault();
              if (!apiKeyName.trim()) return;
              setIssuedKeyValue(null);
              createApiKeyMutation.mutate();
            }}
          >
            <input
              className={formStyles.input}
              placeholder="Key name"
              value={apiKeyName}
              onChange={(event) => setApiKeyName(event.target.value)}
            />
            <button type="submit" className={formStyles.primaryBtn} disabled={createApiKeyMutation.isPending}>
              Issue API key
            </button>
          </form>
          <p className={styles.subtitle}>
            Test M2M auth: <code>GET /api/v1/integration/whoami</code> with header{" "}
            <code>X-API-Key</code>.
          </p>
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
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.length === 0 ? (
                  <EmptyTableRow colSpan={6} message="No API keys issued yet." />
                ) : (
                  apiKeys.map((key) => (
                    <tr key={key.id}>
                      <td>{key.key_name}</td>
                      <td>{key.key_prefix ?? "—"}</td>
                      <td>{key.user_id ?? "—"}</td>
                      <td>{key.is_active ? "Yes" : "No"}</td>
                      <td>{formatTimestamp(key.last_used_at)}</td>
                      <td>
                        {key.is_active && (
                          <button
                            type="button"
                            className={styles.tab}
                            onClick={() => revokeApiKeyMutation.mutate(key.id)}
                            disabled={revokeApiKeyMutation.isPending}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
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
