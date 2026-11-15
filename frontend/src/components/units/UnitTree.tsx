import { useTerms } from "@/lib/org/vocabulary";
import type { OrgUnit } from "@/lib/units/api";
import styles from "@/pages/UnitsPage.module.css";

/** Indented unit tree (units arrive ordered by path, so parents precede children). */
export function UnitTree({
  units,
  selectedId,
  onSelect,
}: {
  units: OrgUnit[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const { unitTypeLabel } = useTerms();
  return (
    <ul className={styles.tree}>
      {units.map((u) => (
        <li key={u.id}>
          <button
            type="button"
            className={`${styles.treeItem} ${u.id === selectedId ? styles.selected : ""}`}
            style={{ paddingLeft: `${0.6 + u.depth * 1.1}rem` }}
            onClick={() => onSelect(u.id)}
            aria-current={u.id === selectedId}
          >
            <span>{u.name}</span>
            <span className={styles.meta}>
              {unitTypeLabel(u.unit_type)} · {u.member_count ?? 0}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
