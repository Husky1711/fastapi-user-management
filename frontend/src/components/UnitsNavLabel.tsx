import { useTerms } from "@/lib/org/vocabulary";

/** Nav label in the organization's own words ("Departments", "Wards", "Sites"...). */
export function UnitsNavLabel() {
  const { term } = useTerms();
  return <>{term("units", "Units")}</>;
}
