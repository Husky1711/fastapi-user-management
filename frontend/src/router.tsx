import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LoginPage } from "@/pages/LoginPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { HomeRedirect } from "@/pages/HomeRedirect";
import { DashboardPage } from "@/pages/DashboardPage";
import { AdminPage } from "@/pages/AdminPage";
import { AdminCreateUserPage } from "@/pages/AdminCreateUserPage";
import { AdminUserDetailPage } from "@/pages/AdminUserDetailPage";
import { AdminUsersPage } from "@/pages/AdminUsersPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { UnauthorizedPage } from "@/pages/UnauthorizedPage";
import { MaintenancePage } from "@/pages/MaintenancePage";
import { OrgAdminPage } from "@/pages/OrgAdminPage";
import { SuperAdminPage } from "@/pages/SuperAdminPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppRouter() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/maintenance" element={<MaintenancePage />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route path="/" element={<HomeRedirect />} />

            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>

            <Route element={<ProtectedRoute adminOnly />}>
              <Route path="/admin" element={<AdminPage />} />
              <Route path="/admin/users" element={<AdminUsersPage />} />
              <Route path="/admin/users/new" element={<AdminCreateUserPage />} />
              <Route path="/admin/users/:userId" element={<AdminUserDetailPage />} />
            </Route>

            <Route element={<ProtectedRoute orgAdminOnly />}>
              <Route path="/org-admin" element={<OrgAdminPage />} />
            </Route>

            <Route element={<ProtectedRoute superAdminOnly />}>
              <Route path="/super-admin" element={<SuperAdminPage />} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
