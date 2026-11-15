import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  addUnitMember,
  createUnit,
  deleteUnit,
  errorMessage,
  grantUnitRole,
  listUnitMembers,
  listUnitRoles,
  moveUnit,
  removeUnitMember,
  renameUnit,
  revokeUnitRole,
  type OrgUnit,
} from "@/lib/units/api";
import type { PersonOption } from "@/lib/units/people";
import { NewUnitForm } from "@/components/units/NewUnitForm";
import adminStyles from "@/pages/AdminPage.module.css";
import styles from "@/pages/UnitsPage.module.css";

/** Manage one unit: rename/move/delete, sub-units, members and unit roles. */
export function UnitPanel({
  unit,
  allUnits,
  people,
  busy,
  run,
  onDeleted,
  labels,
  roleOptions,
}: {
  unit: OrgUnit;
  allUnits: OrgUnit[];
  people: PersonOption[];
  busy: boolean;
  run: (fn: () => Promise<unknown>) => void;
  onDeleted: () => void;
  labels: {
    membersLabel: string;
    roleLabel: (r: string) => string;
    unitTypeLabel: (t: string) => string;
  };
  roleOptions: string[];
}) {
  const [includeSubtree, setIncludeSubtree] = useState(false);
  const [name, setName] = useState(unit.name);
  const [memberId, setMemberId] = useState("");
  const [grantUser, setGrantUser] = useState("");
  const [grantRole, setGrantRole] = useState("");

  const members = useQuery({
    queryKey: ["units", unit.id, "members", includeSubtree],
    queryFn: () => listUnitMembers(unit.id, includeSubtree),
  });
  const roles = useQuery({
    queryKey: ["units", unit.id, "roles"],
    queryFn: () => listUnitRoles(unit.id),
  });
  const moveTargets = allUnits.filter((u) => !u.path.startsWith(unit.path));

  return (
    <div>
      <h2 className={styles.panelTitle}>{unit.name}</h2>
      <p className={styles.meta}>{labels.unitTypeLabel(unit.unit_type)}</p>

      <div className={styles.row}>
        <input
          className={styles.input}
          aria-label="Rename"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button
          className={styles.button}
          type="button"
          disabled={busy || !name.trim() || name === unit.name}
          onClick={() => run(() => renameUnit(unit.id, name.trim()))}
        >
          Rename
        </button>
        <select
          className={styles.input}
          aria-label="Move to"
          value=""
          onChange={(e) => {
            const v = e.target.value;
            if (v) run(() => moveUnit(unit.id, v === "root" ? null : Number(v)));
          }}
        >
          <option value="">Move to…</option>
          <option value="root">Top level</option>
          {moveTargets.map((u) => (
            <option key={u.id} value={u.id}>
              {"— ".repeat(u.depth)}
              {u.name}
            </option>
          ))}
        </select>
        <button
          className={`${styles.button} ${styles.danger}`}
          type="button"
          disabled={busy}
          onClick={() => {
            if (window.confirm(`Delete "${unit.name}"? Only empty units can be deleted.`)) {
              run(async () => {
                await deleteUnit(unit.id);
                onDeleted();
              });
            }
          }}
        >
          Delete
        </button>
      </div>

      <h3 className={styles.sectionTitle}>New sub-unit</h3>
      <NewUnitForm
        parent={unit}
        busy={busy}
        onCreate={(n, t) => run(() => createUnit({ name: n, unit_type: t, parent_id: unit.id }))}
      />

      <h3 className={styles.sectionTitle}>{labels.membersLabel}</h3>
      <label className={styles.row}>
        <input
          type="checkbox"
          checked={includeSubtree}
          onChange={(e) => setIncludeSubtree(e.target.checked)}
        />
        Include everything below
      </label>
      {members.isError && <p className={adminStyles.error}>{errorMessage(members.error)}</p>}
      {members.data?.length === 0 && <p className={styles.empty}>Nobody here yet.</p>}
      {members.data && members.data.length > 0 && (
        <div className={adminStyles.tableWrap}>
          <table className={adminStyles.table}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {members.data.map((m) => (
                <tr key={m.id}>
                  <td>{m.username}</td>
                  <td>{labels.roleLabel(m.role)}</td>
                  <td>
                    {!includeSubtree && (
                      <button
                        className={`${styles.button} ${styles.danger}`}
                        type="button"
                        disabled={busy}
                        onClick={() => run(() => removeUnitMember(unit.id, m.id))}
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form
        className={styles.row}
        onSubmit={(e) => {
          e.preventDefault();
          if (memberId) run(() => addUnitMember(unit.id, Number(memberId)));
          setMemberId("");
        }}
      >
        <select
          className={styles.input}
          aria-label="Person to add"
          value={memberId}
          onChange={(e) => setMemberId(e.target.value)}
        >
          <option value="">Add a person…</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.username}
            </option>
          ))}
        </select>
        <button className={`${styles.button} ${styles.primary}`} type="submit" disabled={busy || !memberId}>
          Add
        </button>
      </form>

      <h3 className={styles.sectionTitle}>Roles on this unit</h3>
      <p className={styles.meta}>Apply to this unit and everything below it.</p>
      {roles.isError && <p className={adminStyles.error}>{errorMessage(roles.error)}</p>}
      {roles.data?.length === 0 && <p className={styles.empty}>No roles granted here.</p>}
      {roles.data && roles.data.length > 0 && (
        <ul>
          {roles.data.map((g) => (
            <li key={`${g.user_id}-${g.role}`} className={styles.row}>
              {g.username} · {labels.roleLabel(g.role)}
              <button
                className={`${styles.button} ${styles.danger}`}
                type="button"
                disabled={busy}
                onClick={() => run(() => revokeUnitRole(unit.id, g.user_id, g.role))}
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className={styles.row}
        onSubmit={(e) => {
          e.preventDefault();
          if (grantUser && grantRole) run(() => grantUnitRole(unit.id, Number(grantUser), grantRole));
        }}
      >
        <select
          className={styles.input}
          aria-label="Person"
          value={grantUser}
          onChange={(e) => setGrantUser(e.target.value)}
        >
          <option value="">Person…</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.username}
            </option>
          ))}
        </select>
        <select
          className={styles.input}
          aria-label="Role"
          value={grantRole}
          onChange={(e) => setGrantRole(e.target.value)}
        >
          <option value="">Role…</option>
          {roleOptions.map((r) => (
            <option key={r} value={r}>
              {labels.roleLabel(r)}
            </option>
          ))}
        </select>
        <button
          className={`${styles.button} ${styles.primary}`}
          type="submit"
          disabled={busy || !grantUser || !grantRole}
        >
          Grant
        </button>
      </form>
    </div>
  );
}
