import { Outlet, useLocation } from "react-router-dom";
import { ProductTourDialog } from "@/components/ProductTourDialog";
import { Sidebar } from "@/components/Sidebar";
import { useAuth } from "@/features/auth/AuthProvider";

export function AppLayout() {
  const location = useLocation();
  const { productTourOpen, closeProductTour } = useAuth();

  return (
    <div className="flex h-full bg-background">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-hidden">
        <div key={location.pathname} className="h-full animate-enter">
          <Outlet />
        </div>
      </main>
      <ProductTourDialog open={productTourOpen} onClose={closeProductTour} />
    </div>
  );
}
