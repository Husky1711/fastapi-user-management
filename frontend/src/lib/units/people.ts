import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";

export interface PersonOption {
  id: number;
  username: string;
}

/** People the current user may manage (shape of GET /users varies by role). */
export function usePeople() {
  return useQuery({
    queryKey: ["units", "people"],
    queryFn: async (): Promise<PersonOption[]> => {
      const { data } = await apiClient.get("/api/v1/users");
      const lists: PersonOption[][] = [];
      if (Array.isArray(data?.users)) lists.push(data.users);
      else if (data?.user) lists.push([data.user]);
      else if (data && typeof data === "object") {
        for (const group of Object.values(data) as { users?: PersonOption[] }[]) {
          if (Array.isArray(group?.users)) lists.push(group.users);
        }
      }
      return lists.flat().map((u) => ({ id: u.id, username: u.username }));
    },
  });
}
