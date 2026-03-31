import { useQuery } from "@tanstack/react-query";

import { listCategories } from "../api/categories";
import { useSession } from "../state/session";

export function useCategories() {
  const { session } = useSession();
  return useQuery({
    queryKey: ["categories"],
    queryFn: () => listCategories(session),
    staleTime: 5 * 60 * 1000
  });
}
