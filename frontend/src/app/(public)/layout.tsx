import { AppProvider } from "@/contexts/AppContext";
import { AuthProvider } from "@/contexts/AuthContext";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AppProvider>
        <div className="min-h-screen bg-zinc-950 text-zinc-100">{children}</div>
      </AppProvider>
    </AuthProvider>
  );
}
