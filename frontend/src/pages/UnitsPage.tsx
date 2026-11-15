import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth/AuthProvider";
import { getHomePathForRole } from "@/lib/auth/routing";
import { useTerms } from "@/lib/org/vocabulary";
import { createUnit, errorMessage, listUnits } from "@/lib/units/api";
import { usePeople } from "@/lib/units/people";
import { OrgSwitcher } from "@/components/OrgSwitcher";
import { NewUnitForm } from "@/components/units/NewUnitForm";
import { UnitPanel } from "@/components/units/UnitPanel";
import { UnitTree } from "@/components/units/UnitTree";
import adminStyles from "@/pages/AdminPage.module.css";
import styles from "./UnitsPage.module.css";

export function UnitsPage() {
  const { user } = useAuth();
  const { vocabulary, term, roleLabel, unitTypeLabel } = useTerms();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const units = useQuery({ queryKey: ["units"], queryFn: listUnits });
  const people = usePeople();
  const selected = units.data?.find((u) => u.id === selectedId) ?? null;

  const refresh = () => {
    setError(null);
    void queryClient.invalidateQueries({ queryKey: ["units"] });
  };
  const run = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: refresh,
    onError: (err) => setError(errorMessage(err)),
  });

  const unitsLabel = term("units", "Units");
  const unitLabel = term("unit", "Unit");
  const membersLabel = term("members", "Members");

  return (
    <main className={adminStyles.page}>
      <header className={adminStyles.header}>
        <div>
          <h1>{unitsLabel}</h1>
          <p className={adminStyles.subtitle}>
            {vocabulary?.sector_name ?? "Organization"} · {user?.username}
          </p>
          <OrgSwitcher />
        </div>
        <Link className={adminStyles.logoutBtn} to={getHomePathForRole(user?.role ?? "user")}>
          Back
        </Link>
      </header>

      {error && (
        <p className={adminStyles.error} role="alert">
          {error}
        </p>
      )}

      <div className={styles.layout}>
        <section className={adminStyles.card} aria-label={unitsLabel}>
          {units.isLoading && <p className={adminStyles.loading}>Loading…</p>}
          {units.isError && <p className={adminStyles.error}>{errorMessage(units.error)}</p>}
          {units.data && units.data.length === 0 && (
            <p className={styles.empty}>No {unitsLabel.toLowerCase()} yet.</p>
          )}
          <UnitTree
            units={units.data ?? []}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id);
              setError(null); // a previous failure no longer applies
            }}
          />
          <h2 className={styles.sectionTitle}>New top-level {unitLabel.toLowerCase()}</h2>
          <NewUnitForm
            parent={null}
            busy={run.isPending}
            onCreate={(name, type) => run.mutate(() => createUnit({ name, unit_type: type, parent_id: null }))}
          />
        </section>

        <section className={adminStyles.card}>
          {!selected ? (
            <p className={styles.empty}>Select a {unitLabel.toLowerCase()} to manage it.</p>
          ) : (
            <UnitPanel
              key={selected.id}
              unit={selected}
              allUnits={units.data ?? []}
              people={people.data ?? []}
              busy={run.isPending}
              run={(fn) => run.mutate(fn)}
              onDeleted={() => setSelectedId(null)}
              labels={{ membersLabel, roleLabel, unitTypeLabel }}
              roleOptions={Object.keys(vocabulary?.role_labels ?? {}).filter((r) => r !== "super_admin")}
            />
          )}
        </section>
      </div>
    </main>
  );
}
