import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SuperAdminShell } from "@/components/SuperAdminShell";
import { createOrganization } from "@/lib/superAdmin/api";
import { getApiError } from "@/lib/apiClient";
import styles from "@/pages/ProfilePage.module.css";

export function SuperAdminCreateOrganizationPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("active");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createOrganization({
        name,
        description: description || undefined,
        status,
      }),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["super-admin", "organizations"] });
      void queryClient.invalidateQueries({ queryKey: ["super-admin", "organizations-stats"] });
      navigate(`/super-admin/organizations/${data.organization?.id ?? ""}`, { replace: true });
    },
    onError: (err) => setError(getApiError(err).detail),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <SuperAdminShell>
      <section className={styles.panel}>
        <Link to="/super-admin/organizations" className={styles.backLink}>
          ← Back to organizations
        </Link>
        <h2 style={{ marginTop: "1rem" }}>Create organization</h2>
        <p className={styles.subtitle}>POST /api/v1/organizations</p>

        <form className={styles.form} onSubmit={onSubmit}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
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
          {error && <p className={styles.error}>{error}</p>}
          <button className={styles.primaryBtn} type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create organization"}
          </button>
        </form>
      </section>
    </SuperAdminShell>
  );
}
