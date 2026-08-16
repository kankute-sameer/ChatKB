import { api } from "@/lib/api";

export function logProductOpened(): Promise<{ logged: boolean }> {
  return api<{ logged: boolean }>("/v1/product/opened", {
    method: "POST",
  });
}

export function submitExperienceFeedback(
  comment: string,
): Promise<{ submitted: boolean }> {
  return api<{ submitted: boolean }>("/v1/feedback", {
    method: "POST",
    body: JSON.stringify({ comment }),
  });
}
