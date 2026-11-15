import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";
import { useAuth } from "@/lib/auth/AuthProvider";

/** Organization wording from its sector template (+ org overrides). */
export interface UnitTypeSpec {
  key: string;
  label: string;
  plural: string;
  /** Parent unit types allowed; `null` = may sit at the top level. */
  parents: (string | null)[];
}

export interface Vocabulary {
  organization_id: number;
  sector: string;
  sector_name: string;
  terms: Record<string, string>;
  role_labels: Record<string, string>;
  unit_types: UnitTypeSpec[];
  relations: { key: string; label: string }[];
}

export function useVocabulary() {
  const { status } = useAuth();
  return useQuery({
    queryKey: ["vocabulary"],
    queryFn: async () => (await apiClient.get<Vocabulary>("/api/v1/vocabulary")).data,
    enabled: status === "authenticated",
    staleTime: 5 * 60_000,
  });
}

/** Label helpers that fall back gracefully while the vocabulary loads. */
export function useTerms() {
  const { data } = useVocabulary();
  return {
    vocabulary: data,
    term: (key: string, fallback: string) => data?.terms[key] ?? fallback,
    roleLabel: (role: string) => data?.role_labels[role] ?? role.replace(/_/g, " "),
    unitTypeLabel: (key: string) => data?.unit_types.find((u) => u.key === key)?.label ?? key,
  };
}
