import { type FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SuperAdminShell } from "@/components/SuperAdminShell";
import { fetchOrganizationById, updateOrganization } from "@/lib/superAdmin/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/ProfilePage.module.css";

export function SuperAdminOrganizationDetailPage() {
  const { orgId } = useParams();
  const id = Number(orgId);
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("active");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const orgQuery = useQuery({
    queryKey: ["super-admin", "organization", id],
    queryFn: () => fetchOrganizationById(id),
    enabled: Number.isFinite(id),
  });

  useEffect(() => {
    if (!orgQuery.data) {
      return;
    }
    setName(orgQuery.data.name);
    setDescription(orgQuery.data.description ?? "");
    setStatus(orgQuery.data.status);
  }, [orgQuery.data]);

  const mutation = useMutation({
    mutationFn: () =>
      updateOrganization(id, {
        name,
        description: description || undefined,
        status,
      }),
    onSuccess: (data) => {
      setError(null);
      setSuccess(data.message);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: ["super-admin", "organization", id] });
      void queryClient.invalidateQueries({ queryKey: ["super-admin", "organizations"] });
      void queryClient.invalidateQueries({ queryKey: ["super-admin", "organizations-stats"] });
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
    <SuperAdminShell>
      <section className={styles.panel}>
        <Link to="/super-admin/organizations" className={styles.backLink}>
          ← Back to organizations
        </Link>
        <h2 style={{ marginTop: "1rem" }}>Organization detail</h2>
        <p className={styles.subtitle}>GET /api/v1/organizations/{orgId}</p>

        {orgQuery.isLoading && <p className={styles.loading}>Loading organization…</p>}
        {orgQuery.error && (
          <p className={styles.error}>{getApiError(orgQuery.error).detail}</p>
        )}

        {orgQuery.data && (
          <>
            {success && <p className={styles.success}>{success}</p>}
            {error && <p className={styles.error}>{error}</p>}

            {!editing && (
              <div className={styles.card} style={{ marginTop: "1rem" }}>
                <div className={styles.fieldGrid}>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>ID</span>
                    <span className={styles.fieldValue}>{orgQuery.data.id}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Name</span>
                    <span className={styles.fieldValue}>{orgQuery.data.name}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Status</span>
                    <span className={styles.fieldValue}>{orgQuery.data.status}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Description</span>
                    <span className={styles.fieldValue}>
                      {orgQuery.data.description || "—"}
                    </span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Total users</span>
                    <span className={styles.fieldValue}>{orgQuery.data.total_users}</span>
                  </div>
                  <div className={styles.fieldRow}>
                    <span className={styles.fieldLabel}>Active users</span>
                    <span className={styles.fieldValue}>{orgQuery.data.active_users}</span>
                  </div>
                </div>
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
                  Edit organization
                </button>
              </div>
            )}

            {editing && (
              <form className={styles.form} onSubmit={onSubmit} style={{ marginTop: "1rem" }}>
                <p className={styles.subtitle}>PATCH /api/v1/organizations/{orgId}</p>
                <label>
                  Name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    minLength={2}
                  />
                </label>
                <label>
                  Description
                  <input
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    maxLength={500}
                  />
                </label>
                <label>
                  Status
                  <select value={status} onChange={(e) => setStatus(e.target.value)}>
                    <option value="active">active</option>
                    <option value="inactive">inactive</option>
                  </select>
                </label>
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
    </SuperAdminShell>
  );
}
