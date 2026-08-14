import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError } from "@/lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const username = String(form.get("username") ?? "").trim();
    const password = String(form.get("password") ?? "");
    setError(null);
    setPending(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not reach the server",
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="grid h-full grid-cols-2 bg-background">
      <div className="relative min-h-0 overflow-hidden bg-gray-900">
        <img src="/login-art.png" alt="" className="size-full object-cover" />
      </div>

      <div className="relative flex h-full flex-col items-center justify-center px-8">
        <form
          className="flex w-full max-w-login flex-col items-center gap-6"
          onSubmit={onSubmit}
        >
          <Mark />
          <h1 className="text-center font-serif text-2xl font-normal text-ink">
            Log into your account
          </h1>

          <div className="flex w-full flex-col gap-3">
            <Input
              id="username"
              name="username"
              autoComplete="username"
              placeholder="Username"
              required
              className="h-auto py-3"
            />
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="Password"
              required
              className="h-auto py-3"
            />
            {error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : null}
            <Button
              type="submit"
              disabled={pending}
              className="h-auto w-full bg-gray-700 py-3 text-white hover:bg-gray-800"
            >
              {pending ? "Signing in…" : "Continue"}
            </Button>
          </div>
        </form>

        <p className="absolute bottom-8 max-w-login px-4 text-center text-xs text-muted-foreground">
          By continuing you agree to our terms of service and privacy policy.
        </p>
      </div>
    </div>
  );
}

function Mark() {
  return (
    <svg
      viewBox="0 0 32 32"
      className="size-8 text-foreground"
      aria-hidden="true"
    >
      <circle cx="16" cy="16" r="3.5" fill="currentColor" />
      <g fill="none" stroke="currentColor" strokeWidth="1.5">
        <ellipse cx="16" cy="16" rx="11" ry="5.5" />
        <ellipse cx="16" cy="16" rx="11" ry="5.5" transform="rotate(60 16 16)" />
        <ellipse cx="16" cy="16" rx="11" ry="5.5" transform="rotate(120 16 16)" />
      </g>
    </svg>
  );
}
