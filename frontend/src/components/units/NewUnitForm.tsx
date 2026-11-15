import { useMemo, useState, type FormEvent } from "react";
import { useTerms } from "@/lib/org/vocabulary";
import type { OrgUnit } from "@/lib/units/api";
import styles from "@/pages/UnitsPage.module.css";

/** Create a unit; type suggestions come from the org's sector template. */
export function NewUnitForm({
  parent,
  busy,
  onCreate,
}: {
  parent: OrgUnit | null;
  busy: boolean;
  onCreate: (name: string, unitType: string) => void;
}) {
  const { vocabulary } = useTerms();
  const [name, setName] = useState("");
  const [unitType, setUnitType] = useState("");
  const suggestions = useMemo(
    () =>
      (vocabulary?.unit_types ?? []).filter((t) => t.parents.includes(parent ? parent.unit_type : null)),
    [vocabulary, parent],
  );
  const listId = `unit-types-${parent?.id ?? "root"}`;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !unitType.trim()) return;
    onCreate(name.trim(), unitType.trim());
    setName("");
  };

  return (
    <form className={styles.row} onSubmit={submit}>
      <input
        className={styles.input}
        placeholder="Name"
        aria-label="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <input
        className={styles.input}
        placeholder="Type"
        aria-label="Type"
        list={listId}
        value={unitType}
        onChange={(e) => setUnitType(e.target.value)}
      />
      <datalist id={listId}>
        {suggestions.map((t) => (
          <option key={t.key} value={t.key}>
            {t.label}
          </option>
        ))}
      </datalist>
      <button className={`${styles.button} ${styles.primary}`} type="submit" disabled={busy}>
        Add
      </button>
    </form>
  );
}
