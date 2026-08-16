import { api } from "@/lib/api";

export function submitExperienceFeedback(
  comment: string,
): Promise<{ submitted: boolean }> {
  return api<{ submitted: boolean }>("/v1/feedback", {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}
