import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { StaffShell } from "@/components/StaffShell";
import { fetchUserById, fetchUsers, updateUser } from "@/lib/admin/api";
import { allowedCreateRoles, canEditUser, isManagerRole } from "@/lib/admin/roles";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/ProfilePage.module.css";

const STATUS_OPTIONS = ["active", "inactive", "suspended", "pending"];

export function AdminUserDetailPage() {
  const { userId } = useParams();
  const id = Number(userId);
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("user");
  const [status, setStatus] = useState("active");
  const [managerId, setManagerId] = useState<string>("");
  const [organizationId, setOrganizationId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const userQuery = useQuery({
    queryKey: ["admin", "user", id],
    queryFn: () => fetchUserById(id),
    enabled: Number.isFinite(id),
  });

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: fetchUsers,
    enabled: editing && Number.isFinite(id),
  });

  const editable =
    !!currentUser &&
    !!userQuery.data &&
    userQuery.data.id !== currentUser.id &&
    canEditUser(currentUser.role, userQuery.data.role);

  const assignableRoles = currentUser ? allowedCreateRoles(currentUser.role) : [];

  const roleOptions = useMemo(() => {
    if (!userQuery.data) {
      return assignableRoles;
    }
    return Array.from(new Set([...assignableRoles, userQuery.data.role]));
  }, [assignableRoles, userQuery.data]);

  const managerOptions = useMemo(() => {
    if (!currentUser || !userQuery.data) {
      return [];
    }

    if (currentUser.role === "admin") {
      return [
        {
          id: currentUser.id,
          username: currentUser.username,
          role: currentUser.role,
        },
      ];
    }

    if (!usersQuery.data) {
      return [];
    }

    return usersQuery.data.filter(
      (candidate) =>
        candidate.id !== userQuery.data.id && isManagerRole(candidate.role),
    );
  }, [currentUser, usersQuery.data, userQuery.data]);

  useEffect(() => {
    if (!userQuery.data) {
      return;
    }
    setEmail(userQuery.data.email);
    setPhone(userQuery.data.phone_number ?? "");
    setRole(userQuery.data.role);
    setStatus(userQuery.data.status);
    setManagerId(userQuery.data.manager_id ? String(userQuery.data.manager_id) : "");
    setOrganizationId(String(userQuery.data.organization_id));
  }, [userQuery.data]);

  const mutation = useMutation({
    mutationFn: () =>
      updateUser(id, {
        email,
        phone_number: phone || undefined,
        role,
        status,
        manager_id:
          role === "user"
            ? managerId
              ? Number(managerId)
              : null
            : null,
        organization_id:
          currentUser?.role === "super_admin" ? Number(organizationId) : undefined,
      }),
    onSuccess: (data) => {
      setError(null);
      setSuccess(data.message);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["admin", "user", id] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    mutation.mutate();
  }

  return (
    <StaffShell>
      <section className={styles.panel}>
        <Link to="/admin/users" className={styles.backLink}>
          ← Back to users
        </Link>
        <h2 style={{ marginTop: "1rem" }}>User detail</h2>
        <p className={styles.subtitle}>GET /api/v1/users/{userId}</p>

        {userQuery.isLoading && <p className={styles.loading}>Loading user…</p>}
        {userQuery.error && (
          <p className={styles.error}>{getApiError(userQuery.error).detail}</p>
        )}

        {userQuery.data && (
          <>
            {success && <p className={styles.success}>{success}</p>}
            {error && <p className={styles.error}>{error}</p>}

            {!editing && (
              <div className={styles.card} style={{ marginTop: "1rem" }}>
                <div className={styles.fieldGrid}>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>ID</span>
                    <span className={styles.fieldValue}>{userQuery.data.id}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Username</span>
                    <span className={styles.fieldValue}>{userQuery.data.username}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Email</span>
                    <span className={styles.fieldValue}>{userQuery.data.email}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Role</span>
                    <span className={styles.fieldValue}>{userQuery.data.role}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Status</span>
                    <span className={styles.fieldValue}>{userQuery.data.status}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Organization</span>
                    <span className={styles.fieldValue}>
                      {userQuery.data.organization_name ?? userQuery.data.organization_id}
                    </span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Manager</span>
                    <span className={styles.fieldValue}>
                      {userQuery.data.manager_username ??
                        (userQuery.data.manager_id ? `#${userQuery.data.manager_id}` : "—")}
                    </span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Phone</span>
                    <span className={styles.fieldValue}>
                      {userQuery.data.phone_number || "—"}
                    </span>
                  </div>
                </div>

                {editable && (
                  <button
                    type="button"
                    className={styles.primaryBtn}
                    style={{ marginTop: "1rem" }}
                    onClick={() => {
                      setSuccess(null);
                      setError(null);
                      setEditing(true);
                    }}
                  >
                    Edit user
                  </button>
                )}
              </div>
            )}

            {editing && editable && (
              <form className={styles.form} onSubmit={onSubmit} style={{ marginTop: "1rem" }}>
                <p className={styles.subtitle}>PATCH /api/v1/users/{userId}</p>
                <label>
                  Email
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Phone
                  <input value={phone} onChange={(e) => setPhone(e.target.value)} />
                </label>
                <label>
                  Role
                  <select value={role} onChange={(e) => setRole(e.target.value)}>
                    {roleOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Status
                  <select value={status} onChange={(e) => setStatus(e.target.value)}>
                    {STATUS_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                {currentUser?.role === "super_admin" && (
                  <label>
                    Organization ID
                    <input
                      type="number"
                      min={1}
                      value={organizationId}
                      onChange={(e) => setOrganizationId(e.target.value)}
                      required
                    />
                  </label>
                )}
                {role === "user" && (
                  <label>
                    Reporting manager
                    <select
                      value={managerId}
                      onChange={(e) => setManagerId(e.target.value)}
                    >
                      <option value="">No manager</option>
                      {managerOptions.map((manager) => (
                        <option key={manager.id} value={manager.id}>
                          {manager.username} ({manager.role})
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <button className={styles.primaryBtn} type="submit" disabled={mutation.isPending}>
                    {mutation.isPending ? "Saving…" : "Save changes"}
                  </button>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    onClick={() => setEditing(false)}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </>
        )}
      </section>
    </StaffShell>
  );
}
