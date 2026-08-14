import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";

export function AppLayout() {
  const location = useLocation();

  return (
    <div className="flex h-full bg-background">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-hidden">
        <div key={location.pathname} className="h-full animate-enter">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
